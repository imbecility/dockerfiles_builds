import sys
import time
import traceback
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx
from playwright.sync_api import Browser, Page, Playwright


def log(step: str, ok: bool, extra: str = "") -> None:
    mark = "OK  " if ok else "FAIL"
    suffix = f" — {extra}" if extra else ""
    print(f"[{mark}] {step}{suffix}", flush=True)


def run_step(name: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
    try:
        fn(*args, **kwargs)
        log(name, True)
        return True
    except Exception as e:  # noqa: BLE001
        log(name, False, repr(e))
        return False


def set_html(page: Page, html_content: str) -> None:
    """
    универсальная вставка HTML через data:URI — не зависит от того, в одном
    ли сетевом namespace находятся тестовый скрипт (раннер) и сам браузер
    (контейнер), т.к. `--host-exec` запускает test.py на раннере.
    """
    page.goto(f"data:text/html;charset=utf-8,{quote(html_content)}", wait_until="domcontentloaded")


def wait_for_ws_server(pw: Playwright, url: str, timeout: int = 40) -> Browser:
    print(f"Ожидание готовности WS-сервера по адресу {url}...")
    start = time.time()
    last_err: Exception | None = None
    while time.time() - start < timeout:
        try:
            browser = pw.firefox.connect(url, timeout=5000)
            print("WS-сервер готов, подключение установлено.")
            return browser
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1)
    raise RuntimeError(f"не удалось подключиться к WS {url} за {timeout}с: {last_err}")


def wait_for_cdp_server(url: str, timeout: int = 30) -> None:
    print(f"ожидание готовности CDP-сервера по адресу {url}...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = httpx.get(f"{url}/json/version", timeout=2.0)
            if response.status_code == 200:
                print("CDP-сервер успешно запущен и готов к работе!")
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f"сервер CDP на {url} не ответил за {timeout} секунд.")


def run_main(main_fn: Callable[[], None]) -> None:
    try:
        main_fn()
    except Exception as e:
        print(f"[FATAL] сценарий упал с ошибкой: {e!r}", flush=True)
        traceback.print_exc()
        sys.exit(1)