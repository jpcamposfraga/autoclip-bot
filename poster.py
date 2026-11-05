import time
import random
from pathlib import Path
import uiautomator2 as u2
import adbutils
import emulator

PLATFORM_PACKAGES = {
    "tiktok": "com.zhiliaoapp.musically",
    "instagram": "com.instagram.android",
    "youtube_shorts": "com.google.android.youtube",
    "tiktok_lite": "com.zhiliaoapp.musically.go",
    "instagram_lite": "com.instagram.lite"
}

def human_sleep(min_s: float = 1.5, max_s: float = 3.2):
    time.sleep(random.uniform(min_s, max_s))

def click_element_safely(d, el, timeout: int = 5) -> bool:
    try:
        if el.wait(timeout=timeout):
            bounds = el.info.get("bounds", {})
            if bounds:
                cx = (bounds["left"] + bounds["right"]) // 2 + random.randint(-4, 4)
                cy = (bounds["top"] + bounds["bottom"]) // 2 + random.randint(-4, 4)
                d.click(cx, cy)
            else:
                el.click()
            human_sleep()
            return True
    except Exception:
        pass
    return False

def dismiss_common_dialogs(d):
    for text in ["Permitir", "PERMITIR", "Allow", "ALLOW", "Fechar", "FECHAR", "Close", "Agora não", "AGORA NÃO", "Not now", "OK", "Continuar", "CONTINUAR"]:
        btn = d(text=text)
        if btn.exists:
            btn.click()
            human_sleep(1.0, 1.8)

# ==================== INSTAGRAM OFICIAL ====================
def post_instagram_official(device, d, remote_dest: str, caption: str) -> bool:
    dismiss_common_dialogs(d)
    
    # Try Share Intent (Fastest & most direct)
    cmd = f"am start -a android.intent.action.SEND -t video/mp4 --eu android.intent.extra.STREAM file://{remote_dest} -p com.instagram.android"
    device.shell(cmd)
    human_sleep(5.0, 7.0)
    dismiss_common_dialogs(d)

    # If prompted to choose Feed, Story, or Reels, tap Reels
    if d(textContains="Reel").exists:
        click_element_safely(d, d(textContains="Reel"), timeout=4)
    elif d(textContains="REELS").exists:
        click_element_safely(d, d(textContains="REELS"), timeout=4)

    # If Intent did not navigate to composer, fallback to opening app and tapping +
    if not (d(text="Avançar").exists or d(text="Next").exists or d(className="android.widget.EditText").exists):
        d.app_start("com.instagram.android")
        human_sleep(4.0, 6.0)
        dismiss_common_dialogs(d)

        # Tap + (New Post)
        create_btn = d(descriptionContains="Nova publicação") or d(descriptionContains="New post") or d(descriptionContains="Criar") or d(descriptionContains="Create")
        if not click_element_safely(d, create_btn, timeout=6):
            d.click(540, 1850)
            human_sleep(2.0, 3.0)

        # Select REEL tab
        reel_tab = d(text="REELS") or d(text="Reels") or d(text="REEL")
        click_element_safely(d, reel_tab, timeout=4)

        # Select first video in gallery
        first_video = d(resourceId="com.instagram.android:id/gallery_grid").child(index=0) or d(className="android.widget.ImageView")
        click_element_safely(d, first_video, timeout=5)

    # In video edit screen: tap Next / Avançar
    next_btn = d(text="Avançar") or d(text="Next") or d(descriptionContains="Avançar") or d(descriptionContains="Next")
    click_element_safely(d, next_btn, timeout=6)
    human_sleep(2.0, 3.5)

    # Repeat Next if there is an audio or filter prompt
    if d(text="Avançar").exists or d(text="Next").exists:
        click_element_safely(d, d(text="Avançar") or d(text="Next"), timeout=4)

    # In Details/Share screen: fill caption
    caption_field = d(textContains="Escreva uma legenda") or d(textContains="Write a caption") or d(className="android.widget.EditText")
    if caption_field.wait(timeout=6):
        caption_field.set_text(caption)
        human_sleep(1.5, 2.5)

    # Tap Share / Compartilhar
    share_btn = d(text="Compartilhar") or d(text="Share") or d(descriptionContains="Compartilhar") or d(descriptionContains="Share")
    if click_element_safely(d, share_btn, timeout=6):
        human_sleep(5.0, 7.0)
        return True

    return False

# ==================== TIKTOK OFICIAL ====================
def post_tiktok_official(device, d, remote_dest: str, caption: str) -> bool:
    dismiss_common_dialogs(d)
    
    # Try Share Intent
    cmd = f"am start -a android.intent.action.SEND -t video/mp4 --eu android.intent.extra.STREAM file://{remote_dest} -p com.zhiliaoapp.musically"
    device.shell(cmd)
    human_sleep(6.0, 8.0)
    dismiss_common_dialogs(d)

    # If Intent did not hit composer, fallback to app start
    if not (d(text="Avançar").exists or d(text="Next").exists or d(className="android.widget.EditText").exists):
        d.app_start("com.zhiliaoapp.musically")
        human_sleep(5.0, 7.0)
        dismiss_common_dialogs(d)

        # Tap + (Record / Create)
        create_btn = d(descriptionContains="Record") or d(descriptionContains="Gravar") or d(descriptionContains="Create") or d(text="+")
        if not click_element_safely(d, create_btn, timeout=6):
            d.click(540, 1850)
            human_sleep(3.0, 4.0)

        # Tap Carregar / Upload (bottom right)
        upload_btn = d(text="Carregar") or d(text="Upload") or d(descriptionContains="Upload") or d(descriptionContains="Carregar")
        if not click_element_safely(d, upload_btn, timeout=5):
            d.click(920, 1750)
            human_sleep(2.0, 3.0)

        # Tap first video
        first_video = d(resourceIdMatches=".*item.*|.*grid.*").child(index=0) or d(className="android.widget.ImageView")
        click_element_safely(d, first_video, timeout=5)

    # In editor: tap Avançar / Next
    next_btn = d(text="Avançar") or d(text="Next") or d(descriptionContains="Avançar") or d(descriptionContains="Next")
    click_element_safely(d, next_btn, timeout=6)
    human_sleep(2.0, 3.5)

    # In details screen: enter caption
    caption_field = d(textContains="Descreva") or d(textContains="Describe") or d(className="android.widget.EditText")
    if caption_field.wait(timeout=6):
        caption_field.set_text(caption)
        human_sleep(1.5, 2.5)

    # Tap Post / Publicar
    post_btn = d(text="Publicar") or d(text="Post") or d(descriptionContains="Publicar")
    if click_element_safely(d, post_btn, timeout=6):
        human_sleep(5.0, 7.0)
        return True

    return False

