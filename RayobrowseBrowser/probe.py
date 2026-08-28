# ./RayobrowseBrowser/probe.py
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright
from shared import run_chromium_smoke_suite, wait_for_cdp_server

CDP_URL = "http://localhost:9222"
SUCCESS = False


def print_full_system_and_container_dump() -> None:
    print("\n" + "=" * 60, flush=True)
    print("🚨 ДИАГНОСТИЧЕСКИЙ ДАМП СИСТЕМЫ И КОНТЕЙНЕРА 🚨", flush=True)
    print("=" * 60, flush=True)

    # 1. Память на хосте (раннере)
    try:
        mem = subprocess.check_output(["free", "-h"], text=True)
        print(f"=== RAM ХОСТА (free -h) ===\n{mem}", flush=True)
    except Exception as e:
        print(f"[Не удалось прочитать free: {e}]", flush=True)

    # 2. Список и состояние контейнеров
    try:
        cids = subprocess.check_output(["docker", "ps", "-a", "-q"], text=True).strip().split()
        if not cids:
            print("[Нет контейнеров в docker ps -a]", flush=True)
            return

        latest_cid = cids[0]
        print(f"=== КОНТЕЙНЕР ID: {latest_cid} ===", flush=True)

        # Проверка OOM статуса
        inspect_out = subprocess.check_output(
            ["docker", "inspect", latest_cid, "--format",
             "Status={{.State.Status}} ExitCode={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}} Error={{.State.Error}} FinishedAt={{.State.FinishedAt}}"],
            text=True
        )
        print(f"Статус контейнера: {inspect_out.strip()}", flush=True)

        # Логи контейнера
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

    # Регистрируем обработчики сигналов завершения
    for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP]:
        signal.signal(sig, sig_handler)

    print(f"[{time.strftime('%X')}] 1. Ожидание запуска Rayobrowse CDP на {CDP_URL}...", flush=True)
    wait_for_cdp_server(CDP_URL, timeout=60)
    print(f"[{time.strftime('%X')}] 2. CDP сервер ответил 200 OK на /json/version", flush=True)

    print(f"[{time.strftime('%X')}] 3. Подключение Playwright через connect_over_cdp...", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        print(f"[{time.strftime('%X')}] 4. Успешное подключение к CDP сессии браузера!", flush=True)

        context = browser.contexts[0] if browser.contexts else browser.new_context()
        context.set_default_timeout(20000)

        print(f"[{time.strftime('%X')}] 5. Запуск набора smoke-проверок Chromium...", flush=True)
        run_chromium_smoke_suite(context, expected_extensions_count=7)

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