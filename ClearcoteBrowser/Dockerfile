FROM debian:stable-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PATH="/app/.venv/bin:$PATH" \
    XDG_CACHE_HOME=/opt/xdg-cache
WORKDIR /app
COPY serve.py /app/serve.py

# Набор пакетов — как в официальном Dockerfile clearcote-labs: только рантайм-либы
# Chromium + базовый набор шрифтов. Никаких Mesa/EGL — SwiftShader (программный
# рендер) зашит внутри самого бинарника chrome и системных GL-либ не требует.
RUN apt-get update && apt-get install -y --no-install-recommends \
      xz-utils ca-certificates socat xvfb \
      libnss3 libnspr4 libgbm1 libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libxfixes3 libxext6 libxrender1 libxcb1 \
      libpango-1.0-0 libcairo2 libx11-6 libexpat1 libdbus-1-3 libxi6 libxtst6 \
      fontconfig fonts-liberation fonts-noto-color-emoji fonts-unifont fonts-wqy-zenhei && \
    uv venv --python 3.14 && uv pip install pip && \
    mkdir -p /opt/xdg-cache && \
    pip install --no-cache-dir clearcote httpx && \
    python -c "from clearcote import download; print('binary:', download())" && \
    useradd -m -u 10001 cc && chown -R cc /opt/xdg-cache /app && \
    rm -rf /var/lib/apt/lists/*

# Кэш движка — как VOLUME у оригинала, чтобы пережить пересоздание контейнера
# и не тянуть ~180 MB заново на каждый старт.
VOLUME ["/opt/xdg-cache"]

USER cc
EXPOSE 9222
# Персона через env: CC_PLATFORM (windows|linux|macos|android), CC_FINGERPRINT, CC_BRAND,
# CC_ACCEPT_LANGUAGE, CC_TIMEZONE, CC_HARDWARE_CONCURRENCY, CC_GPU_VENDOR/RENDERER, CC_TLS_PROFILE.
ENTRYPOINT ["/app/.venv/bin/python", "/app/serve.py"]