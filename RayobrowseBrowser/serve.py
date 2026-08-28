# ./RayobrowseBrowser/serve.py
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
import aiohttp
from aiohttp import web

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [rayobrowse-proxy] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("serve")

INTERNAL_PORT = int(os.getenv("RAYOBROWSE_INTERNAL_PORT", "9223"))
EXTERNAL_PORT = int(os.getenv("PORT", "9222"))
TARGET_OS = os.getenv("RAYOBROWSE_OS", "windows")
HEADLESS = os.getenv("RAYOBROWSE_HEADLESS", "false")

current_browser_ws: str | None = None
browser_lock = asyncio.Lock()
daemon_ready_event = asyncio.Event()


def get_extensions_arg() -> str:
    ext_dir = Path("/app/extensions")
    if not ext_dir.exists():
        return ""
    dirs = [str(d) for d in ext_dir.iterdir() if d.is_dir()]
    return ",".join(dirs)


async def get_or_create_browser() -> str:
    """Создает свежий браузер по требованию (on-demand) без риска закрытия по idle-таймауту."""
    global current_browser_ws
    await daemon_ready_event.wait()

    async with browser_lock:
        if current_browser_ws:
            return current_browser_ws

        logger.info("Запрос создания активного инстанса Chromium в Rayobrowse Daemon...")
        params = {
            "os": TARGET_OS,
            "headless": HEADLESS,
            "keepAlive": "true",
            "maxLifetime": "86400",
        }
        exts = get_extensions_arg()
        if exts:
            params["extension"] = exts

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
            url = f"http://127.0.0.1:{INTERNAL_PORT}/connect"
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    err_body = await resp.text()
                    raise RuntimeError(f"Daemon /connect вернул {resp.status}: {err_body}")

                text = (await resp.text()).strip()
                if "://" in text:
                    parts = text.split("://", 1)[1]
                    path = parts.split("/", 1)[1] if "/" in parts else ""
                    current_browser_ws = f"ws://127.0.0.1:{INTERNAL_PORT}/{path}"
                else:
                    current_browser_ws = text

                logger.info(f"🎉 Инстанс готов: {current_browser_ws}")
                return current_browser_ws


# --- HTTP Handlers ---

async def handle_version(request: web.Request) -> web.Response:
    try:
        # Создаем или получаем живой браузер
        await get_or_create_browser()
    except Exception as e:
        logger.error(f"Ошибка создания браузера для /json/version: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=503)

    host = request.host
    return web.json_response({
        "Browser": "Chrome/146.0.7680.219",
        "Protocol-Version": "1.3",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "V8-Version": "12.0.0",
        "WebKit-Version": "537.36",
        "webSocketDebuggerUrl": f"ws://{host}/devtools/browser/default",
    })


async def handle_json_list(request: web.Request) -> web.Response:
    host = request.host
    return web.json_response([{
        "description": "",
        "devtoolsFrontendUrl": f"/devtools/inspector.html?ws={host}/devtools/page/default",
        "id": "default",
        "title": "Stealth Page",
        "type": "page",
        "url": "about:blank",
        "webSocketDebuggerUrl": f"ws://{host}/devtools/page/default",
    }])


async def handle_health(request: web.Request) -> web.Response:
    if not daemon_ready_event.is_set():
        return web.json_response({"success": False, "status": "starting"}, status=503)
    return web.json_response({"success": True, "status": "healthy"})


# --- WebSocket Proxy ---

async def handle_cdp_ws(request: web.Request) -> web.WebSocketResponse:
    global current_browser_ws
    client_ws = web.WebSocketResponse(max_msg_size=0, timeout=None, autoping=True)
    await client_ws.prepare(request)

    target_ws = await get_or_create_browser()
    logger.info(f"CDP сессия клиента открыта -> проксирование на {target_ws}")

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(target_ws, max_msg_size=0, timeout=None, autoping=True) as server_ws:
            async def forward(src, dst):
                try:
                    async for msg in src:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await dst.send_str(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await dst.send_bytes(msg.data)
                        elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                            break
                except Exception:
                    pass

            t1 = asyncio.create_task(forward(client_ws, server_ws))
            t2 = asyncio.create_task(forward(server_ws, client_ws))
            await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
            t1.cancel()
            t2.cancel()

    logger.info("CDP сессия клиента завершена.")
    current_browser_ws = None
    return client_ws


async def wait_for_daemon():
    logger.info(f"Ожидание старта Rayobrowse Daemon на порту {INTERNAL_PORT}...")
    for _ in range(120):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1.0)) as session:
                async with session.get(f"http://127.0.0.1:{INTERNAL_PORT}/health") as resp:
                    if resp.status == 200:
                        logger.info("Rayobrowse Daemon успешно запущен.")
                        daemon_ready_event.set()
                        return
        except Exception:
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError("Таймаут ожидания запуска Rayobrowse Daemon!")


async def main():
    # 1. Запуск внешнего HTTP/CDP сервера
    app = web.Application()
    for route in ["/json/version", "/json/version/"]:
        app.router.add_get(route, handle_version)
    for route in ["/json", "/json/", "/json/list", "/json/list/"]:
        app.router.add_get(route, handle_json_list)
    for route in ["/health", "/health/"]:
        app.router.add_get(route, handle_health)
    for route in ["/json/protocol", "/json/protocol/"]:
        app.router.add_get(route, handle_version)

    app.router.add_get("/devtools/browser/{tail:.*}", handle_cdp_ws)
    app.router.add_get("/devtools/page/{tail:.*}", handle_cdp_ws)
    app.router.add_get("/cdp/{tail:.*}", handle_cdp_ws)
    app.router.add_get("/ws/{tail:.*}", handle_cdp_ws)
    app.router.add_get("/", handle_cdp_ws)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", EXTERNAL_PORT)
    await site.start()
    logger.info(f"✨ CDP сервер открыт и слушает: http://0.0.0.0:{EXTERNAL_PORT}")

    # 2. Запуск официального демона Rayobrowse
    env = dict(os.environ)
    env["STEALTH_BROWSER_ACCEPT_TERMS"] = "true"
    env["PYTHONPATH"] = "/app/rayobyte_python/src"

    daemon_proc = subprocess.Popen(
        ["/usr/local/bin/python3", "-m", "rayobrowse.daemon", "run", "--host", "127.0.0.1", "--port", str(INTERNAL_PORT)],
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    await wait_for_daemon()

    try:
        while True:
            if daemon_proc.poll() is not None:
                logger.error(f"Rayobrowse Daemon процесс завершился с кодом {daemon_proc.returncode}!")
                break
            await asyncio.sleep(2)
    finally:
        daemon_proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())