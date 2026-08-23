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
      xz-utils ca-certificates socat xvfb unzip curl \
      libnss3 libnspr4 libgbm1 libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libxfixes3 libxext6 libxrender1 libxcb1 \
      libpango-1.0-0 libcairo2 libx11-6 libexpat1 libdbus-1-3 libxi6 libxtst6 \
      fontconfig fonts-liberation fonts-noto-color-emoji fonts-unifont fonts-wqy-zenhei && \
    uv venv --python 3.14 && uv pip install pip && \
    mkdir -p /opt/xdg-cache && \
    pip install --no-cache-dir clearcote httpx && \
    python -c "from clearcote import download; print('binary:', download())" && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Dddkjiahejlhfcafbddmgiahcphecmpfh%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/ublock && unzip -q /tmp/ext.zip -d /app/extensions/ublock || true && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Dnngceckbapebfimnlniiiahkandclblb%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/bitwarden && unzip -q /tmp/ext.zip -d /app/extensions/bitwarden || true && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Daapbdbdomjkkjkaonfhkkikfgjllcleb%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/gtranslate && unzip -q /tmp/ext.zip -d /app/extensions/gtranslate || true && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Dkbfnbcaeplbcioakkpcpgfkobkghlhen%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/grammarly && unzip -q /tmp/ext.zip -d /app/extensions/grammarly || true && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Dedibdbjcniadpccecjdfdjjppcpchdlm%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/cookies && unzip -q /tmp/ext.zip -d /app/extensions/cookies || true && \
    curl -L "https://clients2.google.com/service/update2/crx?response=redirect&arch=x86-64&os_arch=x86-64&nacl_arch=x86-64&prod=chromecrx&prodchannel=unknown&prodversion=9999.0.9999.0&acceptformat=crx2,crx3&x=id%3Dladdjijkcfpakbbnnedbhnnciecidncp%26uc" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/yasearch && unzip -q /tmp/ext.zip -d /app/extensions/yasearch || true && \
    curl -L "https://github.com/ClearURLs/Addon/releases/download/1.27.3/ClearURLs.zip" -o /tmp/ext.zip && \
    mkdir -p /app/extensions/clearurls && unzip -q /tmp/ext.zip -d /app/extensions/clearurls || true && \
    rm -f /tmp/ext.zip && \
    useradd -m -u 10001 cc && chown -R cc /opt/xdg-cache /app && \
    chmod 755 /root && chmod -R a+rX /root/.local && \
    rm -rf /var/lib/apt/lists/*

ENV CC_EXTENSIONS="/app/extensions/ublock,/app/extensions/bitwarden,/app/extensions/gtranslate,/app/extensions/grammarly,/app/extensions/cookies,/app/extensions/yasearch,/app/extensions/clearurls"

# Кэш движка — как VOLUME у оригинала, чтобы пережить пересоздание контейнера
# и не тянуть ~180 MB заново на каждый старт.
VOLUME ["/opt/xdg-cache"]

USER cc
EXPOSE 9222
# Персона через env: CC_PLATFORM (windows|linux|macos|android), CC_FINGERPRINT, CC_BRAND,
# CC_ACCEPT_LANGUAGE, CC_TIMEZONE, CC_HARDWARE_CONCURRENCY, CC_GPU_VENDOR/RENDERER, CC_TLS_PROFILE.
CMD ["/app/.venv/bin/python", "/app/serve.py"]