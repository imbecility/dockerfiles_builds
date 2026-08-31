ARG BASE_IMAGE=base:latest

# Stage 1: Сборка Go CDP-прокси
FROM golang:bookworm AS go-builder
WORKDIR /app
COPY proxy ./
RUN go mod init cdp-proxy && \
    go mod tidy && \
    CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -trimpath -o /app/cdp-proxy .

# Stage 2: Скачивание стабильного chrome-headless-shell
FROM debian:stable-slim AS fetcher
RUN apt-get update && apt-get install -y --no-install-recommends curl jq unzip ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp
RUN curl -fsSL https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json -o versions.json && \
    DOWNLOAD_URL=$(jq -r '.channels.Stable.downloads["chrome-headless-shell"][] | select(.platform=="linux64") | .url' versions.json) && \
    echo "Downloading Stable Headless Shell from: $DOWNLOAD_URL" && \
    curl -fsSL "$DOWNLOAD_URL" -o shell.zip && \
    unzip shell.zip && \
    mv chrome-headless-shell-linux64 /opt/headless-shell && \
    chmod +x /opt/headless-shell/chrome-headless-shell

# Stage 3: Финальный образ на основе общего Base
FROM ${BASE_IMAGE}

RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
    ca-certificates \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libexpat1 \
    libgbm1 \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxkbcommon0 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    libgl1-mesa-dri \
    libegl-mesa0 >/dev/null \
    && rm -rf /var/lib/apt/lists/*

COPY --from=fetcher /opt/headless-shell /opt/headless-shell
COPY --from=go-builder /app/cdp-proxy /usr/local/bin/cdp-proxy

ENV CHROME_BIN="/opt/headless-shell/chrome-headless-shell" \
    CHROME_HTTP="http://127.0.0.1:9223" \
    CHROME_WS="ws://127.0.0.1:9223" \
    PROXY_LISTEN=":9222" \
    PROXY_PUBLIC_HOST="localhost:9222" \
    PATH="/opt/headless-shell:${PATH}" \
    PORT=9222

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e
bash /app/start_dns.sh
touch /.dockerenv
exec /usr/local/bin/cdp-proxy
EOF

EXPOSE 9222
CMD ["/bin/bash", "/app/start.sh"]