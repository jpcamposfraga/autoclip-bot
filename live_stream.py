import subprocess
import time
from pathlib import Path
import shutil
from config import BASE_DIR, FFMPEG_BIN, MEDIA_DIR

LIVE_BUFFER_DIR = MEDIA_DIR / "live_buffer"
LIVE_BUFFER_DIR.mkdir(parents=True, exist_ok=True)

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

def start_circular_buffer(stream_url: str) -> tuple[subprocess.Popen, subprocess.Popen]:
    """Inicia gravação de buffer circular de ~100s da live em pedaços de 10s."""
    # Limpa buffer anterior
    for f in LIVE_BUFFER_DIR.glob("buffer_*.ts"):
        try:
            f.unlink()
        except Exception:
            pass

    streamlink_cmd = [
        STREAMLINK_BIN,
        "--stdout",
        "--default-stream", "best,720p,480p,worst",
        stream_url
    ]

    ffmpeg_cmd = [
        FFMPEG_BIN, "-y",
        "-i", "-",
        "-c", "copy",
        "-f", "segment",
        "-segment_time", "10",
        "-segment_wrap", "10",
        "-reset_timestamps", "1",
        str(LIVE_BUFFER_DIR / "buffer_%02d.ts")
    ]

    p_stream = subprocess.Popen(streamlink_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p_ffmpeg = subprocess.Popen(ffmpeg_cmd, stdin=p_stream.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p_stream.stdout.close()

    return p_stream, p_ffmpeg

def extract_recent_buffer(output_path: Path, num_chunks: int = 6) -> Path:
    """Junta os últimos N pedaços de 10s (ex: 6 = 60 segundos) sem re-encodamento."""
    chunks = sorted(list(LIVE_BUFFER_DIR.glob("buffer_*.ts")), key=lambda f: f.stat().st_mtime)
    if not chunks:
        raise RuntimeError("Nenhum pedaço de vídeo encontrado no buffer circular.")

    # Pega os últimos chunks completos (ignora o último que pode estar sendo escrito agora)
    selected = chunks[-num_chunks - 1 : -1] if len(chunks) > num_chunks else chunks

    concat_file = LIVE_BUFFER_DIR / "concat_list.txt"
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
