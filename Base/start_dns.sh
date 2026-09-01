#!/bin/bash
set -e

DNSMASQ_CONF="/etc/dnsmasq.conf"
DNS_HOSTS_FILE="/etc/dnsmasq.hosts"
REFRESH_HOURS="${DNS_BLOCKLIST_REFRESH_HOURS:-6}"

if [ "${DNS_SINKHOLE_DISABLE:-0}" != "1" ]; then
    echo "[dns-sinkhole] Перенаправление /etc/resolv.conf на 127.0.0.1..."
    cat <<EOF > /etc/resolv.conf
nameserver 127.0.0.1
options timeout:1 attempts:1
EOF

    # в resolv.conf можно прописать реальный локальный ip контейнера
    # а в dnsmasq прослушивание 0.0.0.0
    CONTAINER_IP=$(ip route get 1.1.1.1 2>/dev/null \
        | awk '/src/{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')
    if [ -z "$CONTAINER_IP" ] || [[ "$CONTAINER_IP" == 127.* ]]; then
        CONTAINER_IP=$(hostname -I 2>/dev/null | tr ' ' '\n' \
            | grep -v '^127\.' | grep -v '^$' | head -1)
    fi

    echo "[dns-sinkhole] IP контейнера: ${CONTAINER_IP:-не определён (используем 127.0.0.1)}"

    echo "[dns-sinkhole] Проверка конфигурации dnsmasq..."
    # если файл по какой-то причине не создался на этапе build
    if [ ! -f "$DNS_HOSTS_FILE" ]; then
        echo "[dns-sinkhole] ВНИМАНИЕ: $DNS_HOSTS_FILE не найден! Создаем пустой, чтобы dnsmasq не упал."
        touch "$DNS_HOSTS_FILE"
    fi

    echo "[dns-sinkhole] Запуск dnsmasq..."
    pkill -9 -x dnsmasq 2>/dev/null || true
    # stderr в лог, чтобы увидеть причину падения, если оно произойдет.
    dnsmasq --conf-file="$DNSMASQ_CONF" 2>&1 | tee /tmp/dnsmasq_startup.log &
    sleep 1

    if ! pgrep "dnsmasq" > /dev/null; then
        echo "[dns-sinkhole] ОШИБКА: процесс dnsmasq не найден после запуска!"
        echo "[dns-sinkhole] Лог ошибки dnsmasq:"
        cat /tmp/dnsmasq_startup.log || true
        echo "[dns-sinkhole] Текущий resolv.conf:"
        cat /etc/resolv.conf || true
    else
        echo "[dns-sinkhole] dnsmasq успешно запущен."
    fi

    DNS_READY=0
    for i in $(seq 1 40); do
        if /app/.venv/bin/python - 2>/dev/null <<'PYEOF'
import socket
# Минимальный DNS A-запрос: "example.com"
q = (b'\xca\xfe'          # ID
     b'\x01\x00'          # Flags: standard query, recursion desired
     b'\x00\x01'          # QDCOUNT = 1
     b'\x00\x00\x00\x00\x00\x00'
     b'\x07example\x03com\x00'
     b'\x00\x01'          # QTYPE = A
     b'\x00\x01')         # QCLASS = IN
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(0.4)
try:
    s.sendto(q, ('127.0.0.1', 53))
    data = s.recv(512)
    exit(0 if len(data) >= 12 else 1)
except Exception:
    exit(1)
finally:
    s.close()
PYEOF
        then
            DNS_READY=1
            echo "[dns-sinkhole] dnsmasq готов (попытка $i)"
            break
        fi
        sleep 0.25
    done

    if [ "$DNS_READY" -eq 0 ]; then
        echo "[dns-sinkhole] WARN: dnsmasq не ответил за отведённое время — продолжаем" >&2
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
                    --output "${DNS_HOSTS_FILE}.new"; then
                    mv "${DNS_HOSTS_FILE}.new" "${DNS_HOSTS_FILE}"
                    pkill -HUP -x dnsmasq 2>/dev/null || true
                    echo "[dns-sinkhole] База обновлена, кэш dnsmasq сброшен"
                else
                    rm -f "${DNS_HOSTS_FILE}.new"
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