ARG BASE_IMAGE=base:latest
FROM ${BASE_IMAGE}

ENV PORT=7860
WORKDIR /app

RUN echo "deb http://deb.debian.org/debian bookworm contrib" > /etc/apt/sources.list.d/contrib.list && \
    echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections && \
    apt-get update >/dev/null && apt-get install -y --no-install-recommends \
    git \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdbus-1-3 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libx11-xcb1 libfontconfig1 libx11-6 \
    libxcb1 libxext6 libxshmfence1 \
    libglib2.0-0 libgtk-3-0 libpangocairo-1.0-0 libcairo-gobject2 \
    libgdk-pixbuf-2.0-0 libxss1 libxtst6 \
    fonts-unifont fonts-freefont-ttf \
    fonts-ipafont-gothic fonts-wqy-zenhei fonts-tlwg-loma-otf \
    ttf-mscorefonts-installer \
    libgl1-mesa-dri libegl-mesa0 \
    xclip ffmpeg unzip >/dev/null && \
    ln -sf /app/.venv/bin/* /usr/local/bin/ && \
    pip install --no-cache-dir cloakbrowser[serve,geoip] >/dev/null && \
    mkdir -p ~/.cloakbrowser && touch ~/.cloakbrowser/.welcome_show && \
    find /app/.venv -path "*/cloakbrowser/download.py" -exec sed -i 's/logger.info/logger.debug/g' {} + && \
    python -c "from cloakbrowser import ensure_binary; ensure_binary()" >/dev/null && \
    curl -sSL https://raw.githubusercontent.com/CloakHQ/CloakBrowser/refs/heads/main/bin/cloakserve -o /app/.venv/bin/cloakserve && \
    sed -i 's/level=logging.INFO/level=logging.WARNING/g' /app/.venv/bin/cloakserve && \
    sed -i '/logger = logging.getLogger("cloakserve")/a logger.setLevel(logging.INFO)' /app/.venv/bin/cloakserve && \
    sed -i 's/"--disable-extensions",//g' /app/.venv/bin/cloakserve && \
    chmod +x /app/.venv/bin/cloakserve && fc-cache -f && rm -rf /var/lib/apt/lists/* /root/.cache/* && \
    find /root/.cloakbrowser -name "chromedriver" -delete || true && \
    find /root/.cloakbrowser/Locales -type f -name "*.pak" ! -name "en-US.pak" ! -name "ru.pak" -delete || true && \
    find /root/.cloakbrowser/locales -type f -name "*.pak" ! -name "en-US.pak" ! -name "ru.pak" -delete || true

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e
sudo bash /app/start_dns.sh
touch /.dockerenv
export HTTPX_LOG_LEVEL=warning
export DISPLAY=:99

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

PORT="${PORT:-7860}"
echo -e "\n==================================\nstarting chromium cdp server...\nconnect:\nwith sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp('http://host:port/?fingerprint=<seed>')\n==================================\n"
exec /app/.venv/bin/cloakserve \
    --port="${PORT}" \
    --host=0.0.0.0 \
    --log-level=3 \
    --no-sandbox \
    --disable-setuid-sandbox \
    --use-gl=angle \
    --use-angle=swiftshader \
    --enable-unsafe-swiftshader \
    --window-size=1920,1080 \
    --start-maximized \
    --headless=false \
    --disable-dev-shm-usage \
    --load-extension="/app/extensions/clearurls,/app/extensions/cookies,/app/extensions/grammarly,/app/extensions/gtranslate,/app/extensions/bitwarden,/app/extensions/ublock,/app/extensions/yasearch"
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]