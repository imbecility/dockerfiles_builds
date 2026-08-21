import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

# Поиск бинарника в фиксированной директории
CHROME_BIN = None
for p in Path("/root/.clearcote").rglob("chrome"):
    if p.is_file() and os.access(p, os.X_OK):
        CHROME_BIN = str(p)
        break

if not CHROME_BIN:
    import clearcote
    CHROME_BIN = str(clearcote.executable_path())

print(f"[clearcote] Chromium binary: {CHROME_BIN}", flush=True)

port = int(os.getenv("PORT", "9222"))
internal = int(os.getenv("CC_INTERNAL_PORT", "9223"))
fingerprint = os.getenv("CC_FINGERPRINT", "clearcote-seed-123")
platform = os.getenv("CC_PLATFORM", "windows")
brand = os.getenv("CC_BRAND", "Chrome")

# Уникальная временная папка для профиля при каждом запуске
# (Защита от запекания мертвых lock-файлов в SlimToolkit)
profile_dir = tempfile.mkdtemp(prefix="cc_profile_")

# TCP-прокси для DevTools: 0.0.0.0:$port -> 127.0.0.1:$internal
socat_proc = subprocess.Popen(
    ["socat", f"TCP-LISTEN:{port},fork,reuseaddr,bind=0.0.0.0", f"TCP:127.0.0.1:{internal}"]
)

cmd = [
    CHROME_BIN,
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
    f"--fingerprint={fingerprint}",
    f"--fingerprint-platform={platform}",
    f"--fingerprint-brand={brand}",
    f"--user-data-dir={profile_dir}",
    "about:blank",
]

tz = os.getenv("CC_TIMEZONE")
if tz:
    cmd.append(f"--timezone={tz}")

lang = os.getenv("CC_ACCEPT_LANGUAGE")
if lang:
    cmd.append(f"--lang={lang}")

proxy = os.getenv("PROXY_SERVER")
if proxy:
    cmd.append(f"--proxy-server={proxy}")

print(f"[clearcote] Запуск Chromium: {' '.join(cmd)}", flush=True)
chrome_proc = subprocess.Popen(cmd)


def shutdown(signum, frame):
    print("[clearcote] Завершение процессов...", flush=True)
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

try:
    exit_code = chrome_proc.wait()
    socat_proc.terminate()
    sys.exit(exit_code)
except KeyboardInterrupt:
    shutdown(None, None)