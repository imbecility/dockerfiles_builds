# syntax=docker/dockerfile:1
ARG RAYOBROWSE_IMAGE=rayobyte/rayobrowse:latest
FROM ${RAYOBROWSE_IMAGE}

ENV PORT=9222 \
    STEALTH_BROWSER_ACCEPT_TERMS=true \
    RAYOBROWSE_PORT=9222

WORKDIR /app

# Устанавливаем dnsmasq и вспомогательные утилиты для работы DNS Sinkhole
USER root
RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
      dnsmasq procps sudo curl socat unzip >/dev/null && \
    mkdir -p /etc/dnsmasq.d /app/dns_sinkhole /app/extensions && \
    rm -rf /var/lib/apt/lists/*

# Добавляем скрипты DNS Sinkhole
COPY --from=base:latest /app/start_dns.sh /app/start_dns.sh
COPY --from=base:latest /app/build_dns_blocklist.py /app/build_dns_blocklist.py
COPY --from=base:latest /app/dns_sinkhole/ /app/dns_sinkhole/
COPY --from=base:latest /etc/dnsmasq.conf /etc/dnsmasq.conf
COPY --from=base:latest /app/chrome-extensions.sh /app/chrome-extensions.sh

RUN chmod +x /app/start_dns.sh /app/chrome-extensions.sh && \
    /app/chrome-extensions.sh && rm /app/chrome-extensions.sh

COPY serve.py /app/serve.py

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Запуск DNS Sinkhole
bash /app/start_dns.sh
touch /.dockerenv

# 2. Запуск сервиса
exec python3 /app/serve.py
EOF

EXPOSE 9222
VOLUME ["/data"]
CMD ["/bin/bash", "/app/start.sh"]