import os
import subprocess
import time
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

_wv = os.environ.get("CC_WIDEVINE")
_wv_on = (_wv not in ("0", "false", "no")) if _wv else (opts.get("platform") == "windows")
if _wv_on:
    os.environ.setdefault(
        "CLEARCOTE_WIDEVINE_DIR",
        os.path.join(os.environ.get("XDG_CACHE_HOME", "/opt/xdg-cache"), "clearcote", "WidevineCdm"),
    )
    try:
        from clearcote._widevine import seed_widevine

        seed_widevine(PROFILE_DIR, quiet=True)
        print("[clearcote] widevine CDM seeded", flush=True)
    except Exception as exc:
        print(f"[clearcote] widevine unavailable: {exc!r}", flush=True)

try:
    args = fingerprint_args(opts)
except Exception:
    args = [f"--fingerprint={opts['fingerprint']}", f"--fingerprint-platform={opts['platform']}"]

port = os.environ.get("PORT", os.environ.get("CC_PORT", "9222"))
internal = os.environ.get("CC_INTERNAL_PORT", "9223")
extra = os.environ.get("CC_EXTRA_ARGS", "").split()

# Публикация loopback-only DevTools эндпоинта наружу через socat: 0.0.0.0:$port -> 127.0.0.1:$internal
subprocess.Popen(
    ["socat", f"TCP-LISTEN:{port},fork,reuseaddr,bind=0.0.0.0", f"TCP:127.0.0.1:{internal}"]
)

headless = os.environ.get("CC_HEADLESS", "").strip().lower() in ("1", "true", "yes")
mode_args = []
if headless:
    mode_args = ["--headless=new"]
    print("[clearcote] display: pure headless (CC_HEADLESS set)", flush=True)
else:
    display = os.environ.get("DISPLAY") or ":99"
    if not os.environ.get("DISPLAY"):
        screen = os.environ.get("CC_SCREEN", "1920x1080x24")
        subprocess.Popen(["Xvfb", display, "-screen", "0", screen, "-nolisten", "tcp", "-ac"])
        sock = "/tmp/.X11-unix/X" + display.lstrip(":").split(".")[0]
        for _ in range(100):
            if os.path.exists(sock):
                break
            time.sleep(0.1)
        os.environ["DISPLAY"] = display
    print(f"[clearcote] display: headful on Xvfb {os.environ.get('DISPLAY')}", flush=True)

wb_args = []
try:
    wb_args = web_bluetooth_args()
except Exception:
    pass

cmd = [
    exe,
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    f"--remote-debugging-port={internal}",
    "--remote-allow-origins=*",
    f"--user-data-dir={PROFILE_DIR}",
] + mode_args + args + wb_args + extra

env = dict(os.environ)
try:
    env.update(linux_font_env(exe))
except Exception:
    pass

_sd = os.environ.get("CC_SHADER_DIALECT")
if _sd:
    if _sd not in ("0", "false", "no"):
        env["CLEARCOTE_SHADER_DIALECT"] = _sd
elif opts.get("platform") == "windows":
    env["CLEARCOTE_SHADER_DIALECT"] = "hlsl"

print(f"[clearcote] CDP endpoint on 0.0.0.0:{port} (proxy -> chrome 127.0.0.1:{internal}) | persona={opts}", flush=True)
os.execvpe(cmd[0], cmd, env)