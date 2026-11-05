from pathlib import Path
import adbutils
import uiautomator2 as u2

COMMON_EMULATOR_ADDRESSES = [
    "127.0.0.1:5555",  # LDPlayer padrão / BlueStacks
    "127.0.0.1:5554",  # LDPlayer alternativa
    "127.0.0.1:7555",  # MuMu Player
    "127.0.0.1:62001", # Nox Player
]

def connect_device(address: str) -> str:
    try:
        res = adbutils.adb.connect(address)
        return str(res)
    except Exception as e:
        return f"Erro: {e}"

def get_connected_devices(auto_scan: bool = True) -> list[str]:
    if auto_scan:
        for addr in COMMON_EMULATOR_ADDRESSES:
            try:
                adbutils.adb.connect(addr)
            except Exception:
                pass

    try:
        devices = adbutils.adb.device_list()
        return [d.serial for d in devices]
    except Exception:
        return []

def push_video_to_gallery(device_serial: str, local_path: Path) -> bool:
    try:
        device = adbutils.adb.device(serial=device_serial)
        remote_dest = f"/sdcard/DCIM/Camera/{local_path.name}"
        
        device.shell("mkdir -p /sdcard/DCIM/Camera")
        device.sync.push(str(local_path), remote_dest)
        
        cmd = f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{remote_dest}"
        device.shell(cmd)
        return True
    except Exception as e:
        print(f"Error pushing to device {device_serial}: {e}")
        return False

def launch_app(device_serial: str, package_name: str):
    d = u2.connect(device_serial)
    d.app_start(package_name)
    return d
