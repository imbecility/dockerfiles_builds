#!/bin/bash
set -e

DNSMASQ_CONF="/etc/dnsmasq.conf"

if [ "${DNS_SINKHOLE_DISABLE:-0}" != "1" ]; then
    echo -e "nameserver 127.0.0.1\noptions timeout:1 attempts:1" > /etc/resolv.conf
    dnsmasq --conf-file="$DNSMASQ_CONF"
else
    echo -e "nameserver 1.1.1.1\nnameserver 1.0.0.1" > /etc/resolv.conf
fi

echo -e "\n==========================================\nсодержимое /etc/resolv.conf:\n"
cat /etc/resolv.conf
echo -e "\n==========================================\n"
