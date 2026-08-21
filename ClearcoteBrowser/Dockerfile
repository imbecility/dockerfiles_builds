FROM debian:stable-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PATH="/app/.venv/bin:$PATH" \
    PORT=9222

WORKDIR /app

RUN echo "deb http://deb.debian.org/debian trixie contrib" >> /etc/apt/sources.list.d/contrib.list && \
    echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates procps xclip ffmpeg unzip xz-utils \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdbus-1-3 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libx11-xcb1 libfontconfig1 libx11-6 libxcb1 libxext6 libxshmfence1 libglib2.0-0 \
    libgtk-3-0 libpangocairo-1.0-0 libcairo-gobject2 libgdk-pixbuf-2.0-0 libxss1 libxtst6 \
    fonts-liberation fonts-croscore fonts-noto-color-emoji fonts-unifont fonts-freefont-ttf \
    fonts-ipafont-gothic fonts-wqy-zenhei fonts-tlwg-loma-otf \
    libgl1-mesa-dri libegl-mesa0 xvfb x11-utils xdotool mesa-utils libglx-mesa0 libgl1 libegl1 libglvnd0 \
    ttf-mscorefonts-installer git privoxy && \
    uv venv --python 3.14 && uv pip install pip && \
    pip install --no-cache-dir playwright httpx clearcote && \
    playwright install-deps chromium 2>/dev/null || true && pip uninstall -y playwright && \
    python -c "import clearcote; clearcote.download()" && \
    find /root/.cache/clearcote -iname "chromedriver" -delete || true && \
    CC_BIN=$(find /root/.cache/clearcote -type f -name "chrome" | head -n 1) && \
    ln -sf "$CC_BIN" /usr/local/bin/clearcote-browser && \
    chmod +x /usr/local/bin/clearcote-browser && \
    mkdir -p /root/.clearcote/profile && \
    fc-cache -f && \
    rm -rf /var/lib/apt/lists/* /root/.cache/pip

COPY <<-"EOF" /app/resolv.conf
nameserver 1.1.1.1
nameserver 1.0.0.1
nameserver 2606:4700:4700::1111
nameserver 2606:4700:4700::1002
EOF

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
cat /app/resolv.conf > /etc/resolv.conf 2>/dev/null || true
touch /.dockerenv 2>/dev/null || true
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
fc-cache -f 2>/dev/null || true

PORT="${PORT:-9222}"
FINGERPRINT="${CC_FINGERPRINT:-clearcote-seed-123}"
PLATFORM="${CC_PLATFORM:-linux}"

echo -e "\n==================================\nstarting clearcote cdp server directly...\n==================================\n"

exec /usr/local/bin/clearcote-browser \
    --remote-debugging-port="${PORT}" \
    --remote-debugging-address=0.0.0.0 \
    --remote-allow-origins="*" \
    --user-data-dir=/root/.clearcote/profile \
    --fingerprint="${FINGERPRINT}" \
    --fingerprint-platform="${PLATFORM}" \
    --no-sandbox \
    --disable-setuid-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --disable-vulkan \
    --window-size=1920,1080 \
    --start-maximized \
    --headless=false
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]