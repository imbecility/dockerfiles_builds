FROM debian:stable-slim

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Создание системных политик отключения DoH/AsyncDNS для всех Chromium-браузеров
RUN mkdir -p /etc/chromium/policies/managed \
             /etc/opt/chrome/policies/managed \
             /etc/firefox/policies && \
    echo '{"DnsOverHttpsMode":"off","BuiltInDnsClientEnabled":false}' > /etc/chromium/policies/managed/disable_doh.json && \
    echo '{"DnsOverHttpsMode":"off","BuiltInDnsClientEnabled":false}' > /etc/opt/chrome/policies/managed/disable_doh.json && \
    echo '{"policies":{"DNSOverHTTPS":{"Enabled":false}}}' > /etc/firefox/policies/policies.json

RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsmasq curl ca-certificates procps sudo xvfb x11-utils xdotool \
    fonts-liberation fonts-noto-color-emoji && \
    echo "ALL ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/nopasswd && \
    mkdir -p /etc/dnsmasq.d /app/dns_sinkhole && \
    uv venv /app/.venv --python 3.14 && \
    uv pip install pip httpx && \
    rm -rf /var/lib/apt/lists/*

COPY dnsmasq.conf /etc/dnsmasq.conf
COPY start_dns.sh /app/start_dns.sh
COPY build_dns_blocklist.py /app/build_dns_blocklist.py
COPY dns_sinkhole/sources.txt /app/dns_sinkhole/sources.txt
COPY dns_sinkhole/whitelist.txt /app/dns_sinkhole/whitelist.txt

RUN chmod +x /app/start_dns.sh && \
    /app/.venv/bin/python /app/build_dns_blocklist.py \
      --sources /app/dns_sinkhole/sources.txt \
      --whitelist /app/dns_sinkhole/whitelist.txt \
      --output /etc/dnsmasq.d/blocklist.conf
