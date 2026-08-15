import base64
import io
import shutil
import subprocess
import tempfile
import time

from pathlib import Path
from urllib.parse import quote, urlencode

from playwright._impl._api_structures import SetCookieParam  # noqa
from playwright.sync_api import BrowserContext, Page, sync_playwright
import httpx

CDP_URL = "http://localhost:7860"

ASSETS_DIR = Path(tempfile.gettempdir()) / "cdp_browser_assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


cookies: list[SetCookieParam] = [
    {'name': 'ys', 'value': 'wprid.1779106375637420-12880543316618692126-balancer-l7leveler-kubr-yp-klg-290-BAL', 'domain': '.yandex.com', 'path': '/', 'httpOnly': False, 'secure': True, 'sameSite': 'None', 'expires': 2094715208.043561},
    {'name': 'yp', 'value': '1779970352.dlp.2#2094466377.pcs.1#1810642356.sp.shst%3A1%3Ashsh%3A1%3Afamily%3A0#1779711159.szm.1_25%3A2048x1152%3A2033x1031%3A15#1779279175.ygo.10493%3A87#1781698375.ygu.0', 'domain': '.yandex.com', 'path': '/', 'httpOnly': False, 'secure': True, 'sameSite': 'None', 'expires': 2094715208.088647},
    {'name': 'yandex_gid', 'value': '87', 'domain': '.yandex.com', 'path': '/', 'httpOnly': False, 'secure': True, 'sameSite': 'None', 'expires': 2094715208.433255},
]

PERMISSIONS_ORIGIN = "https://example.com"

# должно совпадать с количеством путей в --load-extension в Dockerfile/start.sh
EXPECTED_EXTENSIONS_COUNT = 7

def log(step: str, ok: bool, extra: str = "") -> None:
    mark = "OK  " if ok else "FAIL"
    suffix = f" — {extra}" if extra else ""
    print(f"[{mark}] {step}{suffix}")


