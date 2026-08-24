#!/bin/bash
set -e

DNSMASQ_CONF="/etc/dnsmasq.conf"
BLOCKLIST_CONF="/etc/dnsmasq.d/blocklist.conf"
REFRESH_HOURS="${DNS_BLOCKLIST_REFRESH_HOURS:-6}"

if [ "${DNS_SINKHOLE_DISABLE:-0}" != "1" ]; then
    echo "[dns-sinkhole] Перенаправление /etc/resolv.conf на 127.0.0.1..."
    echo -e "nameserver 127.0.0.1\noptions timeout:1 attempts:1" | tee /etc/resolv.conf > /dev/null

    echo "[dns-sinkhole] Запуск dnsmasq..."
    dnsmasq --conf-file="$DNSMASQ_CONF"

    # Строгая TCP-проверка: если dnsmasq упал из-за ошибки в конфиге, скрипт зависнет и упадет
    for i in $(seq 1 20); do
        if python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(1.0); s.connect(('127.0.0.1', 53)); s.close()" 2>/dev/null; then
            echo "[dns-sinkhole] dnsmasq (TCP 53) успешно запущен и готов"
            break
        fi
        sleep 0.2
    done

    # Фоновое обновление базы
    if [ "$REFRESH_HOURS" -gt 0 ] 2>/dev/null; then
        (
            while true; do
                sleep "$((REFRESH_HOURS * 3600))"
                echo "[dns-sinkhole] Фоновое обновление блок-листов..."
                if python3 /app/build_dns_blocklist.py \
                    --sources /app/dns_sinkhole/sources.txt \
                    --whitelist /app/dns_sinkhole/whitelist.txt \
                    --output "${BLOCKLIST_CONF}.new"; then
                    mv "${BLOCKLIST_CONF}.new" "${BLOCKLIST_CONF}"

                    # Полный рестарт для применения новых address= правил
                    pkill -x dnsmasq 2>/dev/null || true
                    sleep 0.5
                    dnsmasq --conf-file="$DNSMASQ_CONF"
                    echo "[dns-sinkhole] База обновлена, dnsmasq перезапущен"
                else
                    rm -f "${BLOCKLIST_CONF}.new"
                fi
            done
        ) &
    fi
else
    echo "[dns-sinkhole] Отключено (DNS_SINKHOLE_DISABLE=1)"
    echo -e "nameserver 1.1.1.1\nnameserver 1.0.0.1" | tee /etc/resolv.conf > /dev/null
fi