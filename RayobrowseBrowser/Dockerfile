# syntax=docker/dockerfile:1
ARG BASE_IMAGE=base:latest
ARG RAYOBROWSE_IMAGE=rayobyte/rayobrowse:latest

# ---- Stage 1: Собираем все зависимости и расширения в чистом Base ----
FROM ${BASE_IMAGE} AS base_tools

RUN uv pip install aiohttp rayobrowse >/dev/null && \
    mkdir -p /app/extensions && \
    /app/chrome-extensions.sh && \
    rm -f /app/chrome-extensions.sh

# ---- Stage 2: Финальный образ Rayobrowse без вызовов apt-get ----
FROM ${RAYOBROWSE_IMAGE}

ENV PORT=9222 \
    STEALTH_BROWSER_ACCEPT_TERMS=true \
    RAYOBROWSE_PORT=9222 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Копируем бинарник dnsmasq и связанные библиотеки из base_tools
COPY --from=base_tools /usr/sbin/dnsmasq /usr/sbin/dnsmasq
COPY --from=base_tools /usr/lib/x86_64-linux-gnu/libnettle* /usr/lib/x86_64-linux-gnu/
COPY --from=base_tools /usr/lib/x86_64-linux-gnu/libhogweed* /usr/lib/x86_64-linux-gnu/
COPY --from=base_tools /usr/lib/x86_64-linux-gnu/libgmp* /usr/lib/x86_64-linux-gnu/

# Копируем конфигурации и скрипты DNS Sinkhole
COPY --from=base_tools /etc/dnsmasq.conf /etc/dnsmasq.conf
COPY --from=base_tools /etc/dnsmasq.hosts /etc/dnsmasq.hosts
COPY --from=base_tools /app/dns_sinkhole /app/dns_sinkhole
COPY --from=base_tools /app/start_dns.sh /app/start_dns.sh
COPY --from=base_tools /app/build_dns_blocklist.py /app/build_dns_blocklist.py

# Копируем готовое виртуальное окружение Python и скачанные расширения
COPY --from=base_tools /app/.venv /app/.venv
COPY --from=base_tools /app/extensions /app/extensions

RUN chmod +x /app/start_dns.sh /usr/sbin/dnsmasq && \
    mkdir -p /data

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
exec /app/.venv/bin/python /app/serve.py
EOF

EXPOSE 9222
VOLUME ["/data"]
CMD ["/bin/bash", "/app/start.sh"]