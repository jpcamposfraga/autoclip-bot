import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
import config

def send_clip_by_email(video_path: str, title: str, caption: str, recipient_email: str = None) -> tuple[bool, str]:
    cfg = config.load_email_config()
    sender_email = cfg.get("sender_email")
    sender_password = cfg.get("sender_password")
    recipient = recipient_email or cfg.get("recipient_email")
    smtp_server = cfg.get("smtp_server", "smtp.gmail.com")
    smtp_port = int(cfg.get("smtp_port", 587))

    if not sender_email or not sender_password or not recipient:
        return False, "Configurações de e-mail incompletas (remetente, senha ou destinatário ausentes)."

    v_file = Path(video_path)
    if not v_file.exists():
        return False, f"Arquivo de vídeo não encontrado: {video_path}"

    file_size_mb = v_file.stat().st_size / (1024 * 1024)
    if file_size_mb > 24.5:
        return False, f"Vídeo excede o limite de anexo de 25 MB do e-mail ({file_size_mb:.1f} MB)."

    msg = EmailMessage()
    msg["Subject"] = f"🎬 [AutoClip GTA 6]: {title}"
    msg["From"] = sender_email
    msg["To"] = recipient

    body_text = f"""Novo corte gerado automaticamente pelo AutoClip Factory!

🎬 TÍTULO:
{title}

--- LEGENDA PRONTA PARA POSTAR (COPIE ABAIXO) ---
{caption}

------------------------------------------------
O arquivo de vídeo vertical está anexado a este e-mail.
Basta tocar no anexo para salvar na galeria do seu smartphone e publicar!
"""
    msg.set_content(body_text)

    try:
        with open(v_file, "rb") as f:
            video_data = f.read()
            msg.add_attachment(
                video_data,
                maintype="video",
                subtype="mp4",
                filename=v_file.name
            )

        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls(context=context)
            server.login(sender_email, sender_password)
            server.send_message(msg)

        return True, f"Vídeo enviado com sucesso para {recipient}!"
    except Exception as e:
        return False, f"Falha ao enviar e-mail: {e}"

def test_email_connection(sender_email: str, sender_password: str, recipient_email: str) -> tuple[bool, str]:
    if not sender_email or not sender_password or not recipient_email:
        return False, "Preencha todos os campos antes de testar."

    msg = EmailMessage()
    msg["Subject"] = "🎬 [AutoClip]: Teste de Conexão de E-mail"
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg.set_content("Conexão com o servidor de e-mail realizada com sucesso! Você receberá os cortes de GTA 6 aqui.")

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.starttls(context=context)
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True, f"E-mail de teste enviado com sucesso para {recipient_email}!"
    except Exception as e:
        return False, f"Erro na conexão SMTP: {e}"
