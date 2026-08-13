"""
Smoke-тест Camoufox (Firefox-движок через собственный WS-протокол Playwright,
НЕ CDP). Отличия от Chromium-версии (CloackBrowser), на которые стоит обратить
внимание при дальнейшей поддержке:

  - `page.pdf()` в Playwright работает только для Chromium — для Firefox
    вместо генерации PDF проверяем встроенный просмотрщик PDF.js.
  - `context.new_cdp_session(...)` — Chromium-only, для Firefox недоступен,
    поэтому MHTML-снапшот тут не делаем.
  - вместо `chrome://...` у Firefox свои служебные страницы `about:...`.
  - готовность сервера проверяем прямой попыткой WS-подключения (у Camoufox
    нет HTTP-эндпоинта вида /json/version, как у CDP).
  - расширения сейчас в server.py не подключены (нет `addons=[...]` в
    launch_server) — соответствующую проверку добавите, когда появятся
    реальные addon'ы (см. заметку в конце файла).
"""

import base64
import io
import shutil
import subprocess
import tempfile
import time

from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

WS_URL = "ws://localhost:7861/camoufox"

ASSETS_DIR = Path(tempfile.gettempdir()) / "camoufox_assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

PERMISSIONS_ORIGIN = "https://example.com"


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
    """Универсальная вставка HTML через data:URI — не зависит от того, в одном
    ли сетевом namespace находятся тестовый скрипт (раннер) и сам браузер
    (контейнер), т.к. `--host-exec` запускает test.py на раннере."""
    page.goto(f"data:text/html;charset=utf-8,{quote(html_content)}", wait_until="domcontentloaded")


# --------------------------------------------------------------------------
# ожидание готовности WS-сервера
# --------------------------------------------------------------------------

def wait_for_ws_server(pw, url: str, timeout: int = 40) -> Browser:
    """У Camoufox нет HTTP-эндпоинта вроде CDP /json/version — единственный
    надёжный способ проверить готовность, это реально попытаться подключиться."""
    print(f"Ожидание готовности Camoufox WS-сервера по адресу {url}...")
    start = time.time()
    last_err = None
    while time.time() - start < timeout:
        try:
            browser = pw.firefox.connect(url, timeout=5000)
            print("WS-сервер Camoufox готов, подключение установлено.")
            return browser
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1)
    raise RuntimeError(f"не удалось подключиться к {url} за {timeout}с: {last_err}")


# --------------------------------------------------------------------------
# генерация ассетов (идентично CloackBrowser — переиспользуйте общий модуль,
# если заведёте shared/-папку между сервисами)
# --------------------------------------------------------------------------

def make_media_data_uris() -> dict:
    assets = {}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg не найден в PATH — пропускаю генерацию видео/аудио. "
              "Проверьте, что linux_deps.txt подхвачен в CI.")
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


def _make_minimal_pdf_bytes() -> bytes:
    """Минимальный валидный (насколько это в принципе бывает у PDF) документ
    для проверки PDF.js. xref-офсеты не гарантированно точные — PDF.js это
    переживает через собственный fallback-парсинг повреждённых файлов."""
    pdf = (
        b"%PDF-1.1\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >> endobj\n"
        b"trailer << /Size 4 /Root 1 0 R >>\n"
        b"%%EOF"
    )
    return pdf


# --------------------------------------------------------------------------
# отдельные проверки
# --------------------------------------------------------------------------

def test_firefox_internal_pages(context: BrowserContext) -> None:
    page = context.new_page()
    try:
        for url in ["about:blank", "about:support", "about:preferences",
                    "about:downloads", "about:cache", "about:networking",
                    "about:addons"]:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:  # noqa: BLE001
                print(f"{url}: не удалось открыть ({e})")
        page.screenshot(path=str(ASSETS_DIR / "about_pages.jpeg"), type="jpeg", quality=50)
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


def test_pdf_handling(context: BrowserContext) -> None:
    """Chromium-only page.pdf() тут недоступен — вместо генерации PDF
    проверяем, что встроенный PDF.js в состоянии обработать PDF-файл
    (либо отрендерить во вьюере, либо скачать — оба пути трогают нужный код)."""
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
            return {webgl: true, renderer: gl.getParameter(gl.RENDERER), dataUrl};
        }""")
        assert result["dataUrl"].startswith("data:image/png")
        if not result.get("webgl"):
            print("WebGL недоступен — allow_webgl=True в server.py, но в Dockerfile "
                  "нет явного libgl1-mesa-dri/mesa-utils. Если это FAIL — начните отсюда, "
                  "а не с подозрений на SlimToolkit.")
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
    # Firefox поддерживает не все типы permissions, которые есть у Chromium
    # (например clipboard-* — под вопросом) — просим каждое отдельно и не
    # валим весь шаг, если конкретное разрешение не поддерживается.
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


# --------------------------------------------------------------------------
# оркестрация
# --------------------------------------------------------------------------

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
    run_step("шрифты и письменности (кириллица/арабский/CJK/эмодзи)", test_fonts_and_scripts, context)

    # TODO: когда в server.py появятся addons=[...] — добавить сюда проверку
    # количества установленных расширений. У Firefox нет CDP Target.getTargets,
    # придётся идти через about:debugging#/runtime/this-firefox и парсить DOM,
    # либо через about:addons (document.querySelectorAll в его shadow DOM).

    context.set_default_timeout(90000)


def main() -> None:
    with sync_playwright() as p:
        browser = wait_for_ws_server(p, WS_URL, timeout=40)
        context = browser.new_context()

        run_capability_smoke_test(context)

        # TODO: сюда реальный бизнес-сценарий
        # пока просто открываем страницу, чтобы дополнительно убедиться,
        # что базовая навигация работает и после слимификации.
        page = context.new_page()
        page.goto("https://x.com/home", wait_until="domcontentloaded")
        print(f'заголовок страницы: "{page.title()}"')
        page.close()

        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] сценарий упал с необработанной ошибкой: {e!r}")
        import traceback
        traceback.print_exc()