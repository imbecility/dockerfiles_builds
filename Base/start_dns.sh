#!/bin/bash
set -e

DNSMASQ_CONF="/etc/dnsmasq.conf"
BLOCKLIST_CONF="/etc/dnsmasq.blocklist"
REFRESH_HOURS="${DNS_BLOCKLIST_REFRESH_HOURS:-6}"

if [ "${DNS_SINKHOLE_DISABLE:-0}" != "1" ]; then
    echo "[dns-sinkhole] Уничтожение Docker bind-mount для /etc/resolv.conf..."
    # Отвязываем файл от движка Docker и создаем чистый локальный конфиг
    sudo umount /etc/resolv.conf 2>/dev/null || true
    sudo rm -f /etc/resolv.conf
    sudo sh -c 'echo -e "nameserver 127.0.0.1\noptions timeout:1 attempts:1" > /etc/resolv.conf'

    echo "[dns-sinkhole] Запуск dnsmasq..."
    sudo dnsmasq --conf-file="$DNSMASQ_CONF"

    for i in $(seq 1 20); do
        if python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(1.0); s.connect(('127.0.0.1', 53)); s.close()" 2>/dev/null; then
            echo "[dns-sinkhole] dnsmasq (TCP 53) успешно запущен"
            break
        fi
        sleep 0.2
    done

    # Фоновое обновление базы
    if [ "$REFRESH_HOURS" -gt 0 ] 2>/dev/null; then
        (
            while true; do
                sleep "$((REFRESH_HOURS * 3600))"
                if sudo /app/.venv/bin/python /app/build_dns_blocklist.py \
                    --sources /app/dns_sinkhole/sources.txt \
                    --whitelist /app/dns_sinkhole/whitelist.txt \
                    --output "${BLOCKLIST_CONF}.new"; then
                    sudo mv "${BLOCKLIST_CONF}.new" "${BLOCKLIST_CONF}"
                    sudo pkill -x dnsmasq 2>/dev/null || true
                    sleep 0.5
                    sudo dnsmasq --conf-file="$DNSMASQ_CONF"
                else
                    sudo rm -f "${BLOCKLIST_CONF}.new"
                fi
            done
        ) &
    fi
else
    echo "[dns-sinkhole] Отключено (DNS_SINKHOLE_DISABLE=1)"
    sudo umount /etc/resolv.conf 2>/dev/null || true
    sudo rm -f /etc/resolv.conf
    sudo sh -c 'echo -e "nameserver 1.1.1.1\nnameserver 1.0.0.1" > /etc/resolv.conf'
fi