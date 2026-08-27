# ./FortressBrowser/serve.py
import os
import signal
import subprocess
import sys
import time
from tilion_fortress import Fortress

INTERNAL_PORT = 9223
EXTERNAL_PORT = int(os.environ.get("PORT", "9222"))

print("[fortress] Запуск Fortress через официальный Python SDK...", flush=True)

# Инициализируем Fortress на внутреннем порту
try:
    f = Fortress(port=INTERNAL_PORT)
except TypeError:
    try:
        f = Fortress(extra_args=[f"--remote-debugging-port={INTERNAL_PORT}"])
    except TypeError:
        f = Fortress()

f.start()
print(f"[fortress] Fortress успешно запущен: {f.cdp_url}", flush=True)

# Определяем фактический локальный порт Chromium
actual_port = f.cdp_url.split(":")[-1].split("/")[0] if ":" in f.cdp_url else str(INTERNAL_PORT)

# Поднимаем socat для публикации внутреннего DevTools наружу контейнера (0.0.0.0:9222 -> 127.0.0.1:port)
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