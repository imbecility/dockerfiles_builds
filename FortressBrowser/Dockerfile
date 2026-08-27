# syntax=docker/dockerfile:1
ARG BASE_IMAGE=base:latest
ARG FORTRESS_IMAGE=tilion/fortress:latest

FROM ${FORTRESS_IMAGE} AS fortress_upstream

FROM ${BASE_IMAGE}

RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
    libvulkan1 mesa-vulkan-drivers fontconfig socat dumb-init gosu unzip \
    libx11-6 libx11-xcb1 libxcb1 libxext6 libxrender1 libxi6 libxtst6 \
    libexpat1 libdbus-1-3 libgl1-mesa-dri libegl-mesa0 >/dev/null && \
    useradd -m -u 1000 tilion && \
    mkdir -p /home/tilion /tmp/tilion-profile /opt/tilion && \
    pip install --no-cache-dir tilion-fortress >/dev/null && \
    /app/chrome-extensions.sh && rm /app/chrome-extensions.sh && \
    rm -rf /var/lib/apt/lists/*

# Копируем /opt из upstream во временную директорию
COPY --from=fortress_upstream /opt /tmp/upstream_opt

# Динамически находим директорию с бинарником chrome и переносим всё в /opt/tilion/
RUN rm -rf /opt/tilion && \
    mkdir -p /opt/tilion && \
    SRC_DIR=$(find /tmp/upstream_opt -type f -name "chrome" -exec dirname {} \; | head -n 1) && \
    echo "Found Chrome in: $SRC_DIR" && \
    cp -a "$SRC_DIR"/* /opt/tilion/ && \
    rm -rf /tmp/upstream_opt && \
    if [ ! -f /opt/tilion/tilion ] && [ -f /opt/tilion/tillion ]; then ln -sf /opt/tilion/tillion /opt/tilion/tilion; fi && \
    chmod -R 755 /opt/tilion && \
    chown -R tilion:tilion /home/tilion /tmp/tilion-profile /app/extensions /opt/tilion && \
    chmod -R 777 /tmp/tilion-profile /home/tilion && \
    ls -la /opt/tilion

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Нативный запуск DNS от root
bash /app/start_dns.sh
touch /.dockerenv

INTERNAL=9223
PORT="${PORT:-9222}"

EXT_ARGS=""
if [ -d "/app/extensions" ]; then
  EXT_LIST=$(find /app/extensions -mindepth 1 -maxdepth 1 -type d | paste -sd "," -)
  if [ -n "$EXT_LIST" ]; then
    EXT_ARGS="--load-extension=$EXT_LIST --disable-extensions-except=$EXT_LIST"
  fi
fi

# 2. Запуск Fortress от пользователя tilion
echo "[fortress] Запуск Chromium процесса..."
gosu tilion /opt/tilion/tilion \
    --headless=new \
    --no-sandbox \
    --disable-dev-shm-usage \
    --enable-unsafe-swiftshader \
    --remote-debugging-port="$INTERNAL" \
    --user-data-dir=/tmp/tilion-profile \
    $EXT_ARGS > /tmp/fortress.log 2>&1 &
CHROME_PID=$!
trap 'kill "$CHROME_PID" 2>/dev/null || true' TERM INT

echo "[fortress] Ожидание открытия внутреннего порта $INTERNAL..."
READY=0
for i in $(seq 1 40); do
    if ! kill -0 $CHROME_PID 2>/dev/null; then
        echo "[fortress] ERROR: Chromium процесс завершился аварийно (итерация $i)!" >&2
        cat /tmp/fortress.log >&2
        exit 1
    fi
    if (exec 3<>"/dev/tcp/127.0.0.1/$INTERNAL") 2>/dev/null; then
        exec 3>&-
        READY=1
        echo "[fortress] Внутренний порт $INTERNAL готов (попытка $i)"
        break
    fi
    sleep 0.5
done

if [ "$READY" -ne 1 ]; then
    echo "[fortress] ERROR: Таймаут ожидания порта $INTERNAL! Лог Chromium:" >&2
    cat /tmp/fortress.log >&2
    exit 1
fi

echo -e "\n==================================\nstarting fortress cdp server...\nconnect:\nwith sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp('http://host:port')\n==================================\n"
exec socat TCP-LISTEN:"$PORT",fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:"$INTERNAL"
EOF

ENV HOME=/home/tilion PORT=9222
EXPOSE ${PORT}
CMD ["dumb-init", "--", "/bin/bash", "/app/start.sh"]