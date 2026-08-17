from pathlib import Path
from sys import path

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in path:
    path.insert(0, str(ROOT_DIR))

from Camoufox.probe import (
    test_navigation_variants, test_js_execution, test_screenshots, test_pdf_handling, test_image_decoders,
    test_media_playback, test_canvas_and_webgl, test_downloads_and_uploads, test_network_interception, test_fonts_and_scripts
)
from shared.assets import make_media_data_uris, make_image_assets
from shared.utils import run_step, set_html, wait_for_ws_server

WS_URL = "ws://localhost:7861/camoufox"

PERMISSIONS_ORIGIN = "https://example.com"


def test_firefox_internal_pages(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.goto("about:blank", timeout=5000)
        # внутренние страницы Camoufox отличаются, и в нем нет стандартных страниц Firefox
        # реальные внутренние страницы пока не известны
        for url in ["about:blank", ]:
            try:
                page.goto(url, wait_until="commit", timeout=5000)
            except Exception as e:
                print(f"{url}: ошибка перехода ({e})")
    finally:
        page.close()


def test_storage_apis(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.goto(PERMISSIONS_ORIGIN, wait_until="domcontentloaded")
        page.evaluate("localStorage.setItem('k', 'v')")
        assert page.evaluate("localStorage.getItem('k')") == "v"
        page.evaluate("sessionStorage.setItem('k2', 'v2')")
        assert page.evaluate("sessionStorage.getItem('k2')") == "v2"
        idb_result = page.evaluate("""() => new Promise((resolve, reject) => {
            const req = indexedDB.open('slim_smoke_test', 1);
            req.onupgradeneeded = () => req.result.createObjectStore('store');
            req.onsuccess = () => {
                const db = req.result;
                const tx = db.transaction('store', 'readwrite');
                tx.objectStore('store').put('value', 'key');
                tx.oncomplete = () => resolve(true);
            };
            req.onerror = () => reject(req.error);
        })""")
        assert idb_result is True
    finally:
        page.close()


def test_permissions_apis(context: BrowserContext) -> None:
    for perm in ("geolocation", "notifications"):
        try:
            context.grant_permissions([perm], origin=PERMISSIONS_ORIGIN)
        except Exception as e:  # noqa: BLE001
            print(f"разрешение '{perm}' не выдано (возможно, не поддерживается в Firefox): {e}")

    context.set_geolocation({"latitude": 47.6062, "longitude": -122.3321})
    page = context.new_page()
    try:
        page.goto(PERMISSIONS_ORIGIN, wait_until="domcontentloaded")

        try:
            coords = page.evaluate("""() => new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(
                    pos => resolve([pos.coords.latitude, pos.coords.longitude]),
                    err => reject(err)
                );
            })""")
            assert abs(coords[0] - 47.6062) < 0.01
        except Exception as e:  # noqa: BLE001
            print(f"geolocation API недоступен: {e}")

        try:
            context.grant_permissions(["clipboard-read", "clipboard-write"], origin=PERMISSIONS_ORIGIN)
            page.evaluate("navigator.clipboard.writeText('slim test')")
            clipboard_value = page.evaluate("navigator.clipboard.readText()")
            assert clipboard_value == "slim test"
        except Exception as e:  # noqa: BLE001
            print(f"clipboard API недоступен в Firefox (ожидаемо, не считается провалом теста): {e}")
    finally:
        page.close()


def test_dialogs(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.on("dialog", lambda dialog: dialog.accept())
        page.evaluate("alert('slim smoke test')")
    finally:
        page.close()


def test_iframes_and_popups(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.goto(PERMISSIONS_ORIGIN, wait_until="domcontentloaded")
        with context.expect_page() as new_page_info:
            page.evaluate(f"window.open('{PERMISSIONS_ORIGIN}')")
        popup = new_page_info.value
        popup.wait_for_load_state("domcontentloaded")
        popup.close()

        set_html(page, f'<iframe src="{PERMISSIONS_ORIGIN}" style="width:200px;height:200px"></iframe>')
        page.wait_for_selector("iframe")
    finally:
        page.close()


def run_capability_smoke_test(context: BrowserContext) -> None:
    media_uris = make_media_data_uris()
    images = make_image_assets()
    run_step("about: внутренние страницы", test_firefox_internal_pages, context)
    run_step("варианты навигации (about/data/file)", test_navigation_variants, context)
    run_step("выполнение JS (evaluate/expose/wait_for_function)", test_js_execution, context)
    run_step("скриншоты (png/jpeg/clip/full_page)", test_screenshots, context)
    run_step("обработка PDF (PDF.js)", test_pdf_handling, context)
    run_step("декодеры изображений (png/jpeg/gif/webp/bmp/ico/svg)", test_image_decoders, context, images)
    run_step("воспроизведение видео/аудио (h264/vp9/aac/opus/mp3)", test_media_playback, context, media_uris)
    run_step("canvas 2d + WebGL", test_canvas_and_webgl, context)
    run_step("localStorage/sessionStorage/IndexedDB", test_storage_apis, context)
    run_step("geolocation/notifications/clipboard", test_permissions_apis, context)
    run_step("скачивание и загрузка файлов", test_downloads_and_uploads, context)
    run_step("JS-диалоги (alert/confirm)", test_dialogs, context)
    run_step("попапы и iframe", test_iframes_and_popups, context)
    run_step("перехват сетевых запросов", test_network_interception, context)
    run_step("шрифты и письменности (кириллица/арабский/CJK/эмодзи)", test_fonts_and_scripts, context)


def main() -> None:
    with sync_playwright() as p:
        browser = wait_for_ws_server(p, WS_URL, timeout=40)
        context = browser.new_context()
        context.set_default_timeout(15000)
        run_capability_smoke_test(context)
        context.set_default_timeout(30000)
        page = context.new_page()
        page.goto("https://x.com/googledevs", wait_until="domcontentloaded")
        print(f'заголовок страницы: "{page.title()}"')
        page.close()
        context.close()
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] сценарий упал с необработанной ошибкой: {e!r}")
        import traceback
        traceback.print_exc()
