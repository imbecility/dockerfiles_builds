# ./RayobrowseBrowser/serve.py
import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
import aiohttp
from aiohttp import web
import requests

INTERNAL_PORT = 9223
EXTERNAL_PORT = int(os.environ.get("PORT", "9222"))
DAEMON_CONNECT_URL = f"http://127.0.0.1:{INTERNAL_PORT}/connect"
DAEMON_HEALTH_URL = f"http://127.0.0.1:{INTERNAL_PORT}/health"

# 1. Запуск официального демона от пользователя browser
env = os.environ.copy()
env["STEALTH_BROWSER_ACCEPT_TERMS"] = "true"
env["STEALTH_BROWSER_NOVNC"] = "false"
env["DISPLAY"] = ":99"

cmd = [
    "gosu", "browser",
    "python3", "-m", "rayobrowse.daemon", "run",
    "--host", "127.0.0.1",
    "--port", str(INTERNAL_PORT)
]
daemon_proc = subprocess.Popen(cmd, env=env)

# 2. Ожидание запуска демона
print(f"[rayobrowse] Ожидание готовности демона на 127.0.0.1:{INTERNAL_PORT}...", flush=True)
for _ in range(60):
    try:
        r = requests.get(DAEMON_HEALTH_URL, timeout=1)
        if r.status_code == 200 and r.json().get("success"):
            print("[rayobrowse] Демон успешно запущен.", flush=True)
            break
    except Exception:
        pass
    time.sleep(0.5)

# 3. Инициализация постоянной сессии с расширениями
ext_paths = [str(p) for p in Path("/app/extensions").iterdir() if p.is_dir()]
params = {
    "os": "windows",
    "headless": "false",
    "keepAlive": "true",
    "vnc": "false",
}
if ext_paths:
    params["extension"] = ",".join(ext_paths)

print(f"[rayobrowse] Создание постоянного браузера: {params}...", flush=True)
resp = requests.get(DAEMON_CONNECT_URL, params=params, timeout=60)
resp.raise_for_status()
UPSTREAM_WS_URL = resp.text.strip()
print(f"[rayobrowse] Сессия готова, CDP WS: {UPSTREAM_WS_URL}", flush=True)


# 4. Прозрачный мост CDP
async def handle_ws_proxy(request: web.Request) -> web.WebSocketResponse:
    client_ws = web.WebSocketResponse(autoping=True, max_msg_size=0)
    await client_ws.prepare(request)
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(UPSTREAM_WS_URL, max_msg_size=0) as upstream_ws:
            async def fwd(src, dst):
                async for msg in src:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await dst.send_str(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        await dst.send_bytes(msg.data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        await dst.close()
                        break

            await asyncio.gather(fwd(client_ws, upstream_ws), fwd(upstream_ws, client_ws))
    return client_ws


async def handle_http_proxy(request: web.Request) -> web.Response:
    async with aiohttp.ClientSession() as session:
        body = await request.read()
        async with session.request(request.method, f"http://127.0.0.1:{INTERNAL_PORT}{request.path_qs}", headers=request.headers, data=body) as r:
            return web.Response(body=await r.read(), status=r.status, headers=r.headers)


# Единый централизованный диспетчер маршрутов
async def handle_all_requests(request: web.Request):
    path = request.path.rstrip("/")

    # 1. Отвечаем на GET /json/version со ссылкой на активный WebSocket сессии
    if request.method == "GET" and (path == "/json/version" or path == "/json"):
        host = request.headers.get("Host", f"localhost:{EXTERNAL_PORT}")
        ws_path = "/" + UPSTREAM_WS_URL.split("://", 1)[-1].split("/", 1)[-1]
        return web.json_response({
            "Browser": "Chrome/146.0.7680.219",
            "Protocol-Version": "1.3",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "V8-Version": "13.0.0",
            "WebKit-Version": "537.36",
            "webSocketDebuggerUrl": f"ws://{host}{ws_path}"
        })

    # 2. Перехватываем WebSocket подключения от Playwright/CDP клиентов
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return await handle_ws_proxy(request)

    # 3. Все прочие HTTP запросы проксируем во внутренний демон
    return await handle_http_proxy(request)


async def main():
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handle_all_requests)
    app.router.add_route("*", "/", handle_all_requests)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", EXTERNAL_PORT)
    await site.start()
    print(f"[rayobrowse] CDP Сервер готов на 0.0.0.0:{EXTERNAL_PORT}", flush=True)

    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, stop_event.set)
    await stop_event.wait()
    daemon_proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())