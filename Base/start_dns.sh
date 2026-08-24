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
    dnsmasq

    # Ожидание готовности TCP-порта 53
    DNS_READY=0
    for i in $(seq 1 20); do
        if /app/.venv/bin/python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(0.5); s.connect(('127.0.0.1', 53)); s.close()" 2>/dev/null; then
            echo "[dns-sinkhole] dnsmasq успешно запущен и слушает порт 53"
            DNS_READY=1
            break
        fi
        sleep 0.2
    done

    if [ "$DNS_READY" -ne 1 ]; then
        echo "❌ ОШИБКА: dnsmasq не смог запуститься на 127.0.0.1:53!" >&2
        exit 1
    fi

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
