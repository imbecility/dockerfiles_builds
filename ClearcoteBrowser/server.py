import glob
import os
import signal
import subprocess
import sys
import tempfile


def get_chrome_executable() -> str:
    # 1. Попытка через SDK clearcote
    try:
        import clearcote

        for fn_name in ("executable_path", "download"):
            if hasattr(clearcote, fn_name):
                try:
                    path = getattr(clearcote, fn_name)()
                    if path and os.path.exists(path):
                        return str(path)
                except Exception:
                    pass
    except ImportError:
        pass

    # 2. Поиск по известным путям кэша в образе
    search_patterns = [
        "/root/.clearcote/**/chrome",
        "/root/.cache/clearcote/**/chrome",
        "/app/cache/clearcote/**/chrome",
    ]
    for pattern in search_patterns:
        for match in glob.glob(pattern, recursive=True):
            if os.path.isfile(match) and os.access(match, os.X_OK):
                return match

    raise RuntimeError("Не удалось найти исполняемый файл Chrome для Clearcote")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9222"))
    internal_port = port + 1  # 9223

    fingerprint = os.getenv("CC_FINGERPRINT", "clearcote-seed")
    platform = os.getenv("CC_PLATFORM", "windows")

    chrome_path = get_chrome_executable()
    print(f"Используется бинарник Chrome: {chrome_path}")

    # socat слушает 0.0.0.0:PORT и транслирует в 127.0.0.1:INTERNAL_PORT
    socat_cmd = [
        "socat",
        f"TCP-LISTEN:{port},fork,reuseaddr",
        f"TCP:127.0.0.1:{internal_port}",
    ]
    print(f"Запуск socat: 0.0.0.0:{port} -> 127.0.0.1:{internal_port}")
    socat_proc = subprocess.Popen(socat_cmd)

    user_data_dir = os.getenv("USER_DATA_DIR", tempfile.mkdtemp(prefix="clearcote_profile_"))

    chrome_cmd = [
        chrome_path,
        f"--remote-debugging-port={internal_port}",
        f"--fingerprint={fingerprint}",
        f"--fingerprint-platform={platform}",
        f"--user-data-dir={user_data_dir}",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-vulkan",
        "--window-size=1920,1080",
        "--start-maximized",
        "--headless=false",
        "--no-first-run",
        "--no-default-browser-check",
        "--password-store=basic",
        "--use-mock-keychain",
        "--metrics-recording-only",
        "--disable-background-networking",
        "--disable-breakpad",
        "--disable-component-update",
        "--disable-features=Translate,BackForwardCache,AcceptCHFrame,MediaRouter,OptimizationHints",
    ]

    proxy_url = os.getenv("PROXY_SERVER")
    if proxy_url:
        chrome_cmd.append(f"--proxy-server={proxy_url}")

    extra_args = os.getenv("CHROME_EXTRA_ARGS")
    if extra_args:
        chrome_cmd.extend(extra_args.split())

    print(f"Запуск Clearcote Chromium на внутреннем порту {internal_port}...")
    sys.stdout.flush()

    chrome_proc = subprocess.Popen(chrome_cmd)

    def shutdown(signum, frame):
        for proc in (chrome_proc, socat_proc):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        chrome_proc.wait()
    except KeyboardInterrupt:
        shutdown(None, None)