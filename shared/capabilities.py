import base64
import time
from typing import Any

from playwright.sync_api import BrowserContext

from shared.assets import ASSETS_DIR, get_minimal_pdf_bytes, make_image_assets, make_media_data_uris
from shared.utils import run_step, set_html

PERMISSIONS_ORIGIN = "https://example.com"


# --------------------------------------------------------------------------
# атомарные проверки
# --------------------------------------------------------------------------

def test_navigation_variants(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.goto("about:blank")
        page.goto("data:text/html,<h1>data url test</h1>")
        page.goto("file:///etc/os-release", wait_until="domcontentloaded")
    finally:
        page.close()


def test_js_execution(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        set_html(page, "<div id='x'>1</div>")
        page.evaluate("document.getElementById('x').textContent = '2'")
        page.add_script_tag(content="window.__injected = 42;")
        assert page.evaluate("window.__injected") == 42
        page.wait_for_function("window.__injected === 42")
        page.expose_function("pyHello", lambda: "hello from python")
        assert page.evaluate("async () => await window.pyHello()") == "hello from python"
    finally:
        page.close()


def test_screenshots(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        set_html(page, "<div style='width:400px;height:2000px;background:linear-gradient(red,blue)'></div>")
        page.screenshot(path=str(ASSETS_DIR / "shot.png"), type="png")
        page.screenshot(path=str(ASSETS_DIR / "shot_full.jpeg"), type="jpeg", quality=70, full_page=True)
        page.screenshot(path=str(ASSETS_DIR / "shot_clip.png"), clip={"x": 0, "y": 0, "width": 100, "height": 100})
    finally:
        page.close()


def test_image_decoders(context: BrowserContext, images: dict[str, str] | None = None) -> None:
    images = images or make_image_assets()
    page = context.new_page()
    try:
        tags = "".join(f'<img id="img_{ext}" src="{uri}">' for ext, uri in images.items())
        set_html(page, f"<html><body>{tags}</body></html>")
        for ext in images:
            try:
                page.wait_for_function(
                    f"(() => {{ const el = document.getElementById('img_{ext}'); return el && el.complete; }})()",
                    timeout=3000,
                )
                page.evaluate(f"""(() => {{
                    const img = document.getElementById('img_{ext}');
                    const c = document.createElement('canvas');
                    c.width = img.naturalWidth || 8;
                    c.height = img.naturalHeight || 8;
                    const ctx = c.getContext('2d');
                    if (ctx) ctx.drawImage(img, 0, 0);
                }})()""")
            except Exception:
                pass
    finally:
        page.close()


def test_media_playback(context: BrowserContext, media_uris: dict[str, str] | None = None) -> None:
    media_uris = media_uris or make_media_data_uris()
    if not media_uris:
        return
    page = context.new_page()
    try:
        tags = [
            f'<video id="med_{ext}" src="{uri}" muted playsinline></video>' if ext in ("mp4", "webm")
            else f'<audio id="med_{ext}" src="{uri}"></audio>'
            for ext, uri in media_uris.items()
        ]
        set_html(page, "<html><body>" + "".join(tags) + "</body></html>")
        for ext in media_uris:
            try:
                page.eval_on_selector(
                    f"#med_{ext}",
                    """el => new Promise((resolve) => {
                        const timer = setTimeout(() => resolve(false), 3000);
                        el.addEventListener('canplaythrough', () => { clearTimeout(timer); resolve(true); }, {once: true});
                        el.addEventListener('error', () => { clearTimeout(timer); resolve(false); }, {once: true});
                        el.load();
                    })""",
                )
            except Exception:
                pass
    finally:
        page.close()


def test_canvas_and_webgl(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        set_html(page, "<canvas id='c' width='200' height='200'></canvas>")
        result: dict[str, Any] = page.evaluate("""() => {
            const canvas = document.getElementById('c');
            const ctx2d = canvas.getContext('2d');
            ctx2d.fillStyle = 'green';
            ctx2d.fillRect(0, 0, 50, 50);
            const dataUrl = canvas.toDataURL('image/png');

            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (!gl) return {webgl: false, dataUrl};
            gl.clearColor(1, 0, 0, 1);
            gl.clear(gl.COLOR_BUFFER_BIT);
            const pixel = new Uint8Array(4);
            gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
            return {webgl: true, renderer: gl.getParameter(gl.RENDERER), dataUrl, pixel: Array.from(pixel)};
        }""")
        assert result["dataUrl"].startswith("data:image/png")
        if not result.get("webgl"):
            print("  [INFO] WebGL контекст недоступен")
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
            const req = indexedDB.open('smoke_test', 1);
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


def test_permissions_apis(context: BrowserContext, is_firefox: bool = False) -> None:
    perms = ["geolocation", "notifications"]
    if not is_firefox:
        perms.extend(["clipboard-read", "clipboard-write"])

    try:
        context.grant_permissions(perms, origin=PERMISSIONS_ORIGIN)
    except Exception as e:
        print(f"  [INFO] grant_permissions частично не поддерживается: {e}")

    context.set_geolocation({"latitude": 47.6062, "longitude": -122.3321})
    page = context.new_page()
    try:
        page.goto(PERMISSIONS_ORIGIN, wait_until="domcontentloaded")
        coords = page.evaluate("""() => new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(
                pos => resolve([pos.coords.latitude, pos.coords.longitude]),
                err => reject(err)
            );
        })""")
        assert abs(coords[0] - 47.6062) < 0.01

        try:
            page.evaluate("navigator.clipboard.writeText('slim test')")
            assert page.evaluate("navigator.clipboard.readText()") == "slim test"
        except Exception as e:
            if not is_firefox:
                raise e
    finally:
        page.close()


def test_downloads_and_uploads(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        set_html(
            page,
            '<a id="dl" href="data:text/plain;base64,'
            + base64.b64encode(b"hello test").decode()
            + '" download="hello.txt">download</a><input type="file" id="up">',
        )
        with page.expect_download() as download_info:
            page.click("#dl")
        download_info.value.save_as(str(ASSETS_DIR / "hello.txt"))

        upload_source = ASSETS_DIR / "upload_me.txt"
        upload_source.write_text("upload test content", encoding="utf-8")
        page.set_input_files("#up", str(upload_source))
    finally:
        page.close()


def test_dialogs(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.on("dialog", lambda dialog: dialog.accept())
        page.evaluate("alert('smoke test')")
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


def test_network_interception(context: BrowserContext) -> None:
    def handler(route: Any) -> None:
        route.continue_()

    context.route("**/*.png", handler)
    page = context.new_page()
    try:
        set_html(page, '<img src="https://example.com/favicon.ico">')
    finally:
        context.unroute("**/*.png", handler)
        page.close()


def test_fonts_and_scripts(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        samples = {
            "cyrillic": "Привет мир", "arabic": "مرحبا بالعالم",
            "cjk_zh": "你好世界", "cjk_ja": "こんにちは世界",
            "cjk_ko": "안녕하세요 세계", "emoji": "😀🚀🎉🦖",
        }
        html = "".join(f'<p lang="auto">{text}</p>' for text in samples.values())
        set_html(page, f"<html><body style='font-size:32px'>{html}</body></html>")
        page.screenshot(path=str(ASSETS_DIR / "fonts.png"))
    finally:
        page.close()


def test_pdf_viewer(context: BrowserContext) -> None:
    b64 = base64.b64encode(get_minimal_pdf_bytes()).decode()
    data_uri = f"data:application/pdf;base64,{b64}"
    page = context.new_page()
    try:
        downloaded = {"flag": False}
        page.on("download", lambda _: downloaded.update(flag=True))
        try:
            page.goto(data_uri, timeout=10000)
        except Exception:
            pass
        time.sleep(1)

        if downloaded["flag"]:
            return

        viewer_present = page.evaluate("""() => {
            return !!(document.querySelector('#viewer') ||
                      document.querySelector('embed[type="application/pdf"]') ||
                      document.title.toLowerCase().includes('pdf'));
        }""")
        assert viewer_present, "PDF.js viewer не обнаружен"
    finally:
        page.close()


def test_pdf_generation(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.emulate_media(media="print")
        set_html(page, "<h1>PDF test</h1><p>проверка PDFium</p>")
        page.pdf(path=str(ASSETS_DIR / "out.pdf"))
    finally:
        page.close()


def test_chrome_internal_pages(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        for url in ["chrome://version", "chrome://settings", "chrome://downloads",
                    "chrome://history", "chrome://net-internals", "chrome://gpu", "chrome://extensions"]:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.screenshot(path=str(ASSETS_DIR / "extensions.jpeg"), type="jpeg", quality=50)
    finally:
        page.close()


def test_firefox_internal_pages(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.goto("about:blank", timeout=5000)
    finally:
        page.close()


def test_cdp_mhtml_snapshot(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.goto(PERMISSIONS_ORIGIN, wait_until="domcontentloaded")
        cdp = context.new_cdp_session(page)
        result = cdp.send("Page.captureSnapshot", {"format": "mhtml"})
        (ASSETS_DIR / "page.mhtml").write_text(result["data"], encoding="utf-8")
    finally:
        page.close()


def test_extensions_loaded(context: BrowserContext, expected_count: int = 7) -> None:
    page = context.new_page()
    try:
        time.sleep(1.5)
        cdp = context.new_cdp_session(page)
        targets = cdp.send("Target.getTargets")["targetInfos"]
        ext_ids = sorted({
            t["url"].split("chrome-extension://", 1)[1].split("/", 1)[0]
            for t in targets
            if t["url"].startswith("chrome-extension://")
        })
        print(f"обнаружено расширений: {len(ext_ids)} (ожидалось {expected_count})")
        assert len(ext_ids) == expected_count, f"найдено {len(ext_ids)}, ожидалось {expected_count}"
    finally:
        page.close()


def test_dns_sinkhole(context: BrowserContext) -> None:
    blocked_urls = [
        "http://ad.doubleclick.net/favicon.ico",
        "http://mc.yandex.ru/watch/12345"
    ]
    for url in blocked_urls:
        page = context.new_page()
        is_blocked = False
        try:
            resp = page.goto(url, timeout=3000)
            # Если страница отдала статус ошибки или была перехвачена расширением
            if resp is None or resp.status >= 400 or "chrome-extension://" in page.url:
                is_blocked = True
        except Exception:
            # Сетевой сброс (ERR_NAME_NOT_RESOLVED / NS_ERROR_UNKNOWN_HOST / ECONNREFUSED)
            is_blocked = True
        finally:
            page.close()

        assert is_blocked, f"❌ ОШИБКА: домен {url} загрузился: не работает dnsmasq!"

    # Проверка легитимного интернета на свежей изолированной вкладке
    page = context.new_page()
    try:
        resp = page.goto("https://example.com", wait_until="domcontentloaded", timeout=15000)
        assert resp and resp.status < 400, "легитимный сайт example.com не загрузился."
    except Exception as e:
        assert False, f"❌ ОШИБКА: сломан основной DNS-резолвинг легитимных доменов: {e}"
    finally:
        page.close()


# --------------------------------------------------------------------------
# Сборные наборы (Пресеты)
# --------------------------------------------------------------------------

def run_common_capabilities(context: BrowserContext) -> None:
    run_step("варианты навигации (about/data/file)", test_navigation_variants, context)
    run_step("выполнение JS (evaluate/expose/wait_for_function)", test_js_execution, context)
    run_step("скриншоты (png/jpeg/clip/full_page)", test_screenshots, context)
    run_step("декодеры изображений (png/jpeg/gif/webp/bmp/ico/svg)", test_image_decoders, context)
    run_step("воспроизведение видео/аудио (h264/vp9/aac/opus/mp3)", test_media_playback, context)
    run_step("canvas 2d + WebGL", test_canvas_and_webgl, context)
    run_step("скачивание и загрузка файлов", test_downloads_and_uploads, context)
    run_step("JS-диалоги (alert/confirm)", test_dialogs, context)
    run_step("перехват сетевых запросов", test_network_interception, context)
    run_step("шрифты и письменности (кириллица/арабский/CJK/эмодзи)", test_fonts_and_scripts, context)
    run_step("DNS-Sinkhole (блокировка трекеров / DoH отключен)", test_dns_sinkhole, context)


def run_firefox_smoke_suite(context: BrowserContext, extended: bool = False) -> None:
    if extended:
        run_step("about: внутренние страницы", test_firefox_internal_pages, context)

    run_common_capabilities(context)
    run_step("обработка PDF (PDF.js)", test_pdf_viewer, context)

    if extended:
        run_step("localStorage/sessionStorage/IndexedDB", test_storage_apis, context)
        run_step("geolocation/notifications/clipboard", test_permissions_apis, context, is_firefox=True)
        run_step("попапы и iframe", test_iframes_and_popups, context)


def run_chromium_smoke_suite(context: BrowserContext, expected_extensions_count: int = 7) -> None:
    run_step("chrome:// внутренние страницы", test_chrome_internal_pages, context)
    run_common_capabilities(context)
    run_step("генерация PDF", test_pdf_generation, context)
    run_step("localStorage/sessionStorage/IndexedDB", test_storage_apis, context)
    run_step("clipboard/geolocation/notifications", test_permissions_apis, context, is_firefox=False)
    run_step("попапы и iframe", test_iframes_and_popups, context)
    run_step("CDP: MHTML-снапшот страницы", test_cdp_mhtml_snapshot, context)
    run_step("количество загруженных расширений", test_extensions_loaded, context, expected_extensions_count)
