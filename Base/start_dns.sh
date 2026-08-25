#!/bin/bash
set -e

DNSMASQ_CONF="/etc/dnsmasq.d/blocklist.conf"
REFRESH_HOURS="${DNS_BLOCKLIST_REFRESH_HOURS:-6}"

if [ "${DNS_SINKHOLE_DISABLE:-0}" != "1" ]; then
    echo "[dns-sinkhole] Перенаправление /etc/resolv.conf на 127.0.0.1..."
    cat <<EOF > /etc/resolv.conf
nameserver 127.0.0.1
options timeout:1 attempts:1
EOF

    echo "[dns-sinkhole] Запуск dnsmasq..."
    # запускается по умолчанию, подхватывает /etc/dnsmasq.conf
    dnsmasq

    for i in $(seq 1 20); do
        if /app/.venv/bin/python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('127.0.0.1', 53)); s.close()" 2>/dev/null; then
            echo "[dns-sinkhole] dnsmasq успешно запущен"
            break
        fi
        sleep 0.2
    done

    if [ "$REFRESH_HOURS" -gt 0 ] 2>/dev/null; then
        (
            while true; do
                sleep "$((REFRESH_HOURS * 3600))"
                if /app/.venv/bin/python /app/build_dns_blocklist.py \
                    --sources /app/dns_sinkhole/sources.txt \
                    --whitelist /app/dns_sinkhole/whitelist.txt \
                    --output "${DNSMASQ_CONF}.new"; then
                    mv "${DNSMASQ_CONF}.new" "${DNSMASQ_CONF}"
                    pkill -x dnsmasq 2>/dev/null || true
                    sleep 0.2
                    dnsmasq
                else
                    rm -f "${DNSMASQ_CONF}.new"
                fi
            done
        ) </dev/null >/dev/null 2>&1 &
    fi
else
    echo "[dns-sinkhole] Отключено"
    cat <<EOF > /etc/resolv.conf
nameserver 8.8.8.8
nameserver 1.1.1.1
EOF
fi
