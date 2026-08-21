# ./ClearcoteBrowser/test.py
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright
from shared import run_main, wait_for_cdp_server

CDP_URL = "http://localhost:9222"


def main() -> None:
    print(f"Ожидание запуска Clearcote CDP на {CDP_URL}...", flush=True)
    wait_for_cdp_server(CDP_URL, timeout=40)

    with sync_playwright() as p:
        print("Подключение к Clearcote через CDP...", flush=True)
        browser = p.chromium.connect_over_cdp(CDP_URL)
        print(f"Количество контекстов: {len(browser.contexts)}")

        context = browser.contexts[0]
        print(f"Количество существующих страниц в контексте: {len(context.pages)}")

        # Проверка 1: работа с существующей страницей
        if context.pages:
            page0 = context.pages[0]
            print(f"URL существующей страницы: {page0.url}")
            page0.goto("about:blank")
            res = page0.evaluate("() => navigator.userAgent")
            print(f"User-Agent с page0: {res}")
            page0.goto("https://ya.ru", wait_until="domcontentloaded", timeout=30000)
            print(f'Заголовок ya.ru с page0: "{page0.title()}"')

        # Проверка 2: попытка создать новую страницу
        print("Пробуем context.new_page()...")
        try:
            new_p = context.new_page()
            print(f"context.new_page() УСПЕШНО создан: {new_p.url}")
            new_p.close()
        except Exception as e:
            print(f"context.new_page() УПАЛ: {e!r}")

        context.close()
        browser.close()


if __name__ == "__main__":
    run_main(main)