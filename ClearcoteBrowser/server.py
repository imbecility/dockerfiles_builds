import os
import signal
import subprocess
import sys
from pathlib import Path

from clearcote import executable_path
from clearcote._fingerprint import fingerprint_args
from clearcote._fonts import linux_font_env
from clearcote._launchopts import web_bluetooth_args

PROFILE_DIR = os.environ.get("CC_PROFILE_DIR", "/tmp/cc-profile")
Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)

_license = os.environ.get("CLEARCOTE_LICENSE_KEY") or None
_version = os.environ.get("CC_VERSION") or None
_kwargs = {}
if _license:
    _kwargs["license_key"] = _license
if _version:
    _kwargs["version"] = _version

try:
    exe = executable_path(**_kwargs)
except TypeError:
    exe = executable_path()

print(f"[clearcote] engine: {exe} ({'licensed' if _license else 'free'})", flush=True)

opts = {
    "fingerprint": os.environ.get("CC_FINGERPRINT", "clearcote-seed-123"),
    "platform": os.environ.get("CC_PLATFORM", "windows"),
}
_ENV_TO_OPT = {
    "CC_BRAND": "brand",
    "CC_BRAND_VERSION": "brand_version",
    "CC_ACCEPT_LANGUAGE": "accept_language",
    "CC_TIMEZONE": "timezone",
    "CC_HARDWARE_CONCURRENCY": "hardware_concurrency",
    "CC_GPU_VENDOR": "gpu_vendor",
    "CC_GPU_RENDERER": "gpu_renderer",
    "CC_TLS_PROFILE": "tls_profile",
    "CC_STORAGE_QUOTA": "storage_quota",
}
for env_key, opt_key in _ENV_TO_OPT.items():
    val = os.environ.get(env_key)
    if val:
        opts[opt_key] = val

try:
    args = fingerprint_args(opts)
except Exception:
    args = [f"--fingerprint={opts['fingerprint']}", f"--fingerprint-platform={opts['platform']}"]

port = os.environ.get("PORT", os.environ.get("CC_PORT", "9222"))
internal = os.environ.get("CC_INTERNAL_PORT", "9223")
extra = os.environ.get("CC_EXTRA_ARGS", "").split()

# Запуск socat прокси: 0.0.0.0:$port -> 127.0.0.1:$internal
socat_proc = subprocess.Popen(
    ["socat", f"TCP-LISTEN:{port},fork,reuseaddr,bind=0.0.0.0", f"TCP:127.0.0.1:{internal}"]
)

headless = os.environ.get("CC_HEADLESS", "").strip().lower() in ("1", "true", "yes")
mode_args = []
if headless:
    mode_args = ["--headless=new"]
    print("[clearcote] display: pure headless (CC_HEADLESS set)", flush=True)
else:
    print(f"[clearcote] display: headful on DISPLAY={os.environ.get('DISPLAY', ':99')}", flush=True)

wb_args = []
try:
    wb_args = web_bluetooth_args()
except Exception:
    pass

cmd = [
    exe,
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-vulkan",
    "--no-first-run",
    "--no-default-browser-check",
    "--password-store=basic",
    "--window-size=1920,1080",
    "--start-maximized",
    f"--remote-debugging-port={internal}",
    "--remote-allow-origins=*",
    f"--user-data-dir={PROFILE_DIR}",
] + mode_args + args + wb_args + extra

env = dict(os.environ)
try:
    env.update(linux_font_env(exe))
except Exception:
    pass

print(f"[clearcote] CDP endpoint on 0.0.0.0:{port} (proxy -> chrome 127.0.0.1:{internal}) | persona={opts}", flush=True)

# Запускаем Chrome как дочерний процесс, сохраняя Python в качестве PID 1
chrome_proc = subprocess.Popen(cmd, env=env)


def shutdown(signum, frame):
    print("[clearcote] Остановка процессов...", flush=True)
    try:
        chrome_proc.terminate()
        socat_proc.terminate()
        chrome_proc.wait(timeout=5)
    except Exception:
        chrome_proc.kill()
        socat_proc.kill()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

try:
    exit_code = chrome_proc.wait()
    socat_proc.terminate()
    sys.exit(exit_code)
except KeyboardInterrupt:
    shutdown(None, None)