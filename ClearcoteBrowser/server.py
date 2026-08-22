import os
import sys
import time

from clearcote import serve


def main() -> None:
    port = int(os.getenv("CC_INTERNAL_PORT", "9223"))
    fingerprint = os.getenv("CC_FINGERPRINT", "clearcote-seed-123")
    platform = os.getenv("CC_PLATFORM", "linux")
    brand = os.getenv("CC_BRAND", "Chrome")

    print(f"[clearcote] Запуск через официальный SDK (headless) на порту {port}...", flush=True)
    try:
        srv = serve(
            port=port,
            fingerprint=fingerprint,
            platform=platform,
            brand=brand,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        print(f"[clearcote] CDP сервер запущен: {getattr(srv, 'cdp_url', f'http://127.0.0.1:{port}')}", flush=True)
        if hasattr(srv, "wait"):
            srv.wait()
        else:
            while True:
                time.sleep(1)
    except Exception as e:
        print(f"[FATAL] Ошибка запуска Clearcote: {e}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()