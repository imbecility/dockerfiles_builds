FROM debian:stable-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PATH="/app/.venv/bin:$PATH" \
    PORT=7860 \
    GPU=true
WORKDIR /app

RUN echo "deb http://deb.debian.org/debian trixie contrib" >> /etc/apt/sources.list.d/contrib.list && \
    echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl git wget ca-certificates \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdbus-1-3 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libx11-xcb1 libfontconfig1 libx11-6 \
    libxcb1 libxext6 libxshmfence1 \
    libglib2.0-0 libgtk-3-0 libpangocairo-1.0-0 libcairo-gobject2 \
    libgdk-pixbuf-2.0-0 libxss1 libxtst6 fonts-liberation \
    fonts-noto-color-emoji fonts-unifont fonts-freefont-ttf \
    fonts-ipafont-gothic fonts-wqy-zenhei fonts-tlwg-loma-otf \
    libgl1-mesa-dri libegl-mesa0 xvfb x11-utils mesa-utils xdotool libglx-mesa0 \
    procps xclip ffmpeg unzip privoxy ttf-mscorefonts-installer && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    uv venv --python 3.14 && uv pip install pip && ln -s /app/.venv/bin/* /usr/local/bin/ && \
    pip install --no-cache-dir playwright && playwright install-deps chromium 2>/dev/null || true && pip uninstall -y playwright && \
    pip install cloakbrowser[serve,geoip] && \
    mkdir -p  ~/.cloakbrowser && touch ~/.cloakbrowser/.welcome_show && \
    find /app/.venv -path "*/cloakbrowser/download.py" -exec sed -i 's/logger.info/logger.debug/g' {} + && \
    python -c "from cloakbrowser import ensure_binary; ensure_binary()" && \
    curl -L https://raw.githubusercontent.com/CloakHQ/CloakBrowser/refs/heads/main/bin/cloakserve -o /app/.venv/bin/cloakserve && \
    sed -i 's/level=logging.INFO/level=logging.WARNING/g' /app/.venv/bin/cloakserve && \
    sed -i '/logger = logging.getLogger("cloakserve")/a logger.setLevel(logging.INFO)' /app/.venv/bin/cloakserve && \
    sed -i 's/"--disable-extensions",//g' /app/.venv/bin/cloakserve && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Dddkjiahejlhfcafbddmgiahcphecmpfh%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/ublock && unzip -q /tmp/ext.zip -d /app/extensions/ublock || true && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Dnngceckbapebfimnlniiiahkandclblb%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/bitwarden && unzip -q /tmp/ext.zip -d /app/extensions/bitwarden || true && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Daapbdbdomjkkjkaonfhkkikfgjllcleb%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/gtranslate && unzip -q /tmp/ext.zip -d /app/extensions/gtranslate || true && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Dkbfnbcaeplbcioakkpcpgfkobkghlhen%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/grammarly && unzip -q /tmp/ext.zip -d /app/extensions/grammarly || true && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Dedibdbjcniadpccecjdfdjjppcpchdlm%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/cookies && unzip -q /tmp/ext.zip -d /app/extensions/cookies || true && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Dladdjijkcfpakbbnnedbhnnciecidncp%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/yasearch && unzip -q /tmp/ext.zip -d /app/extensions/yasearch || true && \
    curl -L "https://github.com/ClearURLs/Addon/releases/download/1.27.3/ClearURLs.zip" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/clearurls && unzip -q /tmp/ext.zip -d /app/extensions/clearurls || true && \
	rm /tmp/ext.zip && \
    chmod +x /app/.venv/bin/cloakserve && fc-cache -f && rm -rf /var/lib/apt/lists/* /root/.cache/* && \
    find /root/.cloakbrowser -name "chromedriver" -delete || true && \
    find /root/.cloakbrowser/Locales -type f -name "*.pak" ! -name "en-US.pak" ! -name "ru.pak" -delete || true && \
    find /root/.cloakbrowser/locales -type f -name "*.pak" ! -name "en-US.pak" ! -name "ru.pak" -delete || true

COPY <<-"EOF" /app/resolv.conf
nameserver 1.1.1.1
nameserver 1.0.0.1
nameserver 2606:4700:4700::1111
nameserver 2606:4700:4700::1002
EOF

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
cat /app/resolv.conf > /etc/resolv.conf
touch /.dockerenv
export HTTPX_LOG_LEVEL=warning
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &

# ждём, пока Xvfb реально начнёт принимать соединения
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
GPU="${GPU:-true}"
case "$GPU" in
    true|1|yes|on)
        GPU_FLAGS=(--use-gl=angle --use-angle=swiftshader)
        ;;
    *)
        GPU_FLAGS=(--disable-gpu --disable-vulkan)
        ;;
esac
echo -e "\n==================================\nstarting chromium cdp server...\nconnect:\nwith sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp('http://host:port/?fingerprint=<seed>')\n==================================\n"
exec /app/.venv/bin/cloakserve \
    --port="${PORT}" \
	--host=0.0.0.0 \
    --log-level=3 \
    --no-sandbox \
    --disable-setuid-sandbox \
    "${GPU_FLAGS[@]}" \
    --window-size=1920,1080 \
    --start-maximized \
    --headless=false \
    --disable-dev-shm-usage \
    --load-extension="/app/extensions/clearurls,/app/extensions/cookies,/app/extensions/grammarly,/app/extensions/gtranslate,/app/extensions/bitwarden,/app/extensions/ublock,/app/extensions/yasearch"
EOF
EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]
