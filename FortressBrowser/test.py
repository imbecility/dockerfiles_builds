# ./FortressBrowser/test.py
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright
from shared import run_chromium_smoke_suite, run_main, wait_for_cdp_server

CDP_URL = "http://localhost:9222"

def print_container_debug_logs() -> None:
    print("\n" + "=" * 50, flush=True)
    print("🚨 ТАЙМАУТ ПОДКЛЮЧЕНИЯ! ДАМП ЛОГОВ КОНТЕЙНЕРА ИЗ DOCKER:", flush=True)
    print("=" * 50, flush=True)
    try:
        # Получаем ID последнего запущенного контейнера (который создал slim)
        cids = subprocess.check_output(["docker", "ps", "-a", "-q"], text=True).strip().split()
        if cids:
            latest_cid = cids[0]
            print(f"Контейнер ID: {latest_cid}", flush=True)
            logs = subprocess.check_output(["docker", "logs", latest_cid], stderr=subprocess.STDOUT, text=True)
            print(logs if logs else "[Контейнер ничего не вывел в stdout/stderr]", flush=True)
        else:
            print("[Нет запущенных или остановленных контейнеров в docker ps -a]", flush=True)
    except Exception as e:
        print(f"[Не удалось получить логи docker: {e}]", flush=True)
    print("=" * 50 + "\n", flush=True)

def main() -> None:
    print(f"Ожидание запуска Fortress CDP на {CDP_URL}...", flush=True)
    try:
        wait_for_cdp_server(CDP_URL, timeout=30)
    except Exception:
        print_container_debug_logs()
        raise

    with sync_playwright() as p:
        print("Подключение к Fortress через CDP...", flush=True)
        browser = p.chromium.connect_over_cdp(CDP_URL)
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
        print("=== Интеграционный тест Fortress успешно пройден ===", flush=True)

if __name__ == "__main__":
    run_main(main)