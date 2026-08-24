#!/bin/bash
set -e

BLOCKLIST_CONF="/etc/dnsmasq.d/blocklist.conf"
REFRESH_HOURS="${DNS_BLOCKLIST_REFRESH_HOURS:-6}"

if [ "${DNS_SINKHOLE_DISABLE:-0}" != "1" ]; then
    echo "[dns-sinkhole] Перенаправление /etc/resolv.conf на 127.0.0.1..."
    cat <<EOF > /etc/resolv.conf
nameserver 127.0.0.1
options timeout:1 attempts:1
EOF

    echo "[dns-sinkhole] Запуск dnsmasq..."
    # БЕЗ --conf-file: читает /etc/dnsmasq.conf по умолчанию,
    # который содержит no-resolv, server=1.1.1.1 и conf-dir с блоклистом
    dnsmasq

    # Ожидание готовности DNS
    for i in $(seq 1 20); do
        if /app/.venv/bin/python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('127.0.0.1', 53)); s.close()" 2>/dev/null; then
            echo "[dns-sinkhole] dnsmasq успешно запущен"
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
                if /app/.venv/bin/python /app/build_dns_blocklist.py \
                    --sources /app/dns_sinkhole/sources.txt \
                    --whitelist /app/dns_sinkhole/whitelist.txt \
                    --output "${BLOCKLIST_CONF}.new"; then
                    mv "${BLOCKLIST_CONF}.new" "${BLOCKLIST_CONF}"
                    # SIGHUP перечитывает только hosts-файлы, НЕ conf-dir.
                    # Для перезагрузки address= директив нужен рестарт.
                    pkill -x dnsmasq 2>/dev/null || true
                    sleep 0.5
                    dnsmasq
                    echo "[dns-sinkhole] База обновлена, dnsmasq перезапущен"
                else
                    rm -f "${BLOCKLIST_CONF}.new"
                fi
            done
        ) &
    fi
else
    echo "[dns-sinkhole] Отключено (DNS_SINKHOLE_DISABLE=1)"
    cat <<EOF > /etc/resolv.conf
nameserver 1.1.1.1
nameserver 1.0.0.1
EOF
fi

echo -e "\n==========================================\nсодержимое /etc/resolv.conf:\n"
cat /etc/resolv.conf
echo -e "\n==========================================\n"

DOMAIN="mc.yandex.ru"

if curl -I --max-time 3 "http://$DOMAIN" >/dev/null 2>&1; then
    echo "❌ $DOMAIN ОТКРЫВАЕТСЯ — dnsmasq НЕ блокирует"
else
    echo "✅ $DOMAIN НЕ открывается — dnsmasq блокирует"
fi
