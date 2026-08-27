# syntax=docker/dockerfile:1
ARG BASE_IMAGE=base:latest
ARG FORTRESS_IMAGE=tilion/fortress:151.0.7908.0

# официальный образ — только как источник для COPY --from, сам по себе никуда не идёт
FROM ${FORTRESS_IMAGE} AS fortress_upstream

FROM ${BASE_IMAGE}

RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
    libvulkan1 mesa-vulkan-drivers fontconfig socat dumb-init >/dev/null && \
    useradd -m -u 1000 tilion && \
    pip install --no-cache-dir tilion-fortress >/dev/null && \
    rm -rf /var/lib/apt/lists/*

# уже стрипнутый и обрезанный по локалям бандл — берём как есть, повторно стрипать не нужно
COPY --from=fortress_upstream --chown=tilion:tilion /opt/tilion/ /opt/tilion/

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e
sudo bash /app/start_dns.sh

INTERNAL=9223
PORT="${PORT:-9222}"

/opt/tilion/tilion \
    --headless=new \
    --no-sandbox \
    --enable-unsafe-swiftshader \
    --remote-debugging-port="$INTERNAL" \
    --user-data-dir=/tmp/tilion-profile &
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
exec socat TCP-LISTEN:"$PORT",fork,reuseaddr TCP:127.0.0.1:"$INTERNAL"
EOF

USER tilion
ENV HOME=/home/tilion PORT=9222
EXPOSE ${PORT}
CMD ["dumb-init", "--", "/bin/bash", "/app/start.sh"]