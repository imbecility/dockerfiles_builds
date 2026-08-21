#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from utils import wait_for_cdp_server, run_main  # noqa: E402

CDP_URL = os.environ.get("CDP_URL", "http://localhost:9222")


def main() -> None:
    print(f"Ожидание запуска Clearcote CDP на {CDP_URL}...", flush=True)
    wait_for_cdp_server(CDP_URL, timeout=120)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        print(f"Подключение Playwright к {CDP_URL}...", flush=True)
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()

        # Важно: Вызов new_page() заставляет спавниться renderer-процесс в Docker
        # Это гарантирует, что SlimToolkit зафиксирует вызовы к fontconfig и Skia
        page = ctx.new_page()
        print("Переход на https://example.com...", flush=True)
        page.goto("https://example.com", timeout=30000)

        title = page.title()
        print(f"Заголовок: {title!r}", flush=True)
        assert "Example" in title, f"Неожиданный заголовок: {title!r}"

        webdriver = page.evaluate("navigator.webdriver")
        print(f"navigator.webdriver = {webdriver}", flush=True)
        assert not webdriver, "navigator.webdriver должен быть False"

        page.close()
        browser.close()

    print("✓ Тест прошел успешно!", flush=True)


if __name__ == "__main__":
    run_main(main)