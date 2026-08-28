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

BROWSER_WS_URL: str | None = None
browser_ready_event = asyncio.Event()


def get_extensions_arg() -> str:
    ext_dir = Path("/app/extensions")
    if not ext_dir.exists():
        return ""
    dirs = [str(d) for d in ext_dir.iterdir() if d.is_dir()]
    return ",".join(dirs)


async def init_singleton_browser():
    """Единожды создает постоянную сессию браузера при старте контейнера."""
    global BROWSER_WS_URL
    logger.info("Запуск прогрева singleton-сессии браузера...")

    params = {
        "os": TARGET_OS,
        "headless": HEADLESS,
        "keepAlive": "true",
        "maxLifetime": "86400",
    }
    exts = get_extensions_arg()
    if exts:
        params["extension"] = exts

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
        for attempt in range(1, 4):
            try:
                async with session.get(f"http://127.0.0.1:{INTERNAL_PORT}/connect", params=params) as resp:
                    if resp.status == 200:
                        text = (await resp.text()).strip()
                        if "://" in text:
                            parts = text.split("://", 1)[1]
                            path = parts.split("/", 1)[1] if "/" in parts else ""
                            BROWSER_WS_URL = f"ws://127.0.0.1:{INTERNAL_PORT}/{path}"
                        else:
                            BROWSER_WS_URL = text

                        logger.info(f"🎉 Singleton-сессия браузера готова: {BROWSER_WS_URL}")
                        browser_ready_event.set()
                        return
                    else:
                        err = await resp.text()
                        logger.warning(f"Попытка {attempt} /connect вернула {resp.status}: {err}")
                        await asyncio.sleep(2.0)
            except Exception as e:
                logger.warning(f"Ошибка запроса /connect (попытка {attempt}): {e}")
                await asyncio.sleep(2.0)

    logger.error("Не удалось инициализировать браузер после 3 попыток!")


# --- HTTP Handlers ---

async def handle_version(request: web.Request) -> web.Response:
    # Мгновенный ответ без каких-либо обращений к демону
    if not browser_ready_event.is_set():
        return web.json_response({"status": "starting", "message": "Browser is initializing"}, status=503)

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
    if not browser_ready_event.is_set():
        return web.json_response({"success": False, "status": "starting"}, status=503)
    return web.json_response({"success": True, "status": "healthy"})


# --- WebSocket Proxy ---

async def handle_cdp_ws(request: web.Request) -> web.WebSocketResponse:
    client_ws = web.WebSocketResponse(max_msg_size=0, timeout=None, autoping=True)
    await client_ws.prepare(request)

    await browser_ready_event.wait()
    logger.info(f"CDP клиент подключен, проксирование на {BROWSER_WS_URL}")

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(BROWSER_WS_URL, max_msg_size=0, timeout=None, autoping=True) as server_ws:
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
    return client_ws


async def wait_for_daemon():
    logger.info(f"Ожидание старта Rayobrowse Daemon на порту {INTERNAL_PORT}...")
    for _ in range(120):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1.0)) as session:
                async with session.get(f"http://127.0.0.1:{INTERNAL_PORT}/health") as resp:
                    if resp.status == 200:
                        logger.info("Rayobrowse Daemon успешно запущен.")
                        return
        except Exception:
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError("Таймаут ожидания запуска Rayobrowse Daemon!")


async def main():
    # 1. Запуск внешнего прокси-сервера на 9222
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

    # 2. Запуск демона Rayobrowse
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

    # 3. ЕДИНСТВЕННЫЙ фоновый запуск браузера при старте контейнера
    asyncio.create_task(init_singleton_browser())

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