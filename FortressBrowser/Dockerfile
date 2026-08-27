# ./FortressBrowser/Dockerfile
ARG BASE_IMAGE=base:latest
FROM ${BASE_IMAGE}

ENV PORT=9222 \
    FORTRESS_INTERNAL_PORT=9223 \
    XDG_CACHE_HOME=/root/.cache

WORKDIR /app

# Устанавливаем системные зависимости для работы headed Chromium
RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
      binutils socat unzip tzdata \
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
      libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
      libvulkan1 mesa-vulkan-drivers fontconfig ca-certificates \
      libx11-6 libx11-xcb1 libxcb1 libxext6 libxrender1 libxi6 libxtst6 \
      libexpat1 libdbus-1-3 libgtk-3-0 libatspi2.0-0 libgdk-pixbuf-2.0-0 >/dev/null && \
    pip install --no-cache-dir tilion-fortress >/dev/null && \
    mkdir -p /opt/tilion && \
    curl -sSL "https://github.com/tiliondev/fortress/releases/latest/download/tilion-fortress-linux-x64.tar.gz" -o /tmp/fortress.tar.gz && \
    tar -xzf /tmp/fortress.tar.gz -C /opt/tilion --strip-components=1 && \
    rm -f /tmp/fortress.tar.gz && \
    strip --strip-unneeded /opt/tilion/chrome 2>/dev/null || true && \
    strip --strip-unneeded /opt/tilion/chrome_crashpad_handler 2>/dev/null || true && \
    for so in /opt/tilion/*.so /opt/tilion/*.so.1; do strip --strip-unneeded "$so" 2>/dev/null || true; done && \
    find /opt/tilion/locales -type f -name '*.pak' ! -name 'en-US.pak' ! -name 'ru.pak' -delete 2>/dev/null || true && \
    chmod +x /opt/tilion/tilion /opt/tilion/chrome 2>/dev/null || true && \
    /app/chrome-extensions.sh && rm /app/chrome-extensions.sh && \
    rm -rf /var/lib/apt/lists/*

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

bash /app/start_dns.sh
touch /.dockerenv

export HTTPX_LOG_LEVEL=warning
export DISPLAY=:99

# Поднимаем Xvfb для стабильной работы расширений в headed-режиме
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
for i in $(seq 1 20); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        echo "[fortress] Xvfb ready"
        break
    fi
    sleep 0.5
done

PORT="${PORT:-9222}"
INTERNAL_PORT="${FORTRESS_INTERNAL_PORT:-9223}"

EXT_ARGS=""
if [ -d "/app/extensions" ]; then
  EXT_LIST=$(find /app/extensions -mindepth 1 -maxdepth 1 -type d | paste -sd "," -)
  if [ -n "$EXT_LIST" ]; then
    EXT_ARGS="--load-extension=$EXT_LIST --disable-extensions-except=$EXT_LIST"
  fi
fi

echo -e "\n==================================\nstarting fortress chromium cdp server...\nconnect:\nwith sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp('http://localhost:${PORT}')\n==================================\n"

# Запуск браузера БЕЗ флага --headless=new (работает внутри Xvfb)
/opt/tilion/tilion \
  --no-sandbox \
  --disable-setuid-sandbox \
  --disable-dev-shm-usage \
  --enable-unsafe-swiftshader \
  --remote-debugging-port="$INTERNAL_PORT" \
  --user-data-dir=/tmp/tilion-profile \
  --window-size=1920,1080 \
  --start-maximized \
  $EXT_ARGS \
  $FORTRESS_EXTRA_ARGS > /tmp/chrome.log 2>&1 &
CHROME_PID=$!

echo "[fortress] Waiting for internal CDP port $INTERNAL_PORT..."
READY=0
for _ in $(seq 1 80); do
  # Жесткий контроль падения процесса:
  if ! kill -0 $CHROME_PID 2>/dev/null; then
    echo "[fortress] ERROR: Chromium process died unexpectedly!"
    cat /tmp/chrome.log
    exit 1
  fi
  if python3 -c "import socket; s=socket.socket(); s.settimeout(0.5); s.connect(('127.0.0.1', $INTERNAL_PORT)); s.close()" 2>/dev/null; then
    READY=1
    break
  fi
  sleep 0.5
done

if [ "$READY" -eq 0 ]; then
  echo "[fortress] ERROR: Timeout waiting for CDP port."
  cat /tmp/chrome.log
  exit 1
fi

echo "[fortress] CDP ready on $INTERNAL_PORT. Mapping to 0.0.0.0:$PORT"
socat TCP-LISTEN:"$PORT",fork,reuseaddr TCP:127.0.0.1:"$INTERNAL_PORT" &
SOCAT_PID=$!

# Удержание контейнера открытым до смерти браузера
wait $CHROME_PID
echo "[fortress] Chromium process exited normally."
kill $SOCAT_PID 2>/dev/null || true
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]