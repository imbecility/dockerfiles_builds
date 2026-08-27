# ./FortressBrowser/Dockerfile
ARG BASE_IMAGE=base:latest
FROM ${BASE_IMAGE}

ENV PORT=9222 \
    XDG_CACHE_HOME=/home/tilion/.cache \
    HOME=/home/tilion

WORKDIR /app

RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
      binutils socat unzip gosu \
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
      libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
      libvulkan1 mesa-vulkan-drivers fontconfig ca-certificates \
      libx11-6 libx11-xcb1 libxcb1 libxext6 libxrender1 libxi6 libxtst6 \
      libexpat1 libdbus-1-3 libgl1-mesa-dri libegl-mesa0 >/dev/null && \
    pip install --no-cache-dir tilion-fortress >/dev/null && \
    useradd -m -u 1000 tilion && \
    mkdir -p /opt/tilion /opt/tilion/fonts /home/tilion/.cache/tilion/fc /tmp/tilion-profile && \
    curl -sSL "https://github.com/tiliondev/fortress/releases/latest/download/tilion-fortress-linux-x64.tar.gz" -o /tmp/fortress.tar.gz && \
    tar -xzf /tmp/fortress.tar.gz -C /opt/tilion --strip-components=1 && \
    rm -f /tmp/fortress.tar.gz && \
    strip --strip-unneeded /opt/tilion/chrome 2>/dev/null || true && \
    strip --strip-unneeded /opt/tilion/chrome_crashpad_handler 2>/dev/null || true && \
    for so in /opt/tilion/*.so /opt/tilion/*.so.1; do strip --strip-unneeded "$so" 2>/dev/null || true; done && \
    find /opt/tilion/locales -type f -name '*.pak' ! -name 'en-US.pak' ! -name 'ru.pak' -delete 2>/dev/null || true && \
    chmod +x /opt/tilion/tilion /opt/tilion/chrome 2>/dev/null || true && \
    /app/chrome-extensions.sh && rm /app/chrome-extensions.sh && \
    rm -rf /var/lib/apt/lists/*

# Создаем гарантированный шаблон fonts.conf.template для скрипта tilion
RUN cat <<'EOF' > /opt/tilion/fonts/fonts.conf.template
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>@FONTDIR@</dir>
  <cachedir>@CACHEDIR@</cachedir>
  <alias><family>sans-serif</family><prefer><family>Arial</family><family>Segoe UI</family></prefer></alias>
  <alias><family>serif</family><prefer><family>Times New Roman</family></prefer></alias>
  <alias><family>monospace</family><prefer><family>Courier New</family><family>Consolas</family></prefer></alias>
  <alias><family>Arial</family><default><family>sans-serif</family></default></alias>
  <alias><family>emoji</family><prefer><family>Segoe UI Emoji</family></prefer></alias>
  <match target="pattern"><test name="family"><string>Liberation Sans</string></test><edit name="family" mode="assign" binding="strong"><string>__uxr_none__</string></edit></match>
  <match target="pattern"><test name="family"><string>Liberation Serif</string></test><edit name="family" mode="assign" binding="strong"><string>__uxr_none__</string></edit></match>
  <match target="pattern"><test name="family"><string>Liberation Mono</string></test><edit name="family" mode="assign" binding="strong"><string>__uxr_none__</string></edit></match>
  <match target="pattern"><test name="family"><string>Carlito</string></test><edit name="family" mode="assign" binding="strong"><string>__uxr_none__</string></edit></match>
  <match target="pattern"><test name="family"><string>Caladea</string></test><edit name="family" mode="assign" binding="strong"><string>__uxr_none__</string></edit></match>
</fontconfig>
EOF
RUN cp /opt/tilion/fonts/fonts.conf.template /opt/tilion/fonts.conf.template 2>/dev/null || true && \
    if [ -f /opt/tilion/vk_swiftshader_icd.json ]; then sed -i 's|"library_path": ".*"|"library_path": "/opt/tilion/libvk_swiftshader.so"|g' /opt/tilion/vk_swiftshader_icd.json; fi && \
    chown -R tilion:tilion /opt/tilion /home/tilion /app/extensions /tmp/tilion-profile && \
    chmod -R 777 /tmp/tilion-profile /home/tilion/.cache

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. DNS Sinkhole
bash /app/start_dns.sh
touch /.dockerenv

INTERNAL=9223
EXTERNAL="${PORT:-9222}"

EXT_ARGS=""
if [ -d "/app/extensions" ]; then
  EXT_LIST=$(find /app/extensions -mindepth 1 -maxdepth 1 -type d | paste -sd "," -)
  if [ -n "$EXT_LIST" ]; then
    EXT_ARGS="--load-extension=$EXT_LIST --disable-extensions-except=$EXT_LIST"
  fi
fi

echo "[fortress] Starting Chromium process..."
gosu tilion /opt/tilion/tilion \
  --headless=new \
  --no-sandbox \
  --disable-dev-shm-usage \
  --enable-unsafe-swiftshader \
  --remote-debugging-port="$INTERNAL" \
  --remote-allow-origins="*" \
  --user-data-dir=/tmp/tilion-profile \
  $EXT_ARGS > /tmp/fortress.log 2>&1 &
CHROME_PID=$!
trap 'kill "$CHROME_PID" 2>/dev/null || true' TERM INT

echo "[fortress] Waiting for internal port $INTERNAL..."
READY=0
for i in $(seq 1 40); do
  if ! kill -0 $CHROME_PID 2>/dev/null; then
    echo "[fortress] FATAL: Process died! Container logs:" >&2
    cat /tmp/fortress.log >&2
    exit 1
  fi
  if (exec 3<>"/dev/tcp/127.0.0.1/$INTERNAL") 2>/dev/null; then
    exec 3>&-
    READY=1
    echo "[fortress] Port $INTERNAL is open and ready."
    break
  fi
  sleep 0.5
done

if [ "$READY" -ne 1 ]; then
  echo "[fortress] FATAL: Port $INTERNAL did not open in 20s! Container logs:" >&2
  cat /tmp/fortress.log >&2
  exit 1
fi

echo "[fortress] Forwarding 0.0.0.0:$EXTERNAL -> 127.0.0.1:$INTERNAL"
exec socat TCP-LISTEN:"$EXTERNAL",fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:"$INTERNAL"
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]