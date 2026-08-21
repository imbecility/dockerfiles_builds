FROM debian:stable-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PATH="/app/.venv/bin:$PATH" \
    PORT=9222 \
    FINGERPRINT="seed-123" \
    PLATFORM="linux" \
    CLEARCOTE_CACHE_DIR=/root/.cache/clearcote \
    XDG_CACHE_HOME=/root/.cache \
    FONTCONFIG_PATH=/etc/fonts

WORKDIR /app
COPY server.py /app/server.py

RUN echo "deb http://deb.debian.org/debian trixie contrib" >> /etc/apt/sources.list.d/contrib.list && \
    echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates procps xclip ffmpeg unzip xz-utils libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdbus-1-3 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libx11-xcb1 libfontconfig1 libx11-6 libxcb1 libxext6 libxshmfence1 libglib2.0-0 \
    libgtk-3-0 libpangocairo-1.0-0 libcairo-gobject2 libgdk-pixbuf-2.0-0 libxss1 libxtst6 fonts-liberation fonts-croscore \
    fonts-noto-color-emoji fonts-unifont fonts-freefont-ttf fonts-ipafont-gothic fonts-wqy-zenhei fonts-tlwg-loma-otf \
    libgl1-mesa-dri libegl-mesa0 xvfb x11-utils xdotool mesa-utils libglx-mesa0 libgl1 libegl1 libglvnd0 \
    ttf-mscorefonts-installer git privoxy socat && \
    uv venv --python 3.14 && uv pip install pip && \
    pip install --no-cache-dir playwright httpx clearcote && \
    playwright install-deps chromium 2>/dev/null || true && \
    pip uninstall -y playwright && \
    python -c "import clearcote; clearcote.download()" && \
    find /root/.cache -name "chromedriver" -delete 2>/dev/null || true && \
    fc-cache -f -v && \
    # Резервное копирование системных шрифтов, конфигов и gconv в /app (защита от сжатия SlimToolkit)
    mkdir -p /app/etc_fonts /app/share_fonts /app/gconv && \
    cp -a /etc/fonts/* /app/etc_fonts/ && \
    cp -a /usr/share/fonts/* /app/share_fonts/ && \
    cp -a /usr/lib/x86_64-linux-gnu/gconv/* /app/gconv/ 2>/dev/null || true && \
    rm -rf /var/lib/apt/lists/*

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
export DISPLAY=:99

# Восстановление fontconfig и шрифтов, если SlimToolkit удалил системные директории
if [ ! -f /etc/fonts/fonts.conf ] && [ -d /app/etc_fonts ]; then
    echo "[start.sh] Восстановление /etc/fonts из /app/etc_fonts..."
    mkdir -p /etc/fonts
    cp -a /app/etc_fonts/* /etc/fonts/
fi

if [ ! -d /usr/share/fonts/truetype ] && [ -d /app/share_fonts ]; then
    echo "[start.sh] Восстановление /usr/share/fonts из /app/share_fonts..."
    mkdir -p /usr/share/fonts
    cp -a /app/share_fonts/* /usr/share/fonts/
fi

if [ ! -d /usr/lib/x86_64-linux-gnu/gconv ] && [ -d /app/gconv ]; then
    echo "[start.sh] Восстановление /usr/lib/x86_64-linux-gnu/gconv..."
    mkdir -p /usr/lib/x86_64-linux-gnu/gconv
    cp -a /app/gconv/* /usr/lib/x86_64-linux-gnu/gconv/ 2>/dev/null || true
fi

Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &

for i in $(seq 1 30); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        echo "Xvfb готов (попытка $i)"
        break
    fi
    sleep 0.5
done

if ! xdpyinfo -display :99 >/dev/null 2>&1; then
    echo "Xvfb не поднялся!" >&2
    exit 1
fi

fc-cache -f 2>/dev/null || true

PORT="${PORT:-9222}"
echo "Запуск Clearcote CDP сервера на порту ${PORT}..."
exec /app/.venv/bin/python -u /app/server.py
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]