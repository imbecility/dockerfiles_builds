# ./FortressBrowser/Dockerfile
ARG BASE_IMAGE=base:latest
FROM ${BASE_IMAGE}

ENV PORT=9222 \
    FORTRESS_INTERNAL_PORT=9223 \
    XDG_CACHE_HOME=/root/.cache

WORKDIR /app

# Добавляем все недостающие X11 и GUI библиотеки для работы headful Chromium
RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
      binutils socat unzip \
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
      libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
      libvulkan1 mesa-vulkan-drivers fontconfig \
      libx11-6 libx11-xcb1 libxcb1 libxext6 libxrender1 libxi6 libxtst6 \
      libexpat1 libdbus-1-3 libgtk-3-0 libatspi2.0-0 libgdk-pixbuf-2.0-0 >/dev/null && \
    pip install --no-cache-dir tilion-fortress >/dev/null && \
    mkdir -p /opt/tilion && \
    python3 -c "import tilion_fortress; tilion_fortress.download(target_dir='/opt/tilion')" 2>/dev/null || \
    ( \
      LATEST_RELEASE=$(curl -s https://api.github.com/repos/tiliondev/fortress/releases/latest | grep "browser_download_url.*linux-x64.tar.gz" | cut -d : -f 2,3 | tr -d '\" ' | head -n1) && \
      curl -sSL "$LATEST_RELEASE" -o /tmp/fortress.tar.gz && \
      tar -xzf /tmp/fortress.tar.gz -C /opt/tilion --strip-components=1 && \
      rm -f /tmp/fortress.tar.gz \
    ) && \
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
export DISPLAY=:99

# 2. Виртуальный дисплей для headed-поведения и обхода headless-проверок
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &

for i in $(seq 1 20); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        echo "Xvfb готов (попытка $i)"
        break
    fi
    sleep 0.5
done

if ! xdpyinfo -display :99 >/dev/null 2>&1; then
    echo "Xvfb не поднялся за отведенное время!" >&2
    exit 1
fi

PORT="${PORT:-9222}"
echo -e "\n==================================\nstarting fortress chromium cdp server...\nconnect:\nwith sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp('http://localhost:${PORT}')\n==================================\n"
exec python /app/serve.py
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]