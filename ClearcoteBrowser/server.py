#!/usr/bin/env python3
import os
import signal
import subprocess
import sys
import time
import httpx

PORT = int(os.environ.get("PORT", 9222))
INTERNAL_PORT = PORT + 1  # 9223
FINGERPRINT = os.environ.get("FINGERPRINT", "seed-123")
PLATFORM = os.environ.get("PLATFORM", "linux")

procs = []


def cleanup(*_):
    print("[clearcote] Завершение процессов...", flush=True)
    for p in procs:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            pass
    sys.exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)


def main():
    cmd = [
        "clearcote-serve",
        "--port",
        str(INTERNAL_PORT),
        "--fingerprint",
        FINGERPRINT,
        "--platform",
        PLATFORM,
    ]

    print(f"[clearcote] Запуск штатного сервера: {' '.join(cmd)}", flush=True)
    chrome_proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    procs.append(chrome_proc)

    cdp_url = f"http://127.0.0.1:{INTERNAL_PORT}"
    print(f"[clearcote] Ожидание CDP по адресу {cdp_url}...", flush=True)
    ready = False
    deadline = time.monotonic() + 60

    while time.monotonic() < deadline:
        if chrome_proc.poll() is not None:
            print(f"[clearcote] Процесс завершился с кодом {chrome_proc.returncode}", flush=True)
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
        cleanup()

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
            cleanup()
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