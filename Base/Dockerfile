FROM debian:stable-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsmasq curl ca-certificates procps gosu xvfb x11-utils xdotool \
    fonts-liberation fonts-noto-color-emoji && \
    mkdir -p /etc/dnsmasq.d /app/dns_sinkhole && \
    uv venv /app/.venv --python 3.14 && \
    uv pip install pip httpx && \
    rm -rf /var/lib/apt/lists/*

COPY dnsmasq.conf /etc/dnsmasq.conf
COPY entrypoint.sh /app/entrypoint.sh
COPY build_dns_blocklist.py /app/build_dns_blocklist.py
COPY dns_sinkhole/sources.txt /app/dns_sinkhole/sources.txt
COPY dns_sinkhole/whitelist.txt /app/dns_sinkhole/whitelist.txt

# Первичная генерация базы при сборке образа
RUN chmod +x /app/entrypoint.sh && \
    python3 /app/build_dns_blocklist.py \
      --sources /app/dns_sinkhole/sources.txt \
      --whitelist /app/dns_sinkhole/whitelist.txt \
      --output /etc/dnsmasq.hosts

ENTRYPOINT ["/app/entrypoint.sh"]