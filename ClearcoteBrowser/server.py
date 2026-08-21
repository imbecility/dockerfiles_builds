import os
import signal
import subprocess
import sys
import tempfile

import clearcote

if __name__ == "__main__":
    port = os.getenv("PORT", "9222")
    fingerprint = os.getenv("CC_FINGERPRINT", "clearcote-seed")
    platform = os.getenv("CC_PLATFORM", "windows")

    try:
        chrome_path = clearcote.download()
    except Exception as e:
        print(f"[FATAL] Ошибка получения бинарника Clearcote: {e}", file=sys.stderr)
        sys.exit(1)

    user_data_dir = os.getenv("USER_DATA_DIR", tempfile.mkdtemp(prefix="clearcote_profile_"))

    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=0.0.0.0",
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
        cmd.append(f"--proxy-server={proxy_url}")

    extra_args = os.getenv("CHROME_EXTRA_ARGS")
    if extra_args:
        cmd.extend(extra_args.split())

    print(f"Запуск Clearcote Chromium на 0.0.0.0:{port}...")
    sys.stdout.flush()

    proc = subprocess.Popen(cmd)

    def handle_sig(signum, frame):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)

    try:
        proc.wait()
    except KeyboardInterrupt:
        handle_sig(None, None)