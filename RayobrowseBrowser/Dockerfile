# ./RayobrowseBrowser/Dockerfile
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

COPY --from=rayobrowse_upstream /usr/local /usr/local
COPY --from=rayobrowse_upstream /opt/stealth-browser /opt/stealth-browser
COPY --from=rayobrowse_upstream /app/rayobyte_python /app/rayobyte_python

# Предварительная загрузка GeoLite2 на этапе сборки образа
RUN mkdir -p /opt/stealth-browser/geolite2 && \
    python3 -c "from rayobrowse.updater.auto_update import ensure_geolite2_db; ensure_geolite2_db()" 2>/dev/null || true

RUN chmod -R 755 /opt/stealth-browser && \
    for sb in $(find /opt/stealth-browser -type f -name "*chrome*sandbox*"); do \
        chown root:root "$sb" && chmod 4755 "$sb"; \
    done && \
    chown -R browser:browser /opt/stealth-browser /app/rayobyte_python /home/browser /data && \
    ldconfig

WORKDIR /app
COPY serve.py /app/serve.py

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Запуск DNS Sinkhole от root
bash /app/start_dns.sh
touch /.dockerenv

# 2. Запуск serve.py от пользователя browser
exec gosu browser python3 /app/serve.py
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]