def run_step(name, fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
        log(name, True)
    except Exception as e:  # noqa: BLE001
        log(name, False, repr(e))


def set_html(page: Page, html_content: str) -> None:
    """универсальная вставка HTML через data:URI, надежно работающая в любых CDP-прокси."""
    page.goto(f"data:text/html;charset=utf-8,{quote(html_content)}", wait_until="domcontentloaded")


# --------------------------------------------------------------------------
# генерация ассетов в data-URI
# --------------------------------------------------------------------------

def make_media_data_uris() -> dict:
    assets = {}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg не найден в PATH — пропускаю генерацию видео/аудио. "
              "Убедитесь, что linux_deps.txt подхвачен и пакеты установлены на раннере.")
        return assets

    specs = [
        ("mp4", "video/mp4", ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-c:a", "aac", "-shortest"]),
        ("webm", "video/webm", ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libvpx-vp9", "-c:a", "libopus", "-shortest"]),
        ("mp3", "audio/mp3", ["-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "libmp3lame"]),
        ("ogg", "audio/ogg", ["-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "libvorbis"]),
    ]
    for ext, mime, args in specs:
        out_path = ASSETS_DIR / f"test.{ext}"
        cmd = [ffmpeg, "-y", *args, str(out_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            b64 = base64.b64encode(out_path.read_bytes()).decode()
            assets[ext] = f"data:{mime};base64,{b64}"
        except Exception:
            pass
    return assets


def make_image_assets() -> dict:
    images: dict = {}
    try:
        from PIL import Image
        base = Image.new("RGB", (8, 8), color=(255, 0, 0))
        formats = {"png": "PNG", "jpeg": "JPEG", "gif": "GIF", "webp": "WEBP", "bmp": "BMP", "ico": "ICO"}
        for ext, fmt in formats.items():
            try:
                buf = io.BytesIO()
                base.save(buf, format=fmt)
                b64 = base64.b64encode(buf.getvalue()).decode()
                images[ext] = f"data:image/{ext};base64,{b64}"
            except Exception:
                pass
    except ImportError:
        images["png"] = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        images["gif"] = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="

    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="blue"/></svg>'
    images["svg"] = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    return images


# --------------------------------------------------------------------------
# отдельные проверки
# --------------------------------------------------------------------------

def test_chrome_internal_pages(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        for url in ["chrome://version", "chrome://settings", "chrome://downloads",
                    "chrome://history", "chrome://net-internals", "chrome://gpu",
                    "chrome://extensions"]:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.screenshot(path=str(ASSETS_DIR / "extensions.jpeg"), type="jpeg", quality=50)
    finally:
        page.close()


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
        result = page.evaluate("async () => await window.pyHello()")
        assert result == "hello from python"
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


def test_pdf_generation(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.emulate_media(media="print")
        set_html(page, "<h1>PDF test</h1><p>проверка PDFium</p>")
        page.pdf(path=str(ASSETS_DIR / "out.pdf"))
    finally:
        page.close()


def test_image_decoders(context: BrowserContext, images: dict) -> None:
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


def test_media_playback(context: BrowserContext, media_uris: dict) -> None:
    if not media_uris:
        print("нет тестовых медиафайлов — пропускаю.")
        return
    page = context.new_page()
    try:
        tags = []
        for ext, uri in media_uris.items():
            if ext in ("mp4", "webm"):
                tags.append(f'<video id="med_{ext}" src="{uri}" muted playsinline></video>')
            else:
                tags.append(f'<audio id="med_{ext}" src="{uri}"></audio>')
        set_html(page, "<html><body>" + "".join(tags) + "</body></html>")
        for ext in media_uris:
            page.eval_on_selector(
                f"#med_{ext}",
                """el => new Promise((resolve, reject) => {
                    el.addEventListener('canplaythrough', () => resolve(true), {once: true});
                    el.addEventListener('error', () => reject(new Error('decode error: ' + ext)), {once: true});
                    el.load();
                })""",
            )
    finally:
        page.close()


def test_canvas_and_webgl(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        set_html(page, "<canvas id='c' width='200' height='200'></canvas>")
        result = page.evaluate("""() => {
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
            gl.readPixels(100, 100, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
            return {webgl: true, renderer: gl.getParameter(gl.RENDERER), pixel: Array.from(pixel), dataUrl};
        }""")
        assert result["dataUrl"].startswith("data:image/png")
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
    context.grant_permissions(
        ["clipboard-read", "clipboard-write", "geolocation", "notifications"],
        origin=PERMISSIONS_ORIGIN,
    )
    context.set_geolocation({"latitude": 47.6062, "longitude": -122.3321})
    page = context.new_page()
    try:
        page.goto(PERMISSIONS_ORIGIN, wait_until="domcontentloaded")

        page.evaluate("navigator.clipboard.writeText('slim test')")
        clipboard_value = page.evaluate("navigator.clipboard.readText()")
        assert clipboard_value == "slim test"

        coords = page.evaluate("""() => new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(
                pos => resolve([pos.coords.latitude, pos.coords.longitude]),
                err => reject(err)
            );
        })""")
        assert abs(coords[0] - 47.6062) < 0.01
    finally:
        page.close()


def test_downloads_and_uploads(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        set_html(
            page,
            '<a id="dl" href="data:text/plain;base64,'
            + base64.b64encode(b"hello from slim smoke test").decode()
            + '" download="hello.txt">download</a>'
            '<input type="file" id="up">'
        )
        with page.expect_download() as download_info:
            page.click("#dl")
        download = download_info.value
        download.save_as(str(ASSETS_DIR / "hello.txt"))

        upload_source = ASSETS_DIR / "upload_me.txt"
        upload_source.write_text("upload test content", encoding="utf-8")
        page.set_input_files("#up", str(upload_source))
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


def test_network_interception(context: BrowserContext) -> None:
    def handler(route):
        route.continue_()

    context.route("**/*.png", handler)
    page = context.new_page()
    try:
        set_html(page, '<img src="https://example.com/favicon.ico">')
    finally:
        context.unroute("**/*.png", handler)
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


def test_fonts_and_scripts(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        samples = {
            "cyrillic": "Привет мир",
            "arabic": "مرحبا بالعالم",
            "cjk_zh": "你好世界",
            "cjk_ja": "こんにちは世界",
            "cjk_ko": "안녕하세요 세계",
            "emoji": "😀🚀🎉🦖",
        }
        html = "".join(f'<p lang="auto">{text}</p>' for text in samples.values())
        set_html(page, f"<html><body style='font-size:32px'>{html}</body></html>")
        page.screenshot(path=str(ASSETS_DIR / "fonts.png"))
    finally:
        page.close()


def test_extensions_loaded(context: BrowserContext, expected_count: int = EXPECTED_EXTENSIONS_COUNT) -> None:
    """
    не проверяем, что расширения РАБОТАЮТ - они нужны только "для галочки",
    чтобы сайты видели их в списке установленных, а просто мониторим,
    что их количество совпадает с ожидаемым, т.е. что ни одно расширение не потерялось при сборке/слиминге.
    """
    page = context.new_page()
    try:
        # даём время фоновым страницам/service worker'ам расширений подняться
        time.sleep(1.5)
        cdp = context.new_cdp_session(page)
        targets = cdp.send("Target.getTargets")["targetInfos"]
        ext_ids = sorted({
            t["url"].split("chrome-extension://", 1)[1].split("/", 1)[0]
            for t in targets
            if t["url"].startswith("chrome-extension://")
        })
        print(f"обнаружено расширений: {len(ext_ids)} (ожидалось {expected_count})")
        for ext_id in ext_ids:
            print(f"  - {ext_id}")
        assert len(ext_ids) == expected_count, (
            f"количество расширений не совпадает: найдено {len(ext_ids)}, "
            f"ожидалось {expected_count}"
        )
    finally:
        page.close()


def run_yandex_search_scenario(context: BrowserContext, query: str) -> None:
    context.add_cookies(cookies)
    page = context.new_page()
    try:
        page.goto('chrome://extensions/', wait_until='domcontentloaded', timeout=60000)
        page.screenshot(path='extensions.jpeg', full_page=False, type='jpeg', quality=50)

        page.goto(
            f'https://yandex.com/search?text={quote(query.replace(" ", "+"), safe="+")}&lr=84',
            wait_until='domcontentloaded',
            timeout=90000,
        )

        page.add_style_tag(content='''
                .plus-link,
                .plus-link_inactive,
                .plus-link__content,
                .plus-link__icon,
                .plus-link__text,
                .Distribution,
                .DistributionPopup,
                .DistributionInfo,
                [id^="DistributionPopupDesktopSystemNarrow"],
                [data-fast-name="images"],
                [data-fast-name="video-unisearch"]{
                    display: none !important;
                    width: 0px !important;
                    height: 0px !important;
                    position: absolute !important;
                    left: -999999px !important;
                    z-index: -999999 !important;
                }
                ''')
        try:
            footer_link = page.wait_for_selector('.SerpFooter-LinksGroup_type_settings', timeout=20000)
            footer_link.scroll_into_view_if_needed()
            footer_link.click(force=True)
        except Exception as e:
            print(e)
        print(f'итоговый url: "{page.url}"')
        page.screenshot(path='screen.jpeg', full_page=True, type='jpeg', quality=50)

        with open('page.html', 'w+', encoding='utf-8') as f:
            f.write(page.content())
    finally:
        page.close()


def run_capability_smoke_test(context: BrowserContext) -> None:
    media_uris = make_media_data_uris()
    images = make_image_assets()

    context.set_default_timeout(10000)

    run_step("chrome:// внутренние страницы", test_chrome_internal_pages, context)
    run_step("варианты навигации (about/data/file)", test_navigation_variants, context)
    run_step("выполнение JS (evaluate/expose/wait_for_function)", test_js_execution, context)
    run_step("скриншоты (png/jpeg/clip/full_page)", test_screenshots, context)
    run_step("генерация PDF", test_pdf_generation, context)
    run_step("декодеры изображений (png/jpeg/gif/webp/bmp/ico/svg)", test_image_decoders, context, images)
    run_step("воспроизведение видео/аудио (h264/vp9/aac/opus/mp3)", test_media_playback, context, media_uris)
    run_step("canvas 2d + WebGL", test_canvas_and_webgl, context)
    run_step("localStorage/sessionStorage/IndexedDB", test_storage_apis, context)
    run_step("clipboard/geolocation/notifications", test_permissions_apis, context)
    run_step("скачивание и загрузка файлов", test_downloads_and_uploads, context)
    run_step("JS-диалоги (alert/confirm)", test_dialogs, context)
    run_step("попапы и iframe", test_iframes_and_popups, context)
    run_step("перехват сетевых запросов", test_network_interception, context)
    run_step("CDP: MHTML-снапшот страницы", test_cdp_mhtml_snapshot, context)
    run_step("шрифты и письменности (кириллица/арабский/CJK/эмодзи)", test_fonts_and_scripts, context)
    run_step("количество загруженных расширений", test_extensions_loaded, context)

    context.set_default_timeout(90000)


def wait_for_cdp_server(url: str, timeout: int = 30) -> None:
    """ждет, пока CDP-сервер начнет отвечать по HTTP."""
    print(f"Ожидание готовности CDP-сервера по адресу {url}...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = httpx.get(f"{url}/json/version", timeout=2.0)
            if response.status_code == 200:
                print("CDP сервер успешно запущен и готов к работе!")
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f"Сервер CDP на {url} не ответил за {timeout} секунд.")


def main(query: str, seed: str) -> None:
    wait_for_cdp_server(CDP_URL, timeout=30)

    params = urlencode(dict(fingerprint=seed, geoip='true'), safe=':/@-_')
    endpoint = f'{CDP_URL.rstrip("/")}?{params}'

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(endpoint)
        context = browser.contexts[0]

        run_capability_smoke_test(context)
        run_yandex_search_scenario(context, query)

        context.close()
        browser.close()


if __name__ == "__main__":
    try:
        main('bufo bufo care', 'yandex_search')
    except Exception as e:
        print(f"[FATAL] сценарий упал с необработанной ошибкой: {e!r}")
        import traceback
        traceback.print_exc()
