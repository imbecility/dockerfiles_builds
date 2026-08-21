import os
import signal
import subprocess
import sys
import tempfile

from clearcote import executable_path
from clearcote._fingerprint import fingerprint_args
from clearcote._fonts import linux_font_env

exe = executable_path()
print(f"[clearcote] executable: {exe}", flush=True)

opts = {
    "fingerprint": os.environ.get("CC_FINGERPRINT", "clearcote-seed-123"),
    "platform": os.environ.get("CC_PLATFORM", "windows"),
}
brand = os.environ.get("CC_BRAND")
if brand:
    opts["brand"] = brand

args = fingerprint_args(opts)

port = os.environ.get("PORT", "9222")
internal = "9223"

# TCP-прокси для DevTools: 0.0.0.0:$port -> 127.0.0.1:$internal
socat_proc = subprocess.Popen(
    ["socat", f"TCP-LISTEN:{port},fork,reuseaddr,bind=0.0.0.0", f"TCP:127.0.0.1:{internal}"]
)

# Уникальная папка для профиля защищает от запекания мертвых локов при анализе SlimToolkit
profile_dir = tempfile.mkdtemp(prefix="cc_profile_")

cmd = [
    exe,
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-vulkan",
    "--no-first-run",
    "--no-default-browser-check",
    "--password-store=basic",
    "--window-size=1920,1080",
    "--start-maximized",
    f"--remote-debugging-port={internal}",
    "--remote-allow-origins=*",
    f"--user-data-dir={profile_dir}",
    "about:blank",
] + args

env = dict(os.environ)
try:
    # Обязательный модуль! Генерирует конфиг шрифтов в ~/.cache/clearcote
    env.update(linux_font_env(exe))
except Exception as e:
    print(f"[WARN] linux_font_env failed: {e}", flush=True)

print(f"[clearcote] Launching: {' '.join(cmd)}", flush=True)

# Запускаем как дочерний процесс
chrome_proc = subprocess.Popen(cmd, env=env)

def shutdown(signum, frame):
    print("[clearcote] Shutting down...", flush=True)
    try:
        chrome_proc.terminate()
        socat_proc.terminate()
        chrome_proc.wait(timeout=5)
    except Exception:
        chrome_proc.kill()
        socat_proc.kill()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

sys.exit(chrome_proc.wait())