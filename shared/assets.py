import base64
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

ASSETS_DIR = Path(tempfile.gettempdir()) / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


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
    pdf = (
        b"%PDF-1.1\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >> endobj\n"
        b"trailer << /Size 4 /Root 1 0 R >>\n"
        b"%%EOF"
    )
    return pdf
