# ./RayobrowseBrowser/Dockerfile
# syntax=docker/dockerfile:1
ARG BASE_IMAGE=base:latest
ARG RAYOBROWSE_IMAGE=rayobyte/rayobrowse:latest

FROM ${RAYOBROWSE_IMAGE} AS rayobrowse_upstream

FROM ${BASE_IMAGE}

ENV PATH="/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    VIRTUAL_ENV="" \
    PORT=9222 \
    PYTHONPATH=/app/rayobyte_python/src \
    STEALTH_BROWSER_ACCEPT_TERMS=true \
    STEALTH_BROWSER_DIR=/opt/stealth-browser \
    XDG_CONFIG_HOME=/home/browser/.config \
    XDG_DATA_HOME=/home/browser/.local/share \
    DISPLAY=:99

RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
    tigervnc-standalone-server openbox x11-xserver-utils x11-utils xdotool \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
    libgl1-mesa-dri libegl-mesa0 fonts-unifont fonts-wqy-zenhei dbus passwd \
    gosu unzip zstd tar procps ca-certificates >/dev/null && \
    mkdir -p /home/browser /data/data /data/cache /data/logs /app/extensions /var/run/dbus && \
    (useradd -m -u 1000 -d /home/browser -s /bin/bash browser 2>/dev/null || true) && \
    dbus-uuidgen > /etc/machine-id 2>/dev/null || true && \
    /app/chrome-extensions.sh && rm /app/chrome-extensions.sh && \
    rm -rf /var/lib/apt/lists/*

COPY --from=rayobrowse_upstream /usr/local /usr/local
COPY --from=rayobrowse_upstream /opt/stealth-browser /opt/stealth-browser
COPY --from=rayobrowse_upstream /app/rayobyte_python /app/rayobyte_python

# 1. Симлинк домашней директории на запеченные бинарники
RUN mkdir -p /home/browser && \
    rm -rf /home/browser/.stealth-browser && \
    ln -sfn /opt/stealth-browser /home/browser/.stealth-browser && \
    chown -R browser:browser /home/browser /opt/stealth-browser /app /data

# 2. Предзагрузка GeoIP и шрифтов в слой образа во время сборки
RUN gosu browser /usr/local/bin/python3 -c "from rayobrowse.updater.auto_update import ensure_geolite2_db; ensure_geolite2_db()" 2>/dev/null || true
RUN gosu browser /usr/local/bin/python3 -c "from rayobrowse.updater.assets import ensure_asset; ensure_asset('fonts')" 2>/dev/null || true

# 3. Права root:root + setuid (4755) для sandbox
RUN chmod -R 755 /opt/stealth-browser && \
    for sb in $(find /opt/stealth-browser -type f -name "*sandbox*"); do \
        chown root:root "$sb" && chmod 4755 "$sb"; \
    done && \
    ldconfig

WORKDIR /app
COPY serve.py /app/serve.py

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Запуск DNS Sinkhole от root
bash /app/start_dns.sh
touch /.dockerenv

# 2. Инициализация /tmp/.X11-unix и прав sandbox
mkdir -p /tmp/.X11-unix /var/run/dbus /home/browser
chmod 1777 /tmp /tmp/.X11-unix
for sb in $(find /opt/stealth-browser -type f -name "*sandbox*" 2>/dev/null); do
    chown root:root "$sb" 2>/dev/null || true
    chmod 4755 "$sb" 2>/dev/null || true
done
chown -R browser:browser /data /home/browser 2>/dev/null || true

# 3. Запуск Xvnc и Openbox от пользователя browser
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 2>/dev/null || true

gosu browser Xvnc :99 -geometry 1920x1080 -depth 32 -rfbport 0 -SecurityTypes None -nolisten tcp >/dev/null 2>&1 &
for i in $(seq 1 30); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then break; fi
    sleep 0.1
done

mkdir -p /home/browser/.local/share/themes/NoBorder/openbox-3 /home/browser/.config/openbox
cat > /home/browser/.local/share/themes/NoBorder/openbox-3/themerc << 'THEME'
border.width: 0
padding.width: 0
padding.height: 0
window.handle.width: 0
window.client.padding.width: 0
window.client.padding.height: 0
THEME

cat > /home/browser/.config/openbox/rc.xml << 'OBXML'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <theme><name>NoBorder</name><font place="ActiveWindow"><name>sans</name><size>0</size></font></theme>
  <applications><application class="*"><decor>no</decor><maximized>no</maximized></application></applications>
</openbox_config>
OBXML
chown -R browser:browser /home/browser/.local /home/browser/.config

gosu browser openbox >/dev/null 2>&1 &
for i in $(seq 1 30); do
    if xprop -display :99 -root _NET_SUPPORTING_WM_CHECK >/dev/null 2>&1; then break; fi
    sleep 0.1
done

echo "[rayobrowse] Дисплей :99 и Openbox успешно инициализированы."

# 4. Запуск serve.py через Python 3.12
exec gosu browser /usr/local/bin/python3 /app/serve.py
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]