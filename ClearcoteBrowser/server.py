import os
import signal
import subprocess
import sys
import time

from clearcote import serve

if __name__ == "__main__":
    port = int(os.getenv("PORT", "9222"))
    internal_port = port + 1  # 9223

    fingerprint = os.getenv("CC_FINGERPRINT", "clearcote-seed")
    platform = os.getenv("CC_PLATFORM", "windows")

    # 1. Проброс внешнего интерфейса 0.0.0.0:PORT -> локальный 127.0.0.1:INTERNAL_PORT
    socat_cmd = [
        "socat",
        f"TCP-LISTEN:{port},fork,reuseaddr",
        f"TCP:127.0.0.1:{internal_port}",
    ]
    print(f"Запуск socat: 0.0.0.0:{port} -> 127.0.0.1:{internal_port}")
    socat_proc = subprocess.Popen(socat_cmd)

    # 2. Запуск официального CDP-сервера через clearcote SDK
    print(f"Запуск clearcote.serve на порту {internal_port} (платформа: {platform})...")
    sys.stdout.flush()

    srv = serve(
        port=internal_port,
        fingerprint=fingerprint,
        platform=platform,
    )
    print(f"Clearcote CDP успешно запущен: {srv.cdp_url}")
    sys.stdout.flush()

    def shutdown(signum, frame):
        try:
            srv.close()
        except Exception:
            pass
        if socat_proc.poll() is None:
            socat_proc.terminate()
            try:
                socat_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                socat_proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)