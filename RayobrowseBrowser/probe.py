# ./RayobrowseBrowser/probe.py
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright
from shared.capabilities import (
    run_common_capabilities,
    test_downloads_and_uploads,
    test_extensions_loaded,
    test_pdf_generation,
    test_permissions_apis,
    test_storage_apis,
)
from shared.utils import run_step, wait_for_cdp_server

CDP_URL = "http://localhost:9222"
SUCCESS = False


def print_full_system_and_container_dump() -> None:
    print("\n" + "=" * 60, flush=True)
    print("🚨 ДИАГНОСТИЧЕСКИЙ ДАМП СИСТЕМЫ И КОНТЕЙНЕРА 🚨", flush=True)
    print("=" * 60, flush=True)

    try:
        mem = subprocess.check_output(["free", "-h"], text=True)
        print(f"=== RAM ХОСТА (free -h) ===\n{mem}", flush=True)
    except Exception as e:
        print(f"[Не удалось прочитать free: {e}]", flush=True)

    try:
        cids = subprocess.check_output(["docker", "ps", "-a", "-q"], text=True).strip().split()
        if not cids:
            print("[Нет контейнеров в docker ps -a]", flush=True)
            return

        latest_cid = cids[0]
        print(f"=== КОНТЕЙНЕР ID: {latest_cid} ===", flush=True)
        inspect_out = subprocess.check_output(
            ["docker", "inspect", latest_cid, "--format",
             "Status={{.State.Status}} ExitCode={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}} Error={{.State.Error}} FinishedAt={{.State.FinishedAt}}"],
            text=True
        )
        print(f"Статус контейнера: {inspect_out.strip()}", flush=True)

        print("\n=== ПОЛНЫЕ ЛОГИ КОНТЕЙНЕРА (docker logs) ===", flush=True)
        logs = subprocess.check_output(["docker", "logs", latest_cid], stderr=subprocess.STDOUT, text=True)
        print(logs if logs else "[Контейнер ничего не вывел в stdout/stderr]", flush=True)

    except Exception as e:
        print(f"[Ошибка получения данных docker: {e}]", flush=True)
    print("=" * 60 + "\n", flush=True)


def sig_handler(signum, frame):
    print(f"\n⚠️ Получен сигнал {signum} ({signal.Signals(signum).name})! Запуск экстренного дампа...", flush=True)
    print_full_system_and_container_dump()
    sys.exit(1)


def main() -> None:
    global SUCCESS

    for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP]:
        signal.signal(sig, sig_handler)

    print(f"[{time.strftime('%X')}] 1. Ожидание готовности Rayobrowse CDP на {CDP_URL}...", flush=True)
    wait_for_cdp_server(CDP_URL, timeout=90)
    print(f"[{time.strftime('%X')}] 2. CDP сервер и сессия браузера полностью готовы!", flush=True)

    print(f"[{time.strftime('%X')}] 3. Подключение Playwright через connect_over_cdp...", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        print(f"[{time.strftime('%X')}] 4. Успешное подключение к CDP сессии браузера!", flush=True)

        context = browser.contexts[0] if browser.contexts else browser.new_context()
        context.set_default_timeout(20000)

        print(f"[{time.strftime('%X')}] 5. Прогон capability-тестов (Slim tracing)...", flush=True)
        run_common_capabilities(context)
        run_step("генерация PDF", test_pdf_generation, context)
        run_step("localStorage/sessionStorage/IndexedDB", test_storage_apis, context)
        run_step("clipboard/geolocation/notifications", test_permissions_apis, context, is_firefox=False)
        run_step("скачивание и загрузка файлов", test_downloads_and_uploads, context)
        run_step("количество загруженных расширений", test_extensions_loaded, context, 5)

        print(f"[{time.strftime('%X')}] 6. Проверка загрузки внешней страницы (https://google.com)...", flush=True)
        page = context.new_page()
        try:
            page.goto("https://google.com", wait_until="domcontentloaded", timeout=15000)
            print(f'[{time.strftime("%X")}] 7. Заголовок страницы: "{page.title()}"', flush=True)
        finally:
            page.close()

        context.close()
        browser.close()
        SUCCESS = True
        print(f"[{time.strftime('%X')}] ✅ PROBE УСПЕШНО ЗАВЕРШЕН", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ [FATAL] Ошибка выполнения: {e!r}", flush=True)
        print_full_system_and_container_dump()
        sys.exit(1)
    finally:
        if not SUCCESS:
            print("\n⚠️ Завершение без флага успеха. Вывод дампа...", flush=True)
            print_full_system_and_container_dump()