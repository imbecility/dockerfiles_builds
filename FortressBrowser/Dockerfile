# ./FortressBrowser/Dockerfile
ARG BASE_IMAGE=base:latest
FROM ${BASE_IMAGE}

ENV PORT=9222 \
    FORTRESS_INTERNAL_PORT=9223 \
    XDG_CACHE_HOME=/root/.cache

WORKDIR /app

RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
      binutils socat unzip \
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
      libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
      libvulkan1 mesa-vulkan-drivers fontconfig >/dev/null && \
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

COPY serve.py /app/serve.py

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Запуск изолированного DNS sinkhole
bash /app/start_dns.sh
touch /.dockerenv
export HTTPX_LOG_LEVEL=warning

PORT="${PORT:-9222}"
FORTRESS_INTERNAL_PORT="${FORTRESS_INTERNAL_PORT:-9223}"
export FORTRESS_INTERNAL_PORT

echo -e "\n==================================\nstarting fortress chromium cdp server...\nconnect:\nwith sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp('http://localhost:${PORT}')\n==================================\n"

# 2. Запускаем socat-мост в фоне (0.0.0.0:9222 -> 127.0.0.1:9223) как задумано автором
socat TCP-LISTEN:${PORT},fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:${FORTRESS_INTERNAL_PORT} &

# 3. Запуск браузера
exec python /app/serve.py
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]