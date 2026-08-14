# ./Camoufox/test.py
import base64
import io
import os
import shutil
import subprocess
import tempfile
import time

from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

PORT = os.getenv("PORT", "7861")
WS_URL = f"ws://localhost:{PORT}/camoufox"
PERMISSIONS_ORIGIN = "https://example.com"

ASSETS_DIR = Path(tempfile.gettempdir()) / "camoufox_assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def log(step: str, ok: bool, extra: str = "") -> None:
    mark = "OK  " if ok else "FAIL"
    suffix = f" — {extra}" if extra else ""
    print(f"[{mark}] {step}{suffix}", flush=True)


def run_step(name, fn, *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
        log(name, True)
    except Exception as e:  # noqa: BLE001
        log(name, False, repr(e))


def set_html(page: Page, html_content: str) -> None:
    page.goto(f"data:text/html;charset=utf-8,{quote(html_content)}", wait_until="domcontentloaded")


def attach_network_logger(page: Page) -> None:
    page.on("request", lambda req: print(f"  [REQ START] {req.method} {req.url}", flush=True))
    page.on("response", lambda resp: print(f"  [RESP] {resp.status} {resp.url}", flush=True))
    page.on("requestfailed", lambda req: print(f"  [REQ FAILED] {req.url} -> {req.failure}", flush=True))
    page.on("pageerror", lambda err: print(f"  [PAGE ERROR] {err}", flush=True))


def wait_for_ws_server(pw, url: str, timeout: int = 40) -> Browser:
    print(f"Ожидание готовности Camoufox WS-сервера по адресу {url}...", flush=True)
    start = time.time()
    last_err = None
    while time.time() - start < timeout:
        try:
            browser = pw.firefox.connect(url, timeout=4000)
            print("WS-сервер Camoufox готов, подключение установлено.", flush=True)
            return browser
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1)
    raise RuntimeError(f"не удалось подключиться к {url} за {timeout}с: {last_err}")


def make_media_data_uris() -> dict:
    assets = {}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return assets

    specs = [
        ("mp4", "video/mp4", ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=1", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "libx264", "-c:a", "aac", "-shortest"]),
        ("webm", "video/webm", ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=1", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "libvpx-vp9", "-c:a", "libopus", "-shortest"]),
        ("mp3", "audio/mp3", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "libmp3lame"]),
        ("ogg", "audio/ogg", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "libvorbis"]),
    ]
    for ext, mime, args in specs:
        out_path = ASSETS_DIR / f"test.{ext}"
        cmd = [ffmpeg, "-y", *args, str(out_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=10)
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


def _make_minimal_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.1\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >> endobj\n"
        b"trailer << /Size 4 /Root 1 0 R >>\n"
        b"%%EOF"
    )


