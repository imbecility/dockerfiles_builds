# ./RayobrowseBrowser/serve.py
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
import httpx

DAEMON_PORT = 9223
EXTERNAL_PORT = int(os.environ.get("PORT", "9222"))

# 1. Запуск нативного демона rayobrowse на внутреннем порту 9223
env = os.environ.copy()
env["STEALTH_BROWSER_ACCEPT_TERMS"] = "true"
env["RAYOBROWSE_PORT"] = str(DAEMON_PORT)
env["PORT"] = str(DAEMON_PORT)

print(f"[rayobrowse] Запуск демона на порту {DAEMON_PORT}...", flush=True)

# Запускаем оригинальный entrypoint демона
daemon_cmd = ["/entrypoint.sh"] if os.path.exists("/entrypoint.sh") else ["rayobrowse-daemon"]
daemon_proc = subprocess.Popen(daemon_cmd, env=env)

def cleanup(sig=None, frame=None):
    print("[rayobrowse] Завершение процесса демона...", flush=True)
    try:
        daemon_proc.terminate()
        daemon_proc.wait(timeout=5)
    except Exception:
        daemon_proc.kill()
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

# 2. Ожидание готовности демона (/health)
print("[rayobrowse] Ожидание /health...", flush=True)
ready = False
for i in range(60):
    try:
        r = httpx.get(f"http://127.0.0.1:{DAEMON_PORT}/health", timeout=1.0)
        if r.status_code == 200 and r.json().get("success"):
            ready = True
            print(f"[rayobrowse] Демон готов (попытка {i+1})", flush=True)
            break
    except Exception:
        pass
    if daemon_proc.poll() is not None:
        print(f"[rayobrowse] FATAL: Демон упал с кодом {daemon_proc.returncode}", flush=True)
        sys.exit(1)
    time.sleep(0.5)

if not ready:
    print("[rayobrowse] FATAL: Таймаут ожидания /health", flush=True)
    cleanup()

# 3. Создаем постоянную сессию браузера
ext_paths = []
ext_dir = Path("/app/extensions")
if ext_dir.exists():
    ext_paths = [str(p) for p in ext_dir.iterdir() if p.is_dir()]

params = {
    "os": "windows",
    "headless": "false",
    "keepAlive": "true",
    "vnc": "false",
}
if ext_paths:
    params["extension"] = ",".join(ext_paths)
    print(f"[rayobrowse] Загрузка {len(ext_paths)} расширений...", flush=True)

print(f"[rayobrowse] Запрос браузерной сессии: {params}...", flush=True)
try:
    resp = httpx.get(f"http://127.0.0.1:{DAEMON_PORT}/connect", params=params, timeout=120)
    resp.raise_for_status()
    ws_url = resp.text.strip()
    print(f"[rayobrowse] Сессия создана: {ws_url}", flush=True)
except Exception as e:
    print(f"[rayobrowse] Ошибка вызова /connect: {e}", flush=True)
    cleanup()

# 4. Проксируем внешний порт 9222 на внутренний порт 9223 через socat
# Демон сам обрабатывает /json/version и все CDP WebSocket соединения
print(f"[rayobrowse] Публикация порта 0.0.0.0:{EXTERNAL_PORT} -> 127.0.0.1:{DAEMON_PORT}...", flush=True)
socat_proc = subprocess.Popen([
    "socat",
    f"TCP-LISTEN:{EXTERNAL_PORT},fork,reuseaddr,bind=0.0.0.0",
    f"TCP:127.0.0.1:{DAEMON_PORT}"
])

# Мониторим процессы
while True:
    if daemon_proc.poll() is not None:
        print(f"[rayobrowse] Демон завершился с кодом {daemon_proc.returncode}", flush=True)
        break
    if socat_proc.poll() is not None:
        print(f"[rayobrowse] Socat завершился с кодом {socat_proc.returncode}", flush=True)
        break
    time.sleep(1)

cleanup()