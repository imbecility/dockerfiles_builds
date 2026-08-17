import time
from urllib.parse import quote

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright


def log(step: str, ok: bool, extra: str = "") -> None:
    mark = "OK  " if ok else "FAIL"
    suffix = f" — {extra}" if extra else ""
    print(f"[{mark}] {step}{suffix}", flush=True)


def run_step(name, fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
        log(name, True)
    except Exception as e:  # noqa: BLE001
        log(name, False, repr(e))


def set_html(page: Page, html_content: str) -> None:
    """
    универсальная вставка HTML через data:URI — не зависит от того, в одном
    ли сетевом namespace находятся тестовый скрипт (раннер) и сам браузер
    (контейнер), т.к. `--host-exec` запускает test.py на раннере."""
    page.goto(f"data:text/html;charset=utf-8,{quote(html_content)}", wait_until="domcontentloaded")


def wait_for_ws_server(pw, url: str, timeout: int = 40) -> Browser:
    """У Camoufox нет HTTP-эндпоинта вроде CDP /json/version — единственный
    надёжный способ проверить готовность, это реально попытаться подключиться."""
    print(f"Ожидание готовности Camoufox WS-сервера по адресу {url}...")
    start = time.time()
    last_err = None
    while time.time() - start < timeout:
        try:
            browser = pw.firefox.connect(url, timeout=5000)
            print("WS-сервер Camoufox готов, подключение установлено.")
            return browser
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1)
    raise RuntimeError(f"не удалось подключиться к {url} за {timeout}с: {last_err}")
