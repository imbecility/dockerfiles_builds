#!/bin/bash
set -e

echo -e "nameserver 127.0.0.1\noptions timeout:1 attempts:1" > /etc/resolv.conf
dnsmasq --conf-file=/etc/dnsmasq.conf

for i in $(seq 1 20); do
    if python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(0.5); s.connect(('127.0.0.1', 53)); s.close()" 2>/dev/null; then
        break
    fi
    sleep 0.2
done

echo -e "\n==========================================\nсодержимое /etc/resolv.conf:\n"
cat /etc/resolv.conf
echo -e "\n==========================================\n"

DOMAIN="mc.yandex.ru"

if curl -I --max-time 3 "http://$DOMAIN" >/dev/null 2>&1; then
    echo "❌ $DOMAIN ОТКРЫВАЕТСЯ — dnsmasq НЕ блокирует"
else
    echo "✅ $DOMAIN НЕ открывается — dnsmasq блокирует"
fi

