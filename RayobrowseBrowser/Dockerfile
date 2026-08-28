# ./Rayobrowse/Dockerfile
# syntax=docker/dockerfile:1
ARG BASE_IMAGE=base:latest
ARG RAYOBROWSE_IMAGE=rayobyte/rayobrowse:latest

FROM ${RAYOBROWSE_IMAGE} AS rayobrowse_upstream

FROM ${BASE_IMAGE}

ENV PORT=9222 \
    PYTHONPATH=/app/rayobyte_python/src \
    STEALTH_BROWSER_ACCEPT_TERMS=true \
    XDG_CONFIG_HOME=/home/browser/.config \
    XDG_DATA_HOME=/home/browser/.local/share

# Системные зависимости для Chromium, TigerVNC и Openbox
RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
    tigervnc-standalone-server openbox x11-xserver-utils x11-utils xdotool \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
    libgl1-mesa-dri libegl-mesa0 fonts-unifont fonts-wqy-zenhei \
    gosu unzip procps ca-certificates >/dev/null && \
    useradd -m -u 1000 browser && \
    mkdir -p /data/data /data/cache /data/logs /home/browser /app/extensions && \
    chown -R browser:browser /data /home/browser /app && \
    /app/chrome-extensions.sh && rm /app/chrome-extensions.sh && \
    rm -rf /var/lib/apt/lists/*

# Копируем runtime Python 3.12, скомпилированные модули и Chromium-стек
COPY --from=rayobrowse_upstream /usr/local /usr/local
COPY --from=rayobrowse_upstream /opt/stealth-browser /opt/stealth-browser
COPY --from=rayobrowse_upstream /app/rayobyte_python /app/rayobyte_python

# Фиксируем права доступа и sandbox setuid
RUN chmod -R 755 /opt/stealth-browser && \
    for sb in /opt/stealth-browser/chromium/v146/b18/chrome-sandbox /opt/stealth-browser/chromium/v146/b18/chrome_sandbox; do \
        if [ -f "$sb" ]; then chown root:root "$sb" && chmod 4755 "$sb"; fi \
    done && \
    chown -R browser:browser /opt/stealth-browser /app/rayobyte_python /home/browser && \
    ldconfig

WORKDIR /app
COPY serve.py /app/serve.py

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Нативный запуск DNS-sinkhole от root
bash /app/start_dns.sh
touch /.dockerenv

# 2. Передача управления в serve.py от пользователя browser
exec gosu browser python3 /app/serve.py
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]