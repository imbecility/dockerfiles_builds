import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright
from shared.capabilities import (
    run_common_capabilities,
    test_cdp_mhtml_snapshot,
    test_pdf_generation,
    test_permissions_apis,
    test_storage_apis,
)
from shared.utils import run_main, run_step, wait_for_cdp_server

CDP_URL = "http://localhost:9222"


def main() -> None:
    print(f"Ожидание запуска PatchBrowser CDP на {CDP_URL}...", flush=True)
    wait_for_cdp_server(CDP_URL, timeout=40)

    with sync_playwright() as p:
        print("Подключение к PatchBrowser через CDP...", flush=True)
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        context.set_default_timeout(15000)

        # 1. Базовые проверки браузера и stealth-стека
        run_common_capabilities(context)
        run_step("генерация PDF", test_pdf_generation, context)
        run_step("localStorage/sessionStorage/IndexedDB", test_storage_apis, context)
        run_step("clipboard/geolocation/notifications", test_permissions_apis, context, is_firefox=False)
        run_step("CDP: MHTML-снапшот страницы", test_cdp_mhtml_snapshot, context)

        # 2. Навигация во внешний веб
        page = context.new_page()
        try:
            print("Переход на ya.ru для проверки навигации...", flush=True)
            page.goto("https://ya.ru", wait_until="domcontentloaded", timeout=30000)
            title = page.title()
            print(f'Успешно! Заголовок страницы: "{title}"', flush=True)
            assert title, "Заголовок страницы не должен быть пустым"
        finally:
            page.close()

        context.close()
        browser.close()
        print("=== Интеграционный тест PatchBrowser успешно пройден ===", flush=True)


if __name__ == "__main__":
    run_main(main)