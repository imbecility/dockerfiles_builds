#!/bin/bash
set -e

DNSMASQ_CONF="/etc/dnsmasq.conf"

if [ "${DNS_SINKHOLE_DISABLE:-0}" != "1" ]; then
    echo -e "nameserver 127.0.0.1\noptions timeout:1 attempts:1" > /etc/resolv.conf
    dnsmasq --conf-file="$DNSMASQ_CONF"

    for i in $(seq 1 20); do
        if python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(0.5); s.connect(('127.0.0.1', 53)); s.close()" 2>/dev/null; then
            break
        fi
        sleep 0.2
    done
else
    echo -e "nameserver 1.1.1.1\nnameserver 1.0.0.1" > /etc/resolv.conf
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

