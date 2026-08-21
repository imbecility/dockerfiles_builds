import os
import subprocess
import sys
import time

# ВАЖНО: сервер слушает на INTERNAL_PORT, а не на PORT.
# Наружу (0.0.0.0:$PORT) его пробрасывает socat, запущенный в start.sh —
# сам clearcote.serve() / clearcote-serve умеет биндиться только на 127.0.0.1.
INTERNAL_PORT = int(os.getenv("INTERNAL_PORT", "9223"))
FINGERPRINT = os.getenv("FINGERPRINT", "default-seed")
FINGERPRINT_PLATFORM = os.getenv("FINGERPRINT_PLATFORM", "windows")


def start_via_sdk():
    import clearcote

    kwargs = {"fingerprint": FINGERPRINT, "platform": FINGERPRINT_PLATFORM, "port": INTERNAL_PORT}
    try:
        srv = clearcote.serve(**kwargs)
    except TypeError:
        # SDK этой версии не принимает "port" - убираем и полагаемся на его
        # дефолт. Если так, INTERNAL_PORT в start.sh нужно синхронизировать
        # с тем портом, который SDK реально выберет по умолчанию.
        kwargs.pop("port", None)
        srv = clearcote.serve(**kwargs)
    print(f"[server.py] clearcote CDP запущен: {getattr(srv, 'cdp_url', '?')}", flush=True)
    return srv


def start_via_cli():
    cmd = [
        "clearcote-serve",
        "--port", str(INTERNAL_PORT),
        "--fingerprint", FINGERPRINT,
        "--platform", FINGERPRINT_PLATFORM,
    ]
    print(f"[server.py] запускаем через CLI: {' '.join(cmd)}", flush=True)
    return subprocess.Popen(cmd)


def main() -> None:
    try:
        start_via_sdk()
        while True:
            time.sleep(3600)
    except Exception as e:
        print(f"[server.py] SDK-режим не сработал ({e!r}), пробуем CLI...", flush=True)
        proc = start_via_cli()
        proc.wait()
        sys.exit(proc.returncode or 1)


if __name__ == "__main__":
    main()