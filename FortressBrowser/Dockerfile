# ./FortressBrowser/Dockerfile
ARG BASE_IMAGE=base:latest
FROM ${BASE_IMAGE}

ENV PORT=9222 \
    XDG_CACHE_HOME=/home/tilion/.cache \
    HOME=/home/tilion

WORKDIR /app

# Устанавливаем системные зависимости по спецификации автора
RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
      binutils socat unzip gosu \
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
      libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
      libvulkan1 mesa-vulkan-drivers fontconfig ca-certificates >/dev/null && \
    pip install --no-cache-dir tilion-fortress >/dev/null && \
    useradd -m -u 1000 tilion && \
    mkdir -p /opt/tilion /home/tilion/.cache /tmp/tilion-profile && \
    curl -sSL "https://github.com/tiliondev/fortress/releases/latest/download/tilion-fortress-linux-x64.tar.gz" -o /tmp/fortress.tar.gz && \
    tar -xzf /tmp/fortress.tar.gz -C /opt/tilion --strip-components=1 && \
    rm -f /tmp/fortress.tar.gz && \
    strip --strip-unneeded /opt/tilion/chrome 2>/dev/null || true && \
    strip --strip-unneeded /opt/tilion/chrome_crashpad_handler 2>/dev/null || true && \
    for so in /opt/tilion/*.so /opt/tilion/*.so.1; do strip --strip-unneeded "$so" 2>/dev/null || true; done && \
    find /opt/tilion/locales -type f -name '*.pak' ! -name 'en-US.pak' ! -name 'ru.pak' -delete 2>/dev/null || true && \
    chmod +x /opt/tilion/tilion /opt/tilion/chrome 2>/dev/null || true && \
    /app/chrome-extensions.sh && rm /app/chrome-extensions.sh && \
    chown -R tilion:tilion /opt/tilion /home/tilion /app/extensions /tmp/tilion-profile && \
    rm -rf /var/lib/apt/lists/*

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

# 1. Запуск DNS Sinkhole от root
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

# 2. Запуск Fortress от непривилегированного пользователя tilion
gosu tilion /opt/tilion/tilion \
  --headless=new \
  --no-sandbox \
  --enable-unsafe-swiftshader \
  --remote-debugging-port="$INTERNAL" \
  --user-data-dir=/tmp/tilion-profile \
  $EXT_ARGS &
CHROME_PID=$!
trap 'kill "$CHROME_PID" 2>/dev/null || true' TERM INT

# 3. Нативная проверка доступности сокета через bash /dev/tcp
for _ in $(seq 1 80); do
  if (exec 3<>"/dev/tcp/127.0.0.1/$INTERNAL") 2>/dev/null; then exec 3>&-; break; fi
  sleep 0.5
done

# 4. Проксирование внешнего порта на внутренний через socat
exec socat TCP-LISTEN:"$EXTERNAL",fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:"$INTERNAL"
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]