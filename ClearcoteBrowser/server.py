import os
import signal
import sys
import time

from clearcote import serve

if __name__ == "__main__":
    port = int(os.getenv("PORT", "9222"))
    host = os.getenv("HOST", "0.0.0.0")
    fingerprint = os.getenv("CC_FINGERPRINT", "clearcote-seed-123")
    platform = os.getenv("CC_PLATFORM", "windows")
    brand = os.getenv("CC_BRAND", "Chrome")

    server_kwargs = {
        "port": port,
        "host": host,
        "fingerprint": fingerprint,
        "platform": platform,
        "brand": brand,
        "headless": False,
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-vulkan",
            "--window-size=1920,1080",
            "--start-maximized",
        ],
    }

    proxy_server = os.getenv("PROXY_SERVER")
    if proxy_server:
        server_kwargs["proxy"] = {
            "server": proxy_server,
            "username": os.getenv("PROXY_USER", ""),
            "password": os.getenv("PROXY_PASS", ""),
        }

    print(f"Starting Clearcote CDP server on {host}:{port} (platform={platform}, brand={brand})...", flush=True)
    srv = serve(**server_kwargs)
    cdp_url = getattr(srv, "cdp_url", f"http://{host}:{port}")
    print(f"Clearcote CDP server listening at {cdp_url}", flush=True)

    def shutdown(signum, frame):
        print("Shutting down Clearcote CDP server...", flush=True)
        if hasattr(srv, "close"):
            try:
                srv.close()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        if hasattr(srv, "wait"):
            srv.wait()
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)