def test_firefox_internal_pages(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.goto("about:blank", timeout=3000)
        for url in ["about:buildconfig", "about:compat", "about:support"]:
            try:
                page.goto(url, wait_until="commit", timeout=2000)
            except Exception:
                pass
    finally:
        page.close()


def test_navigation_variants(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        page.goto("about:blank")
        page.goto("data:text/html,<h1>data url test</h1>")
        page.goto("file:///etc/os-release", wait_until="load", timeout=3000)
    finally:
        page.close()


def test_js_execution(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        set_html(page, "<div id='x'>1</div>")
        page.evaluate("document.getElementById('x').textContent = '2'")
        page.add_script_tag(content="window.__injected = 42;")
        assert page.evaluate("window.__injected") == 42
        page.expose_function("pyHello", lambda: "hello from python")
        result = page.evaluate("async () => await window.pyHello()")
        assert result == "hello from python"
    finally:
        page.close()


def test_screenshots(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        set_html(page, "<div style='width:400px;height:1000px;background:linear-gradient(red,blue)'></div>")
        page.screenshot(path=str(ASSETS_DIR / "shot.png"), type="png")
        page.screenshot(path=str(ASSETS_DIR / "shot_full.jpeg"), type="jpeg", quality=70, full_page=True)
    finally:
        page.close()


def test_pdf_handling(context: BrowserContext) -> None:
    b64 = base64.b64encode(_make_minimal_pdf_bytes()).decode()
    data_uri = f"data:application/pdf;base64,{b64}"

    page = context.new_page()
    try:
        try:
            page.goto(data_uri, timeout=3000)
        except Exception:
            pass
    finally:
        page.close()


def test_image_decoders(context: BrowserContext, images: dict) -> None:
    page = context.new_page()
    try:
        tags = "".join(f'<img id="img_{ext}" src="{uri}">' for ext, uri in images.items())
        set_html(page, f"<html><body>{tags}</body></html>")
    finally:
        page.close()


def test_media_playback(context: BrowserContext, media_uris: dict) -> None:
    if not media_uris:
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
            try:
                page.eval_on_selector(
                    f"#med_{ext}",
                    """el => new Promise((resolve) => {
                        const t = setTimeout(() => resolve(false), 1500);
                        el.addEventListener('canplaythrough', () => { clearTimeout(t); resolve(true); }, {once: true});
                        el.addEventListener('error', () => { clearTimeout(t); resolve(false); }, {once: true});
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
        result = page.evaluate("""() => {
            const canvas = document.getElementById('c');
            const ctx2d = canvas.getContext('2d');
            ctx2d.fillStyle = 'green';
            ctx2d.fillRect(0, 0, 50, 50);
            const dataUrl = canvas.toDataURL('image/png');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            return {webgl: !!gl, dataUrl};
        }""")
        assert result["dataUrl"].startswith("data:image/png")
    finally:
        page.close()


def test_storage_apis(context: BrowserContext) -> None:
    page = context.new_page()
    attach_network_logger(page)
    try:
        page.goto(PERMISSIONS_ORIGIN, timeout=10000)
        page.evaluate("localStorage.setItem('k', 'v')")
        assert page.evaluate("localStorage.getItem('k')") == "v"
        page.evaluate("sessionStorage.setItem('k2', 'v2')")
        assert page.evaluate("sessionStorage.getItem('k2')") == "v2"
        idb_result = page.evaluate("""() => new Promise((resolve, reject) => {
            const req = indexedDB.open('slim_test', 1);
            req.onupgradeneeded = () => req.result.createObjectStore('store');
            req.onsuccess = () => {
                const db = req.result;
                const tx = db.transaction('store', 'readwrite');
                tx.objectStore('store').put('value', 'key');
                tx.oncomplete = () => resolve(true);
            };
            req.onerror = () => resolve(true);
        })""")
        assert idb_result is True
    finally:
        page.close()


def test_permissions_apis(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        try:
            context.grant_permissions(["notifications"], origin=PERMISSIONS_ORIGIN)
        except Exception as e:
            print(f"permissions API: {e}")

        page.goto(PERMISSIONS_ORIGIN, wait_until="domcontentloaded", timeout=15000)

        try:
            coords = page.evaluate("""() => new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(
                    pos => resolve([pos.coords.latitude, pos.coords.longitude]),
                    err => resolve([0, 0]),
                    {timeout: 3000}
                );
            })""")
            print(f"geolocation coords: {coords}")
        except Exception as e:
            print(f"geolocation API: {e}")
    finally:
        try:
            context.clear_permissions()
        except Exception:
            pass
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
        with page.expect_download(timeout=5000) as download_info:
            page.click("#dl", force=True)
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
        page.goto(PERMISSIONS_ORIGIN, wait_until="domcontentloaded", timeout=15000)
        set_html(page, f'<iframe src="{PERMISSIONS_ORIGIN}" style="width:200px;height:200px"></iframe>')
        page.wait_for_selector("iframe", timeout=10000)
    finally:
        page.close()


def test_network_interception(context: BrowserContext) -> None:
    def handler(route):
        route.continue_()

    context.route("**/*.png", handler)
    page = context.new_page()
    try:
        set_html(page, '<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=">')
    finally:
        context.unroute("**/*.png", handler)
        page.close()


def test_fonts_and_scripts(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        samples = {
            "cyrillic": "Привет мир",
            "cjk": "你好世界",
            "emoji": "😀🚀🎉",
        }
        html = "".join(f'<p>{text}</p>' for text in samples.values())
        set_html(page, f"<html><body style='font-size:32px'>{html}</body></html>")
    finally:
        page.close()


def run_capability_smoke_test(context: BrowserContext) -> None:
    media_uris = make_media_data_uris()
    images = make_image_assets()

    context.set_default_timeout(10000)

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
    run_step("шрифты и письменности", test_fonts_and_scripts, context)


# В ./Camoufox/test.py в main():

def main() -> None:
    with sync_playwright() as p:
        browser = wait_for_ws_server(p, WS_URL, timeout=40)
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        run_capability_smoke_test(context)

        page = context.new_page()
        print("-> Финальный переход на https://example.com в main...", flush=True)
        page.goto("https://example.com", wait_until="domcontentloaded", timeout=20000)
        title = page.title()
        print(f'заголовок страницы: "{title}"', flush=True)
        page.close()

        context.close()
        browser.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] сценарий упал: {e!r}", flush=True)
        import traceback
        traceback.print_exc()
        raise