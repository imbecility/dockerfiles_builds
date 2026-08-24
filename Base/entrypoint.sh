#!/bin/bash
set -e

# ==============================================================================
# КОНФИГУРАЦИЯ И ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# ==============================================================================
DNSMASQ_CONF="${DNSMASQ_CONF:-/etc/dnsmasq.conf}"
DNS_HOSTS_FILE="${DNS_HOSTS_FILE:-/etc/dnsmasq.hosts}"
REFRESH_HOURS="${DNS_BLOCKLIST_REFRESH_HOURS:-6}"
DISABLE_SINKHOLE="${DNS_SINKHOLE_DISABLE:-0}"

DISABLE_XVFB="${DISABLE_XVFB:-0}"
DISPLAY_NUM="${DISPLAY:-:99}"
SCREEN_RES="${SCREEN_RES:-1920x1080x24}"

# ==============================================================================
# 1. DNS-SINKHOLE (DNSMASQ + AUTO-UPDATER)
# ==============================================================================
if [ "$DISABLE_SINKHOLE" != "1" ]; then
    echo "[dns-sinkhole] Настройка /etc/resolv.conf на локальный резолвер..."
    cat <<EOF > /etc/resolv.conf
nameserver 127.0.0.1
options timeout:1 attempts:1
EOF

    echo "[dns-sinkhole] Запуск dnsmasq..."
    dnsmasq --conf-file="$DNSMASQ_CONF" --keep-in-foreground &
    DNSMASQ_PID=$!

    # Проверка доступности порта 53 (TCP/UDP)
    for i in $(seq 1 25); do
        if python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('127.0.0.1', 53)); s.close()" 2>/dev/null; then
            echo "[dns-sinkhole] dnsmasq готов к приему запросов (попытка $i)"
            break
        fi
        sleep 0.2
    done

    # Chrome / Chromium умеет тихо переключаться на DoH (Cloudflare/Google DoH) в обход системного DNS.
    # Жестко отключаем эту фичу через флаги для всех Chromium-сборок:
    DOH_DISABLE_FLAGS="--disable-features=DnsOverHttpsUpgrade,DnsOverHttps"
    export CC_EXTRA_ARGS="${DOH_DISABLE_FLAGS} ${CC_EXTRA_ARGS}"
    export CHROMIUM_FLAGS="${DOH_DISABLE_FLAGS} ${CHROMIUM_FLAGS}"

    # Фоновый периодический апдейтер
    if [ "$REFRESH_HOURS" -gt 0 ] 2>/dev/null; then
        (
            while true; do
                sleep "$((REFRESH_HOURS * 3600))"
                echo "[dns-sinkhole] Плановое обновление блок-листов..."

                NEW_HOSTS="${DNS_HOSTS_FILE}.new"
                if python3 /app/build_dns_blocklist.py \
                    --sources /app/dns_sinkhole/sources.txt \
                    --whitelist /app/dns_sinkhole/whitelist.txt \
                    --output "$NEW_HOSTS"; then

                    mv "$NEW_HOSTS" "$DNS_HOSTS_FILE"
                    # SIGHUP заставляет dnsmasq мгновенно очистить кэш и перечитать addn-hosts
                    kill -HUP "$DNSMASQ_PID" 2>/dev/null || true
                    echo "[dns-sinkhole] Списки обновлены, dnsmasq перезагрузил базу"
                else
                    echo "[dns-sinkhole] Ошибка обновления списков, сохранены предыдущие базы"
                    rm -f "$NEW_HOSTS"
                fi
            done
        ) &
    fi
else
    echo "[dns-sinkhole] Отключено пользователем (DNS_SINKHOLE_DISABLE=1)"
    cat <<EOF > /etc/resolv.conf
nameserver 1.1.1.1
nameserver 1.0.0.1
EOF
fi

# ==============================================================================
# 2. ВИРТУАЛЬНЫЙ ДИСПЛЕЙ (XVFB)
# ==============================================================================
if [ "$DISABLE_XVFB" != "1" ] && [ -n "$DISPLAY_NUM" ]; then
    echo "[display] Запуск Xvfb на $DISPLAY_NUM ($SCREEN_RES)..."
    export DISPLAY="$DISPLAY_NUM"
    Xvfb "$DISPLAY_NUM" -screen 0 "$SCREEN_RES" -nolisten tcp -ac &

    for i in $(seq 1 25); do
        if xdpyinfo -display "$DISPLAY_NUM" >/dev/null 2>&1; then
            echo "[display] Xvfb успешно запущен (попытка $i)"
            break
        fi
        sleep 0.2
    done
fi

# ==============================================================================
# 3. ПЕРЕДАЧА УПРАВЛЕНИЯ ПРИЛОЖЕНИЮ (ROOT ИЛИ NON-ROOT)
# ==============================================================================
echo -e "\n========================================================"
echo " Starting Service Process: $@"
echo -e "========================================================\n"

if [ -n "$CONTAINER_USER" ] && [ "$CONTAINER_USER" != "root" ]; then
    exec gosu "$CONTAINER_USER" "$@"
else
    exec "$@"
fi