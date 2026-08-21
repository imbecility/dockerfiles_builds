import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx


def find_clearcote_binary() -> str:
    # 1. Через SDK clearcote
    try:
        import clearcote

        if hasattr(clearcote, "executable_path"):
            path = clearcote.executable_path()
            if path and Path(path).is_file():
                return str(path)
    except Exception as e:
        print(f"[WARN] clearcote.executable_path() выбросил исключение: {e}", flush=True)

    # 2. Поиск в кэше
    search_roots = [
        Path(os.path.expanduser("~/.cache/clearcote")),
        Path("/root/.cache/clearcote"),
        Path("/opt/xdg-cache/clearcote"),
        Path(os.path.expanduser("~/.clearcote")),
    ]
    for root in search_roots:
        if root.exists():
            for p in root.rglob("chrome"):
                if p.is_file() and os.access(p, os.X_OK):
                    return str(p)

    # 3. Поиск в системном PATH
    which_chrome = shutil.which("clearcote") or shutil.which("chrome")
    if which_chrome:
        return which_chrome

    raise FileNotFoundError("Бинарник Clearcote Chromium не найден в контейнере.")


def main() -> None:
    chrome_bin = find_clearcote_binary()
    print(f"Найден бинарник Clearcote: {chrome_bin}", flush=True)

    port = int(os.getenv("PORT", "9222"))
    host = os.getenv("HOST", "0.0.0.0")
    fingerprint = os.getenv("CC_FINGERPRINT", "clearcote-seed-123")
    platform = os.getenv("CC_PLATFORM", "windows")
    brand = os.getenv("CC_BRAND", "Chrome")
    profile_dir = os.getenv("CC_USER_DATA_DIR", "/tmp/clearcote_user_data")

    cmd = [
        chrome_bin,
        f"--remote-debugging-port={port}",
        f"--remote-debugging-address={host}",
        f"--fingerprint={fingerprint}",
        f"--fingerprint-platform={platform}",
        f"--fingerprint-brand={brand}",
        f"--user-data-dir={profile_dir}",
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
    ]

    tz = os.getenv("CC_TIMEZONE")
    if tz:
        cmd.append(f"--timezone={tz}")

    lang = os.getenv("CC_ACCEPT_LANGUAGE")
    if lang:
        cmd.append(f"--lang={lang}")

    proxy_server = os.getenv("PROXY_SERVER")
    if proxy_server:
        cmd.append(f"--proxy-server={proxy_server}")

    cmd.append("about:blank")
    print(f"Запуск Clearcote: {' '.join(cmd)}", flush=True)

    proc = subprocess.Popen(cmd)

    def shutdown(signum, frame):
        print("Остановка Clearcote сервера...", flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Проверка готовности CDP внутри контейнера
    cdp_ready = False
    for _ in range(40):
        if proc.poll() is not None:
            print(f"[FATAL] Процесс Clearcote завершился с кодом ошибки {proc.returncode}!", flush=True)
            sys.exit(proc.returncode)
        try:
            res = httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=1.0)
            if res.status_code == 200:
                cdp_ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if cdp_ready:
        print(f"\n==================================\nClearcote CDP сервер готов и слушает на {host}:{port}\n==================================\n", flush=True)
    else:
        print("[WARN] CDP сервер не ответил на 127.0.0.1 за 20 секунд, но процесс продолжает работать.", flush=True)

    ret = proc.wait()
    sys.exit(ret)


if __name__ == "__main__":
    main()