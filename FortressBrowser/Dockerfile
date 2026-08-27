# syntax=docker/dockerfile:1
ARG BASE_IMAGE=base:latest
ARG FORTRESS_VERSION=v151.0.7908.0

# ---- stage 1: prep (толстый toolchain стрипа сюда не попадает в финал) ----
FROM debian:bookworm-slim AS prep
ARG FORTRESS_VERSION
RUN apt-get update && apt-get install -y --no-install-recommends binutils curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LO "https://github.com/tiliondev/fortress/releases/download/${FORTRESS_VERSION}/tilion-fortress-linux-x64.tar.gz" && \
    tar xzf tilion-fortress-linux-x64.tar.gz && \
    mv tilion-fortress /opt/tilion && \
    rm tilion-fortress-linux-x64.tar.gz
RUN set -eux; \
    strip --strip-unneeded /opt/tilion/chrome 2>/dev/null || true; \
    strip --strip-unneeded /opt/tilion/chrome_crashpad_handler 2>/dev/null || true; \
    for so in /opt/tilion/*.so /opt/tilion/*.so.1; do strip --strip-unneeded "$so" 2>/dev/null || true; done; \
    find /opt/tilion/locales -type f -name '*.pak' ! -name 'en-US.pak' ! -name 'en-GB.pak' -delete; \
    chmod +x /opt/tilion/tilion /opt/tilion/chrome 2>/dev/null || true

# ---- stage 2: финал, на общем Base (DNS-синкхол/sudo уже там) ----
FROM ${BASE_IMAGE}

RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
    libvulkan1 mesa-vulkan-drivers fontconfig socat dumb-init >/dev/null && \
    useradd -m -u 1000 tilion && \
    rm -rf /var/lib/apt/lists/*

# --chown при копировании, а не отдельный chown -R — не дублируем бандл в новый слой
COPY --from=prep --chown=tilion:tilion /opt/tilion/ /opt/tilion/

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e
sudo bash /app/start_dns.sh

INTERNAL=9223
PORT="${PORT:-9222}"

# используем именно /opt/tilion/tilion (враппер с персоной/шрифтами), а не chrome напрямую
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
# CMD, не ENTRYPOINT — критично для Sync Playwright Version / Extract Internal Browser Version
CMD ["dumb-init", "--", "/bin/bash", "/app/start.sh"]