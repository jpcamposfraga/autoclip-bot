import subprocess
import time
from pathlib import Path
import shutil
from config import BASE_DIR, FFMPEG_BIN, MEDIA_DIR

LIVE_BUFFER_DIR = MEDIA_DIR / "live_buffer"
LIVE_BUFFER_DIR.mkdir(parents=True, exist_ok=True)

def get_session_buffer_dir(session_id: int | str = 1) -> Path:
    s_dir = LIVE_BUFFER_DIR / f"live_{session_id}"
    s_dir.mkdir(parents=True, exist_ok=True)
    return s_dir

def _get_streamlink_bin() -> str:
    path = shutil.which("streamlink")
    if path:
        return path
    py_scripts = Path(r"C:\Users\João\AppData\Local\Python\pythoncore-3.14-64\Scripts")
    cand = py_scripts / "streamlink.exe"
    if cand.exists():
        return str(cand)
    return "streamlink"

STREAMLINK_BIN = _get_streamlink_bin()

def start_circular_buffer(stream_url: str, session_id: int | str = 1) -> tuple[subprocess.Popen, subprocess.Popen]:
    """Inicia gravação de buffer circular de ~150s da live em pedaços de 10s em pasta isolada."""
    s_dir = get_session_buffer_dir(session_id)
    # Limpa buffer anterior da sessão
    for f in s_dir.glob("buffer_*.ts"):
        try:
            f.unlink()
        except Exception:
            pass

    streamlink_cmd = [
        STREAMLINK_BIN,
        "--stdout",
        "--default-stream", "best,720p,480p,worst",
        "--twitch-disable-ads",
        "--twitch-disable-hosting",
        "--twitch-low-latency",
        stream_url
    ]

    ffmpeg_cmd = [
        FFMPEG_BIN, "-y",
        "-i", "-",
        "-c", "copy",
        "-f", "segment",
        "-segment_time", "10",
        "-segment_wrap", "15", # 15 pedaços de 10s = 150 segundos de buffer
        "-reset_timestamps", "1",
        str(s_dir / "buffer_%02d.ts")
    ]

    p_stream = subprocess.Popen(streamlink_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p_ffmpeg = subprocess.Popen(ffmpeg_cmd, stdin=p_stream.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p_stream.stdout.close()

    return p_stream, p_ffmpeg

def extract_recent_buffer(output_path: Path, session_id: int | str = 1, num_chunks: int = 8) -> Path:
    """Junta os últimos N pedaços de 10s (ex: 8 = 80 segundos) da sessão informada sem re-encodamento."""
    s_dir = get_session_buffer_dir(session_id)
    chunks = sorted(list(s_dir.glob("buffer_*.ts")), key=lambda f: f.stat().st_mtime)
    if not chunks:
        raise RuntimeError(f"Nenhum pedaço de vídeo encontrado no buffer circular da sessão {session_id}.")

    # Pega os últimos chunks completos (ignora o último que pode estar sendo escrito agora)
    selected = chunks[-num_chunks - 1 : -1] if len(chunks) > num_chunks else chunks

    concat_file = s_dir / "concat_list.txt"
    lines = [f"file '{c.resolve().as_posix()}'" for c in selected]
    concat_file.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        FFMPEG_BIN, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

def stop_circular_buffer(p_stream, p_ffmpeg):
    """Interrompe os processos de buffer com segurança."""
    for p in [p_stream, p_ffmpeg]:
        if p and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                p.kill()
