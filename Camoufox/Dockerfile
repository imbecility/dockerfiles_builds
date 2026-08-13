FROM debian:stable-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PATH="/app/.venv/bin:$PATH" \
    PORT=7861 \
    WS_PATH=camoufox

WORKDIR /app
COPY server.py /app/server.py

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    xauth \
    x11-utils \
    xdotool \
    libgtk-3-0 \
    libasound2 \
    libx11-xcb1 \
    libdbus-glib-1-2 \
    libxt6 \
    fonts-liberation \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* && \
    uv venv --python 3.14 && uv pip install pip && ln -s /app/.venv/bin/* /usr/local/bin/ && \
    pip install --no-cache-dir  "camoufox[geoip]" browserforge && \
    camoufox fetch

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

PORT="${PORT:-7861}"
echo -e "\n==================================\nstarting firefox remote server...\nconnect:\nwith sync_playwright() as p:\n    browser = p.firefox.connect('ws://localhost:${PORT}/camoufox')\n==================================\n"
exec python /app/server.py
EOF
EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]
