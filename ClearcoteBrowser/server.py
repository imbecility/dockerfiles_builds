#!/usr/bin/env python3
"""
Clearcote CDP server
  1. Запускает clearcote-serve на 127.0.0.1:INTERNAL_PORT
  2. Ждёт готовности CDP (/json/version → 200)
  3. Поднимает socat-бридж 0.0.0.0:PORT → 127.0.0.1:INTERNAL_PORT
  4. Мониторит оба процесса
"""
import os, sys, time, signal, subprocess
import httpx

PORT          = int(os.environ.get("PORT", 9222))
INTERNAL_PORT = PORT + 1                           # 9223 по умолчанию
FINGERPRINT   = os.environ.get("FINGERPRINT", "seed-123")
PLATFORM      = os.environ.get("PLATFORM", "linux")
CDP_INTERNAL  = f"http://127.0.0.1:{INTERNAL_PORT}"

procs: list[subprocess.Popen] = []


def cleanup(*_):
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    sys.exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

# ── 1. Запускаем clearcote-serve на loopback ──────────────────────────────────
print(
    f"[clearcote] launching on 127.0.0.1:{INTERNAL_PORT}  "
    f"fingerprint={FINGERPRINT!r}  platform={PLATFORM!r}",
    flush=True,
)
srv = subprocess.Popen(
    [
        "clearcote-serve",
        "--port", str(INTERNAL_PORT),
        "--fingerprint", FINGERPRINT,
        "--platform", PLATFORM,
    ],
    stdout=sys.stdout,
    stderr=sys.stderr,
)
procs.append(srv)

# ── 2. Ждём готовности CDP (до 120 с) ────────────────────────────────────────
print(f"[clearcote] waiting for CDP at {CDP_INTERNAL} …", flush=True)
deadline = time.monotonic() + 120
ready = False

while time.monotonic() < deadline:
    if srv.poll() is not None:
        print(f"[clearcote] process exited early (rc={srv.returncode})", flush=True)
        sys.exit(1)
    try:
        r = httpx.get(f"{CDP_INTERNAL}/json/version", timeout=3)
        if r.status_code == 200:
            print(f"[clearcote] CDP ready — {r.json().get('Browser', '?')}", flush=True)
            ready = True
            break
    except Exception:
        pass
    time.sleep(1)

if not ready:
    print("[clearcote] timeout: CDP never became healthy within 120 s", flush=True)
    cleanup()

# ── 3. socat: 0.0.0.0:PORT → 127.0.0.1:INTERNAL_PORT ────────────────────────
# Запускаем ПОСЛЕ того, как backend готов — нет риска ECONNREFUSED на клиенте.
print(
    f"[clearcote] socat bridge  0.0.0.0:{PORT} → 127.0.0.1:{INTERNAL_PORT}",
    flush=True,
)
bridge = subprocess.Popen(
    [
        "socat",
        f"TCP-LISTEN:{PORT},reuseaddr,fork,bind=0.0.0.0",
        f"TCP:127.0.0.1:{INTERNAL_PORT}",
    ],
)
procs.append(bridge)

print(
    f"\n{'='*55}\n"
    f"  Clearcote CDP  →  http://localhost:{PORT}\n"
    f"  Connect:  p.chromium.connect_over_cdp('http://localhost:{PORT}')\n"
    f"{'='*55}\n",
    flush=True,
)

# ── 4. Watchdog loop ──────────────────────────────────────────────────────────
while True:
    if srv.poll() is not None:
        print(f"[clearcote] server exited (rc={srv.returncode}), shutting down", flush=True)
        cleanup()

    # socat с fork самосброситься не должен, но на случай краша — рестарт
    if bridge.poll() is not None:
        print("[clearcote] socat bridge died, restarting …", flush=True)
        procs.remove(bridge)
        bridge = subprocess.Popen(
            [
                "socat",
                f"TCP-LISTEN:{PORT},reuseaddr,fork,bind=0.0.0.0",
                f"TCP:127.0.0.1:{INTERNAL_PORT}",
            ],
        )
        procs.append(bridge)

    time.sleep(5)