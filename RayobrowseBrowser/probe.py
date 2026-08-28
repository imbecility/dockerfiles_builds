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
    test_canvas_and_webgl,
    test_dialogs,
    test_dns_sinkhole,
    test_downloads_and_uploads,
    test_extensions_loaded,
    test_fonts_and_scripts,
    test_image_decoders,
    test_media_playback,
    test_navigation_variants,
    test_pdf_generation,
    test_screenshots,
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
        cids = subprocess.check_output(["docker", "ps", "-a", "-q"], text=True).strip().split()
        if cids:
            latest_cid = cids[0]
            print(f"КОНТЕЙНЕР ID: {latest_cid}", flush=True)
            logs = subprocess.check_output(["docker", "logs", latest_cid], stderr=subprocess.STDOUT, text=True)
            print(logs if logs else "[Контейнер ничего не вывел]", flush=True)
    except Exception as e:
        print(f"[Ошибка получения данных docker: {e}]", flush=True)
    print("=" * 60 + "\n", flush=True)


def sig_handler(signum, frame):
    print(f"\n⚠️ Получен сигнал {signum}! Запуск экстренного дампа...", flush=True)
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
        run_step("варианты навигации (about/data/file)", test_navigation_variants, context)
        run_step("скриншоты (png/jpeg/clip/full_page)", test_screenshots, context)
        run_step("декодеры изображений (png/jpeg/gif/webp/bmp/ico/svg)", test_image_decoders, context)
        run_step("воспроизведение видео/аудио (h264/vp9/aac/opus/mp3)", test_media_playback, context)
        run_step("canvas 2d + WebGL", test_canvas_and_webgl, context)
        run_step("скачивание и загрузка файлов", test_downloads_and_uploads, context)
        run_step("JS-диалоги (alert/confirm)", test_dialogs, context)
        run_step("шрифты и письменности (кириллица/арабский/CJK/эмодзи)", test_fonts_and_scripts, context)
        run_step("DNS-Sinkhole (блокировка трекеров / DoH отключен)", test_dns_sinkhole, context)
        run_step("генерация PDF", test_pdf_generation, context)
        run_step("localStorage/sessionStorage/IndexedDB", test_storage_apis, context)
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
            print_full_system_and_container_dump()