# ./Rayobrowse/serve.py
import asyncio
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
import aiohttp
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="[rayobrowse-proxy] %(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("serve")

INTERNAL_PORT = int(os.getenv("RAYOBROWSE_INTERNAL_PORT", "9223"))
EXTERNAL_PORT = int(os.getenv("PORT", "9222"))
TARGET_OS = os.getenv("RAYOBROWSE_OS", "windows")
HEADLESS = os.getenv("RAYOBROWSE_HEADLESS", "false")

current_browser_ws: str | None = None
browser_lock = asyncio.Lock()


def init_display_and_wm() -> None:
    display = os.getenv("DISPLAY", ":99")
    os.environ["DISPLAY"] = display

    # Очистка старых lock-файлов
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
    time.sleep(1)

    # Настройка темы Openbox без рамок для консистентных outerWidth/outerHeight
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

    subprocess.Popen(["openbox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    logger.info("Менеджер окон Openbox успешно запущен.")


def get_extensions_arg() -> str:
    ext_dir = Path("/app/extensions")
    if not ext_dir.exists():
        return ""
    dirs = [str(d) for d in ext_dir.iterdir() if d.is_dir()]
    return ",".join(dirs)


async def ensure_active_browser() -> str:
    global current_browser_ws
    async with browser_lock:
        if current_browser_ws:
            # Проверяем живость текущего инстанса через ping
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(current_browser_ws, timeout=2.0) as ws:
                        await ws.close()
                        return current_browser_ws
            except Exception:
                logger.warning("Существующая сессия браузера недоступна, создаем новую...")
                current_browser_ws = None

        logger.info("Создание новой persistent stealth-сессии в Rayobrowse Daemon...")
        params = {
            "os": TARGET_OS,
            "headless": HEADLESS,
            "keepAlive": "true",
            "maxLifetime": "86400",
        }
        exts = get_extensions_arg()
        if exts:
            params["extension"] = exts

        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{INTERNAL_PORT}/connect"
            async with session.get(url, params=params, timeout=120) as resp:
                resp.raise_for_status()
                text = (await resp.text()).strip()
                # Приводим к локальному адресу демона
                if "://" in text:
                    parts = text.split("://", 1)[1]
                    path = parts.split("/", 1)[1] if "/" in parts else ""
                    current_browser_ws = f"ws://127.0.0.1:{INTERNAL_PORT}/{path}"
                else:
                    current_browser_ws = text

                logger.info(f"Браузер готов: {current_browser_ws}")
                return current_browser_ws


# --- HTTP & CDP Proxy Handlers ---

async def handle_version(request: web.Request) -> web.Response:
    try:
        await ensure_active_browser()
    except Exception as e:
        logger.error(f"Не удалось инициализировать браузер для /json/version: {e}")

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
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{INTERNAL_PORT}/health", timeout=3.0) as resp:
                data = await resp.json()
                return web.json_response(data)
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=503)


async def handle_cdp_ws(request: web.Request) -> web.WebSocketResponse:
    client_ws = web.WebSocketResponse(max_msg_size=0, timeout=None)
    await client_ws.prepare(request)

    target_ws_url = await ensure_active_browser()
    logger.info(f"CDP клиент подключен, проксирование на {target_ws_url}")

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(target_ws_url, max_msg_size=0, timeout=None) as server_ws:
            async def forward_client_to_server():
                async for msg in client_ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await server_ws.send_str(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        await server_ws.send_bytes(msg.data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        break

            async def forward_server_to_client():
                async for msg in server_ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await client_ws.send_str(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        await client_ws.send_bytes(msg.data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        break

            t1 = asyncio.create_task(forward_client_to_server())
            t2 = asyncio.create_task(forward_server_to_client())
            await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)

    return client_ws


async def wait_for_daemon():
    logger.info(f"Ожидание старта Rayobrowse Daemon на порту {INTERNAL_PORT}...")
    for _ in range(60):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{INTERNAL_PORT}/health", timeout=1.0) as resp:
                    if resp.status == 200:
                        logger.info("Rayobrowse Daemon успешно запущен.")
                        return
        except Exception:
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError("Таймаут ожидания запуска Rayobrowse Daemon!")


async def main():
    init_display_and_wm()

    # Запуск официального демона Rayobrowse
    env = dict(os.environ)
    env["STEALTH_BROWSER_ACCEPT_TERMS"] = "true"
    env["PYTHONPATH"] = "/app/rayobyte_python/src"

    daemon_proc = subprocess.Popen(
        [sys.executable, "-m", "rayobrowse.daemon", "run", "--host", "127.0.0.1", "--port", str(INTERNAL_PORT)],
        env=env,
    )

    await wait_for_daemon()

    # Прогрев сессии браузера
    try:
        await ensure_active_browser()
    except Exception as e:
        logger.warning(f"Предварительный прогрев браузера отложен: {e}")

    # Запуск внешнего HTTP/CDP сервера
    app = web.Application()
    app.router.add_get("/json/version", handle_version)
    app.router.add_get("/json", handle_json_list)
    app.router.add_get("/json/list", handle_json_list)
    app.router.add_get("/health", handle_health)

    # Перехват любых CDP WebSocket URL
    app.router.add_get("/devtools/browser/{tail:.*}", handle_cdp_ws)
    app.router.add_get("/devtools/page/{tail:.*}", handle_cdp_ws)
    app.router.add_get("/cdp/{tail:.*}", handle_cdp_ws)
    app.router.add_get("/", handle_cdp_ws)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", EXTERNAL_PORT)
    await site.start()

    logger.info(f"✨ CDP сервер готов: http://0.0.0.0:{EXTERNAL_PORT}")

    try:
        while True:
            if daemon_proc.poll() is not None:
                logger.error("Daemon процесс упал!")
                break
            await asyncio.sleep(2)
    finally:
        daemon_proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())