# ==================== YOUTUBE SHORTS ====================
def post_youtube_shorts(d, title: str, caption: str) -> bool:
    d.app_start("com.google.android.youtube")
    human_sleep(4.0, 6.0)
    dismiss_common_dialogs(d)

    # Tap Create (+)
    create_btn = d(descriptionContains="Criar") or d(descriptionContains="Create") or d(text="+")
    click_element_safely(d, create_btn, timeout=6)

    # Tap "Criar um Short"
    create_short = d(textContains="Short") or d(text="Criar um Short") or d(text="Create a Short")
    click_element_safely(d, create_short, timeout=5)

    # Tap Gallery icon (bottom-left)
    d.click(120, 1750)
    human_sleep(2.0, 3.0)

    # Tap first video
    first_item = d(className="android.widget.ImageView")
    click_element_safely(d, first_item, timeout=5)

    # Tap Concluído / Done
    done_btn = d(text="Concluído") or d(text="Done")
    click_element_safely(d, done_btn, timeout=5)
    human_sleep(3.0, 5.0)

    # Tap Next / Avançar
    next_btn = d(text="Avançar") or d(text="Next")
    click_element_safely(d, next_btn, timeout=5)

    # Set Title
    title_field = d(className="android.widget.EditText")
    if title_field.wait(timeout=6):
        full_title = f"{title} #Shorts"
        title_field.set_text(full_title[:100])
        human_sleep(1.5, 2.5)

    # Tap Upload Short
    upload_btn = d(text="Enviar Short") or d(text="Upload Short")
    if click_element_safely(d, upload_btn, timeout=6):
        human_sleep(5.0, 7.0)
        return True

    return False

# ==================== LEGACY LITE FLOWS ====================
def post_tiktok_lite(d, caption: str) -> bool:
    d.app_start("com.zhiliaoapp.musically.go")
    human_sleep(4.0, 6.0)
    dismiss_common_dialogs(d)
    create_btn = d(descriptionContains="Create") or d(descriptionContains="Criar") or d(text="+")
    if not click_element_safely(d, create_btn, timeout=6):
        d.click(540, 1850)
    upload_btn = d(text="Carregar") or d(text="Upload")
    click_element_safely(d, upload_btn, timeout=5)
    click_element_safely(d, d(className="android.widget.ImageView"), timeout=5)
    click_element_safely(d, d(text="Avançar") or d(text="Next"), timeout=5)
    caption_field = d(className="android.widget.EditText")
    if caption_field.wait(timeout=6):
        caption_field.set_text(caption)
    return click_element_safely(d, d(text="Publicar") or d(text="Post"), timeout=6)

def post_instagram_lite(d, caption: str) -> bool:
    d.app_start("com.instagram.lite")
    human_sleep(4.0, 6.0)
    dismiss_common_dialogs(d)
    create_btn = d(descriptionContains="Nova publicação") or d(descriptionContains="Criar") or d(text="+")
    if not click_element_safely(d, create_btn, timeout=6):
        d.click(540, 1850)
    click_element_safely(d, d(className="android.widget.ImageView"), timeout=5)
    click_element_safely(d, d(text="Avançar") or d(text="Next"), timeout=5)
    caption_field = d(className="android.widget.EditText")
    if caption_field.wait(timeout=6):
        caption_field.set_text(caption)
    return click_element_safely(d, d(text="Compartilhar") or d(text="Share"), timeout=6)

# ==================== MAIN DISPATCHER ====================
def post_clip(device_serial: str, platform: str, video_path: str, title: str, caption: str) -> bool:
    v_path = Path(video_path)
    if not v_path.exists():
        raise FileNotFoundError(f"Arquivo de vídeo não encontrado: {video_path}")

    # Push to device gallery
    if not emulator.push_video_to_gallery(device_serial, v_path):
        raise RuntimeError(f"Falha ao transferir {v_path.name} para o emulador {device_serial}")

    remote_dest = f"/sdcard/DCIM/Camera/{v_path.name}"
    device = adbutils.adb.device(serial=device_serial)
    d = u2.connect(device_serial)

    if platform in ["instagram", "instagram_official"]:
        return post_instagram_official(device, d, remote_dest, caption)
    elif platform in ["tiktok", "tiktok_official"]:
        return post_tiktok_official(device, d, remote_dest, caption)
    elif platform == "youtube_shorts":
        return post_youtube_shorts(d, title, caption)
    elif platform == "instagram_lite":
        return post_instagram_lite(d, caption)
    elif platform == "tiktok_lite":
        return post_tiktok_lite(d, caption)
    else:
        raise ValueError(f"Plataforma não suportada: {platform}")
