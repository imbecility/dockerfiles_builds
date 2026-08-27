# syntax=docker/dockerfile:1
ARG BASE_IMAGE=base:latest
ARG FORTRESS_IMAGE=tilion/fortress:latest

# Официальный образ — только как источник для копирования бинарников
FROM ${FORTRESS_IMAGE} AS fortress_upstream

FROM ${BASE_IMAGE}

RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
    libvulkan1 mesa-vulkan-drivers fontconfig socat dumb-init gosu unzip >/dev/null && \
    useradd -m -u 1000 tilion && \
    mkdir -p /home/tilion /tmp/tilion-profile && \
    pip install --no-cache-dir tilion-fortress >/dev/null && \
    /app/chrome-extensions.sh && rm /app/chrome-extensions.sh && \
    rm -rf /var/lib/apt/lists/*

# Забираем уже стрипнутый и готовый бандл из официального образа
COPY --from=fortress_upstream --chown=tilion:tilion /opt/ /opt/
RUN chown -R tilion:tilion /home/tilion /tmp/tilion-profile /app/extensions

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Нативный запуск DNS от root (без sudo)
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

# 2. Бесшовный сброс привилегий на пользователя tilion через gosu
gosu tilion /opt/tilion/tilion \
    --headless=new \
    --no-sandbox \
    --enable-unsafe-swiftshader \
    --remote-debugging-port="$INTERNAL" \
    --user-data-dir=/tmp/tilion-profile \
    $EXT_ARGS &
CHROME_PID=$!
trap 'kill "$CHROME_PID" 2>/dev/null || true' TERM INT

for i in $(seq 1 40); do
    if (exec 3<>"/dev/tcp/127.0.0.1/$INTERNAL") 2>/dev/null; then
        exec 3>&-
        echo "Fortress готов (попытка $i)"
        break
    fi
    sleep 0.5
done

echo -e "\n==================================\nstarting fortress cdp server...\nconnect:\nwith sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp('http://host:port')\n==================================\n"
exec socat TCP-LISTEN:"$PORT",fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:"$INTERNAL"
EOF

ENV HOME=/home/tilion PORT=9222
EXPOSE ${PORT}
CMD ["dumb-init", "--", "/bin/bash", "/app/start.sh"]