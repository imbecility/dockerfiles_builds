ARG BASE_IMAGE=base:latest
FROM ${BASE_IMAGE}

ENV XDG_CACHE_HOME=/opt/xdg-cache \
    CC_EXTENSIONS="/app/extensions/ublock,/app/extensions/bitwarden,/app/extensions/gtranslate,/app/extensions/grammarly,/app/extensions/cookies,/app/extensions/yasearch,/app/extensions/clearurls"

WORKDIR /app
COPY serve.py /app/serve.py

RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
      xz-utils socat unzip gosu \
      libnss3 libnspr4 libgbm1 libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libxfixes3 libxext6 libxrender1 libxcb1 \
      libpango-1.0-0 libcairo2 libx11-6 libexpat1 libdbus-1-3 libxi6 libxtst6 \
      fontconfig fonts-unifont fonts-wqy-zenhei >/dev/null && \
    mkdir -p /opt/xdg-cache && \
    pip install --no-cache-dir clearcote >/dev/null && \
    python -c "from clearcote import download; print('binary:', download())" >/dev/null && \
    useradd -m -u 10001 cc && chown -R cc /opt/xdg-cache /app && \
    chmod 755 /root && chmod -R a+rX /root/.local && \
    rm -rf /var/lib/apt/lists/*

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Запуск DNS sinkhole (нативно от root)
bash /app/start_dns.sh

# 2. Бесшовный сброс привилегий и запуск браузера строго от пользователя cc
exec gosu cc /app/.venv/bin/python /app/serve.py
EOF

VOLUME ["/opt/xdg-cache"]
EXPOSE 9222
# Персона через env: CC_PLATFORM (windows|linux|macos|android), CC_FINGERPRINT, CC_BRAND,
# CC_ACCEPT_LANGUAGE, CC_TIMEZONE, CC_HARDWARE_CONCURRENCY, CC_GPU_VENDOR/RENDERER, CC_TLS_PROFILE.
CMD ["/bin/bash", "/app/start.sh"]
