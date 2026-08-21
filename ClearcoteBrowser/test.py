#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from utils import wait_for_cdp_server, run_main  # noqa: E402

CDP_URL = os.environ.get("CDP_URL", "http://localhost:9222")


def main() -> None:
    # ── 1. Ждём сервера (timeout увеличен: clearcote стартует дольше 40 с) ──
    wait_for_cdp_server(CDP_URL, timeout=120)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.new_context()

        # ── 2. Создаём страницу — ОБЯЗАТЕЛЬНО для slim probe ────────────────
        # SlimToolkit трекает открытые файлы. Без new_page() renderer не
        # запускается → fontconfig/Skia/GL не трекаются → slim их удаляет →
        # SIGABRT при runtime. Этот вызов — ключ к рабочему slim-образу.
        page = ctx.new_page()

        # ── 3. Навигация (упражняем font rendering) ──────────────────────────
        print("[test] navigating to example.com …", flush=True)
        page.goto("https://example.com", timeout=30_000)

        title = page.title()
        print(f"[test] title = {title!r}", flush=True)
        assert "Example" in title, f"unexpected title: {title!r}"

        # ── 4. Stealth check ─────────────────────────────────────────────────
        wd = page.evaluate("navigator.webdriver")
        print(f"[test] navigator.webdriver = {wd}", flush=True)
        assert not wd, (
            f"navigator.webdriver={wd!r}: stealth broken, "
            "chrome was likely started with --enable-automation"
        )

        # ── 5. UA check ──────────────────────────────────────────────────────
        ua = page.evaluate("navigator.userAgent")
        print(f"[test] userAgent = {ua!r}", flush=True)
        assert "HeadlessChrome" not in ua, f"headless UA leaked: {ua!r}"

        page.close()
        ctx.close()
        browser.close()

    print("[test] ✓ all checks passed", flush=True)


if __name__ == "__main__":
    run_main(main)