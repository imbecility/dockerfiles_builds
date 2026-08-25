FROM debian:stable-slim

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
    dnsmasq curl ca-certificates procps sudo xvfb x11-utils xdotool iproute2 \
    fonts-liberation fonts-noto-color-emoji >/dev/null && \
    echo "Defaults !requiretty" > /etc/sudoers.d/nopasswd && \
    echo "ALL ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/nopasswd && \
    chmod 0440 /etc/sudoers.d/nopasswd && \
    mkdir -p /etc/dnsmasq.d /app/dns_sinkhole /tmp/.X11-unix && \
    chmod 1777 /tmp /tmp/.X11-unix && \
    uv venv /app/.venv --python 3.14 && \
    uv pip install pip httpx >/dev/null && \
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
      --output /etc/dnsmasq.hosts