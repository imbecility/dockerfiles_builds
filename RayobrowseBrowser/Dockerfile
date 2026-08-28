# syntax=docker/dockerfile:1
ARG BASE_IMAGE=base:latest
ARG RAYOBROWSE_IMAGE=rayobyte/rayobrowse:latest

FROM ${RAYOBROWSE_IMAGE} AS rayo_upstream

FROM ${BASE_IMAGE}

ENV PORT=9222 \
    STEALTH_BROWSER_ACCEPT_TERMS=true \
    RAYOBROWSE_PORT=9222

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
      libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
      libvulkan1 mesa-vulkan-drivers fontconfig ca-certificates socat unzip \
      libx11-6 libx11-xcb1 libxcb1 libxext6 libxrender1 libxi6 libxtst6 \
      libexpat1 libdbus-1-3 libgl1-mesa-dri libegl-mesa0 >/dev/null && \
    pip install --no-cache-dir rayobrowse aiohttp >/dev/null && \
    mkdir -p /data /app/extensions && \
    /app/chrome-extensions.sh && rm /app/chrome-extensions.sh && \
    rm -rf /var/lib/apt/lists/*

# Копируем бинарники демона и Chromium из upstream-образа
COPY --from=rayo_upstream / /tmp/upstream_root/
RUN rm -rf /tmp/upstream_root/etc/resolv.conf /tmp/upstream_root/etc/hosts && \
    cp -rn /tmp/upstream_root/usr/local/* /usr/local/ 2>/dev/null || true && \
    cp -rn /tmp/upstream_root/opt/* /opt/ 2>/dev/null || true && \
    if [ -f "/tmp/upstream_root/entrypoint.sh" ]; then cp /tmp/upstream_root/entrypoint.sh /entrypoint.sh && chmod +x /entrypoint.sh; fi && \
    rm -rf /tmp/upstream_root

COPY serve.py /app/serve.py

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Запуск DNS Sinkhole от root
bash /app/start_dns.sh
touch /.dockerenv

# 2. Запуск CDP сервера и моста
echo -e "\n==================================\nstarting rayobrowse cdp bridge on port ${PORT:-9222}...\nconnect:\nwith sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp('http://localhost:9222')\n==================================\n"
exec python /app/serve.py
EOF

# ВАЖНО: только 9222, чтобы extract_port.py в CI пробрасывал именно CDP порт
EXPOSE 9222
VOLUME ["/data"]
CMD ["/bin/bash", "/app/start.sh"]