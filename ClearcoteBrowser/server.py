import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx


def find_clearcote_binary() -> str:
    # 1. Поиск в кэше clearcote
    cache_dirs = [
        Path("/root/.cache/clearcote"),
        Path(os.path.expanduser("~/.cache/clearcote")),
        Path("/opt/xdg-cache/clearcote"),
        Path(os.path.expanduser("~/.clearcote")),
    ]
    for cdir in cache_dirs:
        if cdir.exists():
            for p in cdir.rglob("chrome"):
                if p.is_file():
                    os.chmod(p, 0o755)
                    return str(p)

    # 2. Через SDK
    try:
        import clearcote

        if hasattr(clearcote, "executable_path"):
            p = clearcote.executable_path()
            if p and Path(p).is_file():
                os.chmod(p, 0o755)
                return str(p)
    except Exception as e:
        print(f"[WARN] clearcote.executable_path() error: {e}", flush=True)

    # 3. Поиск в системном PATH
    bin_path = shutil.which("clearcote") or shutil.which("chrome") or shutil.which("chromium")
    if bin_path:
        return bin_path

    raise FileNotFoundError("Бинарник Clearcote Chromium не найден в контейнере.")


def main() -> None:
    chrome_bin = find_clearcote_binary()
    print(f"[clearcote] Найден бинарник: {chrome_bin}", flush=True)

    port = int(os.getenv("PORT", "9222"))
    host = os.getenv("HOST", "0.0.0.0")
    fingerprint = os.getenv("CC_FINGERPRINT", "clearcote-seed-123")
    platform = os.getenv("CC_PLATFORM", "windows")
    profile_dir = os.getenv("CC_USER_DATA_DIR", "/tmp/clearcote_user_data")

    Path(profile_dir).mkdir(parents=True, exist_ok=True)

    cmd = [
        chrome_bin,
        f"--remote-debugging-port={port}",
        f"--remote-debugging-address={host}",
        "--remote-allow-origins=*",
        f"--fingerprint={fingerprint}",
        f"--fingerprint-platform={platform}",
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

    brand = os.getenv("CC_BRAND")
    if brand:
        cmd.append(f"--fingerprint-brand={brand}")

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

    print(f"[clearcote] Запуск процесса: {' '.join(cmd)}", flush=True)

    proc = subprocess.Popen(
        cmd,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    def shutdown(signum, frame):
        print("[clearcote] Завершение работы CDP сервера...", flush=True)
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
            print(f"[FATAL] Процесс Chromium аварийно завершился с кодом {proc.returncode}!", flush=True)
            sys.exit(proc.returncode)
        try:
            res = httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=1.0)
            if res.status_code == 200:
                cdp_ready = True
                print(f"[clearcote] CDP готов (ответил {res.json().get('Browser', 'OK')})", flush=True)
                break
        except Exception:
            pass
        time.sleep(0.5)

    if cdp_ready:
        print(f"\n==================================\nClearcote CDP сервер успешно запущен на {host}:{port}\n==================================\n", flush=True)
    else:
        print("[WARN] CDP сервер не ответил за 20 секунд, но процесс продолжает работать.", flush=True)

    ret = proc.wait()
    sys.exit(ret)


if __name__ == "__main__":
    main()