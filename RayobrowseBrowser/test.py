# ./RayobrowseBrowser/test.py
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import httpx
from playwright.sync_api import sync_playwright
from shared import run_chromium_smoke_suite, run_main, wait_for_cdp_server

CDP_URL = "http://localhost:9222"


def print_container_debug_logs() -> None:
    print("\n" + "=" * 50, flush=True)
    print("🚨 ДАМП ЛОГОВ КОНТЕЙНЕРА ИЗ DOCKER:", flush=True)
    print("=" * 50, flush=True)
    try:
        cids = subprocess.check_output(["docker", "ps", "-a", "-q"], text=True).strip().split()
        if cids:
            latest_cid = cids[0]
            print(f"Контейнер ID: {latest_cid}", flush=True)
            logs = subprocess.check_output(["docker", "logs", latest_cid], stderr=subprocess.STDOUT, text=True)
            print(logs if logs else "[Контейнер ничего не вывел в stdout/stderr]", flush=True)
    except Exception as e:
        print(f"[Не удалось получить логи docker: {e}]", flush=True)
    print("=" * 50 + "\n", flush=True)


def main() -> None:
    print(f"Ожидание доступности Rayobrowse на {CDP_URL}...", flush=True)
    endpoint = None

    # 1. Сначала пробуем прямой /json/version
    try:
        wait_for_cdp_server(CDP_URL, timeout=30)
        endpoint = CDP_URL
    except Exception:
        # 2. Если прямой /json/version не отвечает, запрашиваем через /connect
        print("Пробуем получить сессию через GET /connect...", flush=True)
        try:
            r = httpx.get(f"{CDP_URL}/connect", params={"os": "windows", "headless": "false", "keepAlive": "true"}, timeout=30)
            if r.status_code == 200:
                endpoint = r.text.strip()
                print(f"Получен WebSocket URL: {endpoint}", flush=True)
        except Exception as e:
            print(f"GET /connect не ответил: {e}", flush=True)
            print_container_debug_logs()
            raise

    if not endpoint:
        print_container_debug_logs()
        raise RuntimeError("Не удалось подключиться к Rayobrowse ни напрямую, ни через /connect")

    with sync_playwright() as p:
        print(f"Подключение к Rayobrowse ({endpoint})...", flush=True)
        browser = p.chromium.connect_over_cdp(endpoint)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        context.set_default_timeout(15000)

        run_chromium_smoke_suite(context, expected_extensions_count=7)

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
        print("=== Интеграционный тест Rayobrowse успешно пройден ===", flush=True)


if __name__ == "__main__":
    run_main(main)