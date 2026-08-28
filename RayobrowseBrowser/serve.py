import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import aiohttp
from aiohttp import web
import httpx

INTERNAL_PORT = 9223
EXTERNAL_PORT = int(os.environ.get("PORT", "9222"))
DAEMON_HEALTH_URL = f"http://127.0.0.1:{INTERNAL_PORT}/health"
DAEMON_CONNECT_URL = f"http://127.0.0.1:{INTERNAL_PORT}/connect"

# 1. Запуск внутреннего демона Rayobrowse на порту 9223
env = os.environ.copy()
env["STEALTH_BROWSER_ACCEPT_TERMS"] = "true"
env["RAYOBROWSE_PORT"] = str(INTERNAL_PORT)
env["PORT"] = str(INTERNAL_PORT)

print(f"[rayobrowse] Запуск внутреннего демона на порту {INTERNAL_PORT}...", flush=True)

# Ищем бинарник или стартер демона из upstream образа
daemon_cmd = ["/entrypoint.sh"] if os.path.exists("/entrypoint.sh") else ["rayobrowse-daemon"]
if not os.path.exists(daemon_cmd[0]):
    # Резервный поиск стартера
    for cand in ["/app/entrypoint.sh", "/usr/local/bin/rayobrowse", "/opt/rayobrowse/entrypoint.sh"]:
        if os.path.exists(cand):
            daemon_cmd = [cand]
            break

daemon_proc = subprocess.Popen(daemon_cmd, env=env)

# Ожидание готовности демона
print("[rayobrowse] Ожидание /health демона...", flush=True)
daemon_ready = False
for _ in range(60):
    try:
        r = httpx.get(DAEMON_HEALTH_URL, timeout=1.0)
        if r.status_code == 200 and r.json().get("success"):
            daemon_ready = True
            break
    except Exception:
        pass
    time.sleep(0.5)

if not daemon_ready:
    print("[rayobrowse] ОШИБКА: Демон не поднялся за 30 секунд!", flush=True)
    daemon_proc.kill()
    sys.exit(1)

# 2. Создание постоянной браузерной сессии с расширениями
ext_paths = []
ext_dir = Path("/app/extensions")
if ext_dir.exists():
    ext_paths = [str(p) for p in ext_dir.iterdir() if p.is_dir()]

params = {
    "os": os.environ.get("RAYO_OS", "windows"),
    "headless": os.environ.get("RAYO_HEADLESS", "false"),
    "keepAlive": "true",
    "vnc": "false",
}
if ext_paths:
    params["extension"] = ",".join(ext_paths)
    print(f"[rayobrowse] Подключение {len(ext_paths)} расширений...", flush=True)

print(f"[rayobrowse] Инициализация сессии: {params}...", flush=True)
resp = httpx.get(DAEMON_CONNECT_URL, params=params, timeout=60)
resp.raise_for_status()

# Получаем целевой WebSocket URL (например ws://127.0.0.1:9223/devtools/browser/<uuid>)
UPSTREAM_WS_URL = resp.text.strip()
print(f"[rayobrowse] Сессия готова, CDP WS: {UPSTREAM_WS_URL}", flush=True)


# 3. Асинхронный прозрачный HTTP/CDP прокси на 0.0.0.0:9222
async def handle_json_version(request: web.Request) -> web.Response:
    # Ответ на GET /json/version для прямого подключения Playwright
    ws_path = UPSTREAM_WS_URL.split(f":{INTERNAL_PORT}")[-1] if f":{INTERNAL_PORT}" in UPSTREAM_WS_URL else "/devtools/browser/default"
    host = request.headers.get("Host", f"localhost:{EXTERNAL_PORT}")

    data = {
        "Browser": "Chrome/146.0.0.0",
        "Protocol-Version": "1.3",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "V8-Version": "13.0.0",
        "WebKit-Version": "537.36",
        "webSocketDebuggerUrl": f"ws://{host}{ws_path}"
    }
    return web.json_response(data)


async def handle_ws_proxy(request: web.Request) -> web.WebSocketResponse:
    client_ws = web.WebSocketResponse(autoping=True, max_msg_size=0)
    await client_ws.prepare(request)

    async with aiohttp.ClientSession() as session:
        target_ws_url = UPSTREAM_WS_URL if "devtools/browser" in request.path else f"ws://127.0.0.1:{INTERNAL_PORT}{request.path_qs}"
        async with session.ws_connect(target_ws_url, max_msg_size=0) as upstream_ws:
            async def forward_upstream():
                async for msg in client_ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await upstream_ws.send_str(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        await upstream_ws.send_bytes(msg.data)
                    elif msg.type == aiohttp.WSMsgType.CLOSE:
                        await upstream_ws.close()
                        break

            async def forward_client():
                async for msg in upstream_ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await client_ws.send_str(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        await client_ws.send_bytes(msg.data)
                    elif msg.type == aiohttp.WSMsgType.CLOSE:
                        await client_ws.close()
                        break

            await asyncio.gather(forward_upstream(), forward_client())

    return client_ws


async def handle_http_fallback(request: web.Request) -> web.Response:
    # Проксирование остальных запросов (health, connect, json) на внутренний демон
    target_url = f"http://127.0.0.1:{INTERNAL_PORT}{request.path_qs}"
    async with aiohttp.ClientSession() as session:
        body = await request.read()
        async with session.request(request.method, target_url, headers=request.headers, data=body) as upstream_resp:
            resp_body = await upstream_resp.read()
            return web.Response(body=resp_body, status=upstream_resp.status, headers=upstream_resp.headers)


async def main_server():
    app = web.Application()
    app.router.add_get("/json/version", handle_json_version)
    app.router.add_get("/json", handle_http_fallback)
    app.router.add_get("/json/list", handle_http_fallback)
    app.router.add_route("*", "/devtools/{tail:.*}", handle_ws_proxy)
    app.router.add_route("*", "/{tail:.*}", handle_http_fallback)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", EXTERNAL_PORT)
    await site.start()
    print(f"[rayobrowse] CDP Мост успешно запущен на 0.0.0.0:{EXTERNAL_PORT}", flush=True)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()

    print("[rayobrowse] Остановка моста и демона...", flush=True)
    daemon_proc.terminate()
    await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main_server())