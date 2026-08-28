# syntax=docker/dockerfile:1
ARG BASE_IMAGE=base:latest
ARG RAYOBROWSE_IMAGE=rayobyte/rayobrowse:latest

# Берем инструменты DNS sinkhole из нашего Base
FROM ${BASE_IMAGE} AS base_tools

# За основу берем официальный полнофункциональный образ Rayobrowse
FROM ${RAYOBROWSE_IMAGE}

ENV PORT=9222 \
    STEALTH_BROWSER_ACCEPT_TERMS=true \
    RAYOBROWSE_PORT=9222 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Копируем файлы DNS Sinkhole
COPY --from=base_tools /app/dns_sinkhole /app/dns_sinkhole
COPY --from=base_tools /app/start_dns.sh /app/start_dns.sh
COPY --from=base_tools /app/build_dns_blocklist.py /app/build_dns_blocklist.py
COPY --from=base_tools /app/chrome-extensions.sh /app/chrome-extensions.sh
COPY --from=base_tools /etc/dnsmasq.conf /etc/dnsmasq.conf
COPY --from=base_tools /etc/dnsmasq.hosts /etc/dnsmasq.hosts

# Устанавливаем dnsmasq и python окружение для CDP-моста
RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
      dnsmasq curl ca-certificates procps sudo python3-pip python3-venv >/dev/null && \
    python3 -m venv /app/.venv && \
    /app/.venv/bin/pip install --no-cache-dir httpx aiohttp rayobrowse >/dev/null && \
    chmod +x /app/start_dns.sh /app/chrome-extensions.sh && \
    mkdir -p /data /app/extensions && \
    /app/chrome-extensions.sh && rm /app/chrome-extensions.sh && \
    rm -rf /var/lib/apt/lists/*

COPY serve.py /app/serve.py

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Запуск DNS Sinkhole
bash /app/start_dns.sh
touch /.dockerenv
export HTTPX_LOG_LEVEL=warning

# 2. Запуск CDP сервера и моста
echo -e "\n==================================\nstarting rayobrowse cdp bridge on port ${PORT:-9222}...\nconnect:\nwith sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp('http://localhost:9222')\n==================================\n"
exec /app/.venv/bin/python3 /app/serve.py
EOF

EXPOSE 9222
VOLUME ["/data"]
CMD ["/bin/bash", "/app/start.sh"]