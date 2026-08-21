FROM debian:stable-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PATH="/app/.venv/bin:$PATH" \
    PORT=9222 \
    XDG_CACHE_HOME=/app/cache

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
    pip install --no-cache-dir playwright httpx clearcote && playwright install-deps chromium 2>/dev/null || true && pip uninstall -y playwright && \
    python -c "import clearcote; clearcote.download()" && \
    find /root/.cache/clearcote/v0.1.0-pre.22/browser/chrome -name "chromedriver" -delete || true && \
    fc-cache -f && rm -rf /var/lib/apt/lists/* /root/.cache/*

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



Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
for i in $(seq 1 20); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        echo "Xvfb готов (попытка $i)"
        break
    fi
    sleep 0.5
done

PORT="${PORT:-9222}"
export CC_INTERNAL_PORT=9223

echo "Starting socat proxy: 0.0.0.0:${PORT} -> 127.0.0.1:${CC_INTERNAL_PORT}"
socat TCP-LISTEN:${PORT},fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:${CC_INTERNAL_PORT} &

echo -e "\n==================================\nstarting clearcote cdp server...\n==================================\n"
exec /app/.venv/bin/python -u /app/server.py
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]