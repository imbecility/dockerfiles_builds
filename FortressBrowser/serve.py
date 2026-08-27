# ./FortressBrowser/serve.py
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Фикс бага путей в tilion_fortress (ожидает вложенную папку tilion-fortress)
cache_base = Path(os.environ.get("XDG_CACHE_HOME", "/root/.cache")) / "tilion-fortress"
if cache_base.exists():
    for linux_dir in cache_base.glob("**/linux-x64"):
        tf_link = linux_dir / "tilion-fortress"
        if not tf_link.exists():
            try:
                tf_link.symlink_to(".")
                print(f"[fortress] Создан симлинк {tf_link} -> .", flush=True)
            except Exception as e:
                print(f"[fortress] Ошибка создания симлинка: {e}", flush=True)

from tilion_fortress import Fortress

INTERNAL_PORT = 9223
EXTERNAL_PORT = int(os.environ.get("PORT", "9222"))

print("[fortress] Запуск Fortress через Python SDK...", flush=True)

try:
    f = Fortress(port=INTERNAL_PORT)
except TypeError:
    try:
        f = Fortress(extra_args=[f"--remote-debugging-port={INTERNAL_PORT}"])
    except TypeError:
        f = Fortress()

f.start()
print(f"[fortress] Fortress успешно запущен: {f.cdp_url}", flush=True)

actual_port = f.cdp_url.split(":")[-1].split("/")[0] if ":" in f.cdp_url else str(INTERNAL_PORT)

if str(actual_port) != str(EXTERNAL_PORT):
    print(f"[fortress] Публикация порта через socat: 0.0.0.0:{EXTERNAL_PORT} -> 127.0.0.1:{actual_port}", flush=True)
    socat = subprocess.Popen([
        "socat",
        f"TCP-LISTEN:{EXTERNAL_PORT},fork,reuseaddr,bind=0.0.0.0",
        f"TCP:127.0.0.1:{actual_port}"
    ])

def cleanup(sig, frame):
    print("[fortress] Остановка сервера...", flush=True)
    try:
        f.stop()
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

while True:
    time.sleep(1)