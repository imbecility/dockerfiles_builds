import base64
import sys
import time
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from shared.assets import ASSETS_DIR, _make_minimal_pdf_bytes, make_media_data_uris, make_image_assets
from shared.utils import set_html, run_step, wait_for_ws_server

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

WS_URL = "ws://localhost:7861/camoufox"

PERMISSIONS_ORIGIN = "https://example.com"


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


def test_pdf_handling(context: BrowserContext) -> None:
    b64 = base64.b64encode(_make_minimal_pdf_bytes()).decode()
    data_uri = f"data:application/pdf;base64,{b64}"

    page = context.new_page()
    try:
        downloaded = {"flag": False}
        page.on("download", lambda d: downloaded.update(flag=True))
        try:
            page.goto(data_uri, timeout=10000)
        except Exception:
            pass
        time.sleep(1)

        if downloaded["flag"]:
            print("PDF был скачан вместо показа во вьюере — тоже валидный путь, PDF-код задет.")
            return

        viewer_present = page.evaluate("""() => {
            return !!(document.querySelector('#viewer') ||
                      document.querySelector('embed[type="application/pdf"]') ||
                      document.title.toLowerCase().includes('pdf'));
        }""")
        assert viewer_present, "не удалось подтвердить, что PDF.js обработал файл"
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
            except Exception:
                pass
    finally:
        page.close()


def test_media_playback(context: BrowserContext, media_uris: dict) -> None:
    if not media_uris:
        print("нет тестовых медиафайлов — пропускаю.", flush=True)
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
                        const timer = setTimeout(() => resolve(false), 3000);
                        el.addEventListener('canplaythrough', () => { clearTimeout(timer); resolve(true); }, {once: true});
                        el.addEventListener('error', () => { clearTimeout(timer); resolve(false); }, {once: true});
                        el.load();
                    })""",
                )
            except Exception as e:
                print(f"Медиа {ext} пропущено: {e}", flush=True)
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
            return {webgl: true, renderer: gl.getParameter(gl.RENDERER), dataUrl};
        }""")
        assert result["dataUrl"].startswith("data:image/png")
        if not result.get("webgl"):
            print("WebGL недоступен — allow_webgl=True в server.py, но в Dockerfile "
                  "нет явного libgl1-mesa-dri/mesa-utils. Если это FAIL — начните отсюда, "
                  "а не с подозрений на SlimToolkit.")
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


def run_capability_smoke_test(context: BrowserContext) -> None:
    media_uris = make_media_data_uris()
    images = make_image_assets()
    run_step("варианты навигации (about/data/file)", test_navigation_variants, context)
    run_step("выполнение JS (evaluate/expose/wait_for_function)", test_js_execution, context)
    run_step("скриншоты (png/jpeg/clip/full_page)", test_screenshots, context)
    run_step("обработка PDF (PDF.js)", test_pdf_handling, context)
    run_step("декодеры изображений (png/jpeg/gif/webp/bmp/ico/svg)", test_image_decoders, context, images)
    run_step("воспроизведение видео/аудио (h264/vp9/aac/opus/mp3)", test_media_playback, context, media_uris)
    run_step("canvas 2d + WebGL", test_canvas_and_webgl, context)
    run_step("скачивание и загрузка файлов", test_downloads_and_uploads, context)
    run_step("JS-диалоги (alert/confirm)", test_dialogs, context)
    run_step("перехват сетевых запросов", test_network_interception, context)
    run_step("шрифты и письменности (кириллица/арабский/CJK/эмодзи)", test_fonts_and_scripts, context)


def main() -> None:
    with sync_playwright() as p:
        browser = wait_for_ws_server(p, WS_URL, timeout=40)
        context = browser.new_context()
        context.set_default_timeout(15000)
        run_capability_smoke_test(context)
        context.close()
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] сценарий упал с необработанной ошибкой: {e!r}")
        import traceback

        traceback.print_exc()
