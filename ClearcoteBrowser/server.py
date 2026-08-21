#!/usr/bin/env python3
import os
import shutil
import signal
import subprocess
import sys
import time
import httpx

PORT = int(os.environ.get("PORT", 9222))
INTERNAL_PORT = PORT + 1  # 9223
FINGERPRINT = os.environ.get("FINGERPRINT", "seed-123")
PLATFORM = os.environ.get("PLATFORM", "linux")


def find_chrome_binary() -> str:
    search_dirs = [
        os.environ.get("CLEARCOTE_CACHE_DIR", ""),
        os.environ.get("XDG_CACHE_HOME", ""),
        "/root/.cache",
        "/root/.clearcote",
        "/app/cache",
        os.path.expanduser("~/.cache"),
    ]
    for d in search_dirs:
        if not d or not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            if "chrome" in files:
                full_path = os.path.join(root, "chrome")
                if os.access(full_path, os.X_OK):
                    return full_path
    raise FileNotFoundError("Бинарник chrome от Clearcote не найден в кэше!")


def cleanup(procs):
    print("[clearcote] Завершение процессов...", flush=True)
    for p in procs:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            pass
    sys.exit(0)


def main():
    print("[clearcote] Поиск бинарника chrome...", flush=True)
    chrome_bin = find_chrome_binary()
    print(f"[clearcote] Найден chrome: {chrome_bin}", flush=True)

    profile_dir = "/tmp/clearcote_profile"
    shutil.rmtree(profile_dir, ignore_errors=True)
    os.makedirs(profile_dir, exist_ok=True)

    cmd = [
        chrome_bin,
        f"--remote-debugging-port={INTERNAL_PORT}",
        "--remote-debugging-address=127.0.0.1",
        "--remote-allow-origins=*",
        f"--fingerprint={FINGERPRINT}",
        f"--fingerprint-platform={PLATFORM}",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
    ]

    print(f"[clearcote] Запуск Chrome напрямую на 127.0.0.1:{INTERNAL_PORT}...", flush=True)
    chrome_proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    procs = [chrome_proc]

    signal.signal(signal.SIGTERM, lambda *_: cleanup(procs))
    signal.signal(signal.SIGINT, lambda *_: cleanup(procs))

    cdp_url = f"http://127.0.0.1:{INTERNAL_PORT}"
    print(f"[clearcote] Ожидание CDP по адресу {cdp_url}...", flush=True)
    ready = False
    deadline = time.monotonic() + 60

    while time.monotonic() < deadline:
        if chrome_proc.poll() is not None:
            print(f"[clearcote] Chrome завершился раньше времени с кодом {chrome_proc.returncode}", flush=True)
            sys.exit(1)
        try:
            r = httpx.get(f"{cdp_url}/json/version", timeout=2)
            if r.status_code == 200:
                ready = True
                print(f"[clearcote] CDP готов! Имя сервера: {r.json().get('Browser')}", flush=True)
                break
        except Exception:
            pass
        time.sleep(1)

    if not ready:
        print("[clearcote] CDP не ответил за 60 секунд!", flush=True)
        cleanup(procs)

    print(f"[clearcote] Запуск socat 0.0.0.0:{PORT} -> 127.0.0.1:{INTERNAL_PORT}...", flush=True)
    socat_proc = subprocess.Popen([
        "socat",
        f"TCP-LISTEN:{PORT},reuseaddr,fork,bind=0.0.0.0",
        f"TCP:127.0.0.1:{INTERNAL_PORT}",
    ])
    procs.append(socat_proc)

    print(
        f"\n==================================================\n"
        f"Clearcote CDP сервер доступен на http://0.0.0.0:{PORT}\n"
        f"==================================================\n",
        flush=True,
    )

    while True:
        if chrome_proc.poll() is not None:
            print(f"[clearcote] Chrome завершился (код {chrome_proc.returncode}), выходим...", flush=True)
            cleanup(procs)
        if socat_proc.poll() is not None:
            print("[clearcote] socat упал, перезапуск...", flush=True)
            procs.remove(socat_proc)
            socat_proc = subprocess.Popen([
                "socat",
                f"TCP-LISTEN:{PORT},reuseaddr,fork,bind=0.0.0.0",
                f"TCP:127.0.0.1:{INTERNAL_PORT}",
            ])
            procs.append(socat_proc)
        time.sleep(2)


if __name__ == "__main__":
    main()