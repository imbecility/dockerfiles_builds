# syntax=docker/dockerfile:1
ARG BASE_IMAGE=base:latest
ARG RAYOBROWSE_IMAGE=rayobyte/rayobrowse:latest

# 1. Собираем библиотеки для dnsmasq и скачиваем расширения в Base
FROM ${BASE_IMAGE} AS base_tools

RUN mkdir -p /app/extensions /tmp/dnsmasq_libs && \
    for lib in $(ldd /usr/sbin/dnsmasq | grep -o '/lib[^ ]*'); do \
        cp -L "$lib" /tmp/dnsmasq_libs/ 2>/dev/null || true; \
    done && \
    /app/chrome-extensions.sh && \
    rm -f /app/chrome-extensions.sh

# 2. Финальный образ Rayobrowse
FROM ${RAYOBROWSE_IMAGE}

USER root

# Копируем бинарник dnsmasq и ВСЕ найденные ldd библиотеки
COPY --from=base_tools /usr/sbin/dnsmasq /usr/sbin/dnsmasq
COPY --from=base_tools /tmp/dnsmasq_libs/ /usr/lib/x86_64-linux-gnu/

# Копируем конфигурации и скрипты DNS Sinkhole
COPY --from=base_tools /etc/dnsmasq.conf /etc/dnsmasq.conf
COPY --from=base_tools /etc/dnsmasq.hosts /etc/dnsmasq.hosts
COPY --from=base_tools /app/dns_sinkhole /app/dns_sinkhole
COPY --from=base_tools /app/start_dns.sh /app/start_dns.sh
COPY --from=base_tools /app/build_dns_blocklist.py /app/build_dns_blocklist.py

# Копируем готовые расширения
COPY --from=base_tools /app/extensions /app/extensions

# Настраиваем SUID песочницы Chrome, права и скачиваем GeoLite2 один раз при сборке
RUN chmod +x /app/start_dns.sh /usr/sbin/dnsmasq && \
    mkdir -p /data/data /data/cache /data/logs /opt/stealth-browser/geolite2 && \
    for sandbox in /opt/stealth-browser/chromium/chrome_sandbox /opt/stealth-browser/chromium/chrome-sandbox; do \
      if [ -e "$sandbox" ]; then \
        REAL=$(readlink -f "$sandbox" 2>/dev/null || echo "$sandbox"); \
        chown root:root "$REAL" 2>/dev/null && chmod 4755 "$REAL" 2>/dev/null || true; \
      fi; \
    done && \
    python3 -c "from rayobrowse.updater.auto_update import ensure_geolite2_db; ensure_geolite2_db()" 2>/dev/null || true && \
    chown -R browser:browser /app/extensions /data /opt/stealth-browser && \
    chmod -R 777 /tmp /data /app/extensions

COPY serve.py /app/serve.py

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Запуск DNS Sinkhole от root
bash /app/start_dns.sh
touch /.dockerenv

# 2. Очистка старых локов дисплея
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 2>/dev/null || true

# 3. Запуск Xvnc (depth 32)
Xvnc :99 -geometry 1920x1080 -depth 32 -rfbport 0 -SecurityTypes None -nolisten tcp 2>/dev/null &
for _ in $(seq 1 30); do
    if [ -e /tmp/.X11-unix/X99 ]; then break; fi
    sleep 0.1
done

# 4. Запуск оконного менеджера Openbox с ожиданием готовности
export DISPLAY=:99
mkdir -p /home/browser/.config/openbox
cat <<'OBXML' > /home/browser/.config/openbox/rc.xml
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <applications><application class="*"><decor>no</decor><maximized>yes</maximized></application></applications>
</openbox_config>
OBXML
chown -R browser:browser /home/browser/.config
gosu browser openbox &

for _ in $(seq 1 30); do
    xprop -root _NET_SUPPORTING_WM_CHECK 2>/dev/null | grep -q WINDOW && break
    sleep 0.1
done

# 5. Запуск моста и демона
exec python3 /app/serve.py
EOF

ENTRYPOINT []
ENV PORT=9222
EXPOSE 9222
VOLUME ["/data"]
CMD ["/bin/bash", "/app/start.sh"]