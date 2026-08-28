# ./RayobrowseBrowser/serve.py
import asyncio
import logging
import os
import subprocess
import sys
import time
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
browser_ready_event = asyncio.Event()


def init_display_and_wm() -> None:
    display = os.getenv("DISPLAY", ":99")
    os.environ["DISPLAY"] = display

    disp_num = display.lstrip(":")
    for f in [f"/tmp/.X{disp_num}-lock", f"/tmp/.X11-unix/X{disp_num}"]:
        try:
            Path(f).unlink(missing_ok=True)
        except Exception:
            pass

    logger.info(f"Запуск Xvnc на дисплее {display} (32-bit depth)...")
    subprocess.Popen(
        ["Xvnc", display, "-geometry", "1920x1080", "-depth", "32", "-rfbport", "0", "-SecurityTypes", "None", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    theme_dir = Path.home() / ".local/share/themes/NoBorder/openbox-3"
    theme_dir.mkdir(parents=True, exist_ok=True)
    (theme_dir / "themerc").write_text(
        "border.width: 0\npadding.width: 0\npadding.height: 0\nwindow.handle.width: 0\nwindow.client.padding.width: 0\nwindow.client.padding.height: 0\n"
    )

    ob_dir = Path.home() / ".config/openbox"
    ob_dir.mkdir(parents=True, exist_ok=True)
    (ob_dir / "rc.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><openbox_config xmlns="http://openbox.org/3.4/rc">'
        '<theme><name>NoBorder</name><font place="ActiveWindow"><name>sans</name><size>0</size></font></theme>'
        '<applications><application class="*"><decor>no</decor><maximized>no</maximized></application></applications>'
        '</openbox_config>'
    )

    logger.info("Запуск менеджера окон Openbox...")
    subprocess.Popen(["openbox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for _ in range(30):
        try:
            out = subprocess.check_output(["xprop", "-root", "_NET_SUPPORTING_WM_CHECK"], stderr=subprocess.DEVNULL).decode()
            if "WINDOW" in out:
                logger.info("Openbox WM успешно зарегистрирован.")
                break
        except Exception:
            pass
        time.sleep(0.1)


def get_extensions_arg() -> str:
    ext_dir = Path("/app/extensions")
    if not ext_dir.exists():
        return ""
    dirs = [str(d) for d in ext_dir.iterdir() if d.is_dir()]
    return ",".join(dirs)


async def ensure_active_browser() -> str:
    global current_browser_ws
    # Ожидание готовности основного демона перед обращением к /connect
    await asyncio.wait_for(daemon_ready_event.wait(), timeout=60.0)

    async with browser_lock:
        if current_browser_ws:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(current_browser_ws, timeout=2.0) as ws:
                        await ws.close()
                        return current_browser_ws
            except Exception:
                logger.warning("Сессия браузера закрылась, создаем новую...")
                current_browser_ws = None
                browser_ready_event.clear()

        logger.info(f"Запрос новой stealth-сессии из Rayobrowse Daemon (порт {INTERNAL_PORT})...")
        params = {
            "os": TARGET_OS,
            "headless": HEADLESS,
            "keepAlive": "true",
            "maxLifetime": "86400",
        }
        exts = get_extensions_arg()
        if exts:
            params["extension"] = exts
            logger.info(f"Подключение расширений: {exts}")

        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{INTERNAL_PORT}/connect"
            async with session.get(url, params=params, timeout=120) as resp:
                if resp.status != 200:
                    err_body = await resp.text()
                    raise RuntimeError(f"Daemon /connect вернул статус {resp.status}: {err_body}")

                text = (await resp.text()).strip()
                if "://" in text:
                    parts = text.split("://", 1)[1]
                    path = parts.split("/", 1)[1] if "/" in parts else ""
                    current_browser_ws = f"ws://127.0.0.1:{INTERNAL_PORT}/{path}"
                else:
                    current_browser_ws = text

                logger.info(f"🎉 Stealth-браузер успешно готов: {current_browser_ws}")
                browser_ready_event.set()
                return current_browser_ws


# --- HTTP Handlers ---

async def handle_version(request: web.Request) -> web.Response:
    try:
        await asyncio.wait_for(ensure_active_browser(), timeout=45.0)
    except Exception as e:
        logger.error(f"Ошибка ожидания браузера в handle_version: {e}")
        return web.json_response({"error": str(e)}, status=503)

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
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{INTERNAL_PORT}/health", timeout=3.0) as resp:
                data = await resp.json()
                return web.json_response(data)
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=503)


# --- WebSocket Proxy ---

async def handle_cdp_ws(request: web.Request) -> web.WebSocketResponse:
    client_ws = web.WebSocketResponse(max_msg_size=0, timeout=None, autoping=True)
    await client_ws.prepare(request)

    target_ws_url = await ensure_active_browser()
    logger.info(f"CDP клиент подключен, проксирование на {target_ws_url}")

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(target_ws_url, max_msg_size=0, timeout=None, autoping=True) as server_ws:
            async def forward(src, dst):
                try:
                    async for msg in src:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await dst.send_str(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await dst.send_bytes(msg.data)
                        elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                            break
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
                except Exception:
                    pass

            t1 = asyncio.create_task(forward(client_ws, server_ws))
            t2 = asyncio.create_task(forward(server_ws, client_ws))
            done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()

    return client_ws


async def wait_for_daemon():
    logger.info(f"Ожидание старта Rayobrowse Daemon на порту {INTERNAL_PORT}...")
    for _ in range(120):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{INTERNAL_PORT}/health", timeout=1.0) as resp:
                    if resp.status == 200:
                        logger.info("Rayobrowse Daemon успешно запущен.")
                        daemon_ready_event.set()
                        return
        except Exception:
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError("Таймаут ожидания запуска Rayobrowse Daemon!")


async def main():
    init_display_and_wm()

    # 1. Запуск HTTP/CDP сервера на порту 9222
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
        [sys.executable, "-m", "rayobrowse.daemon", "run", "--host", "127.0.0.1", "--port", str(INTERNAL_PORT)],
        env=env,
    )

    await wait_for_daemon()

    # 3. Фоновый прогрев первой сессии
    asyncio.create_task(ensure_active_browser())

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