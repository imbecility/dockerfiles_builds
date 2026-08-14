FROM debian:stable-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PATH="/app/.venv/bin:$PATH" \
    PORT=7861 \
    WS_PATH=camoufox

WORKDIR /app
COPY server.py /app/server.py

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdbus-1-3 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libx11-xcb1 libfontconfig1 libx11-6 \
    libxcb1 libxext6 libxshmfence1 \
    libglib2.0-0 libgtk-3-0 libpangocairo-1.0-0 libcairo-gobject2 \
    libgdk-pixbuf-2.0-0 libxss1 libxtst6 fonts-liberation \
    libgl1-mesa-dri libegl-mesa0 xvfb x11-utils xdotool \
    procps xclip ffmpeg unzip && \
    mkdir -p /root/.camoufox && \
    uv venv --python 3.14 && uv pip install pip && ln -s /app/.venv/bin/* /usr/local/bin/ && \
    pip install --no-cache-dir playwright && playwright install-deps firefox 2>/dev/null || true && pip uninstall -y playwright && \
    pip install --no-cache-dir  "camoufox[geoip]" browserforge && \
    camoufox fetch && rm -rf /var/lib/apt/lists/*

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
export MOZ_SANDBOX_DISABLE=1
export MOZ_DISABLE_CONTENT_SANDBOX=1
export MOZ_DISABLE_SOCKET_PROCESS_SANDBOX=1

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

curl -sS 2ip.me
PORT="${PORT:-7861}"
echo -e "\n==================================\nstarting firefox remote server...\nconnect:\nwith sync_playwright() as p:\n    browser = p.firefox.connect('ws://localhost:${PORT}/camoufox')\n==================================\n"
exec python /app/server.py
EOF
EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]
