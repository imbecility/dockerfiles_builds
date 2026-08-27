"""
Fortress CDP-server launcher:
Запускает Tilion Fortress со встроенной персоной, поддержкой DoH-less DNS sinkhole,
установленными расширениями и публикацией внешнего DevTools/CDP порта через socat.
"""
import os
import subprocess
import time
from pathlib import Path

INTERNAL_PORT = os.environ.get("FORTRESS_INTERNAL_PORT", "9223")
EXTERNAL_PORT = os.environ.get("PORT", "9222")
PROFILE_DIR = os.environ.get("FORTRESS_PROFILE_DIR", "/tmp/tilion-profile")
EXTENSIONS_DIR = os.environ.get("EXTENSIONS_DIR", "/app/extensions")
TILION_BIN = "/opt/tilion/tilion"

# Подготовка конфигурации шрифтов Tilion
cache_dir = Path(os.environ.get("XDG_CACHE_HOME", "/root/.cache")) / "tilion" / "fc"
cache_dir.mkdir(parents=True, exist_ok=True)
fonts_conf = cache_dir.parent / "fonts.conf"

template_path = Path("/opt/tilion/fonts/fonts.conf.template")
if template_path.exists():
    tmpl = template_path.read_text(encoding="utf-8")
    conf_content = tmpl.replace("@FONTDIR@", "/opt/tilion/fonts").replace("@CACHEDIR@", str(cache_dir))
    fonts_conf.write_text(conf_content, encoding="utf-8")
    os.environ["FONTCONFIG_FILE"] = str(fonts_conf)

if Path("/opt/tilion/vk_swiftshader_icd.json").exists():
    os.environ["VK_ICD_FILENAMES"] = "/opt/tilion/vk_swiftshader_icd.json"

os.environ["TZ"] = os.environ.get("TILION_TZ", "America/New_York")

# Загрузка расширений
ext_paths = []
if Path(EXTENSIONS_DIR).exists():
    ext_paths = [str(p) for p in Path(EXTENSIONS_DIR).iterdir() if p.is_dir()]

cmd = [
    TILION_BIN,
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--enable-unsafe-swiftshader",
    f"--remote-debugging-port={INTERNAL_PORT}",
    "--remote-allow-origins=*",
    f"--user-data-dir={PROFILE_DIR}",
]

if ext_paths:
    joined_exts = ",".join(ext_paths)
    cmd.extend([
        f"--load-extension={joined_exts}",
        f"--disable-extensions-except={joined_exts}"
    ])
    print(f"[fortress] Загружено расширений: {len(ext_paths)}", flush=True)

extra_args = os.environ.get("FORTRESS_EXTRA_ARGS", "").split()
cmd.extend(extra_args)

# Запуск socat-моста (0.0.0.0:9222 -> 127.0.0.1:9223)
subprocess.Popen([
    "socat",
    f"TCP-LISTEN:{EXTERNAL_PORT},fork,reuseaddr,bind=0.0.0.0",
    f"TCP:127.0.0.1:{INTERNAL_PORT}"
])

print(f"[fortress] Запуск Chromium CDP сервера на 0.0.0.0:{EXTERNAL_PORT} (внутренний порт {INTERNAL_PORT})...", flush=True)
os.execv(TILION_BIN, cmd)