#!/bin/bash
set -e

DNSMASQ_CONF="/etc/dnsmasq.d/blocklist.conf"
REFRESH_HOURS="${DNS_BLOCKLIST_REFRESH_HOURS:-6}"

if [ "${DNS_SINKHOLE_DISABLE:-0}" != "1" ]; then
    # Получаем локальный IP контейнера вместо 127.0.0.1, чтобы обойти анти-loopback паранойю Chromium
    LOCAL_IP=$(hostname -i | awk '{print $1}')
    echo "[dns-sinkhole] Перенаправление /etc/resolv.conf на $LOCAL_IP..."
    cat <<EOF > /etc/resolv.conf
nameserver $LOCAL_IP
options timeout:1 attempts:1
EOF

    echo "[dns-sinkhole] Запуск dnsmasq..."
    dnsmasq

    # Простейшая валидация старта
    for i in $(seq 1 30); do
        if /app/.venv/bin/python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('$LOCAL_IP', 53)); s.close()" 2>/dev/null; then
            echo "[dns-sinkhole] dnsmasq успешно запущен"
            break
        fi
        sleep 0.2
    done

    # Полное отсечение процесса от сессии sudo для Clearcote
    if [ "$REFRESH_HOURS" -gt 0 ] 2>/dev/null; then
        UPDATER_SCRIPT="/tmp/dns_updater.sh"
        cat <<EOF > "$UPDATER_SCRIPT"
#!/bin/bash
while true; do
    sleep \$(( $REFRESH_HOURS * 3600 ))
    if /app/.venv/bin/python /app/build_dns_blocklist.py \\
        --sources /app/dns_sinkhole/sources.txt \\
        --whitelist /app/dns_sinkhole/whitelist.txt \\
        --output "${DNSMASQ_CONF}.new"; then
        mv "${DNSMASQ_CONF}.new" "$DNSMASQ_CONF"
        pkill -HUP -x dnsmasq 2>/dev/null || true
    fi
done
EOF
        chmod +x "$UPDATER_SCRIPT"
        nohup "$UPDATER_SCRIPT" >/dev/null 2>&1 &
    fi
else
    echo "[dns-sinkhole] Отключено (DNS_SINKHOLE_DISABLE=1)"
    cat <<EOF > /etc/resolv.conf
nameserver 1.1.1.1
nameserver 1.0.0.1
EOF
fi
