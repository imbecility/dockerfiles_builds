# ./FortressBrowser/Dockerfile
ARG BASE_IMAGE=base:latest
FROM ${BASE_IMAGE}

ENV PORT=9222 \
    XDG_CACHE_HOME=/root/.cache \
    HOME=/root

WORKDIR /app

RUN apt-get update >/dev/null && apt-get install -y --no-install-recommends \
      socat unzip \
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
      libpango-1.0-0 libcairo2 libasound2 libxshmfence1 libglib2.0-0 \
      libvulkan1 mesa-vulkan-drivers fontconfig ca-certificates \
      libx11-6 libx11-xcb1 libxcb1 libxext6 libxrender1 libxi6 libxtst6 \
      libexpat1 libdbus-1-3 libgl1-mesa-dri libegl-mesa0 >/dev/null && \
    pip install --no-cache-dir tilion-fortress >/dev/null && \
    python3 -c "from tilion_fortress import Fortress; f = Fortress(); f.start(); f.stop()" >/dev/null 2>&1 || true && \
    /app/chrome-extensions.sh && rm /app/chrome-extensions.sh && \
    rm -rf /var/lib/apt/lists/*

COPY serve.py /app/serve.py

COPY --chmod=755 <<-"EOF" /app/start.sh
#!/bin/bash
set -e

bash /app/start_dns.sh
touch /.dockerenv
export HTTPX_LOG_LEVEL=warning

echo -e "\n==================================\nstarting fortress cdp server...\nconnect:\nwith sync_playwright() as p:\n    browser = p.chromium.connect_over_cdp('http://localhost:9222')\n==================================\n"
exec python /app/serve.py
EOF

EXPOSE ${PORT}
CMD ["/bin/bash", "/app/start.sh"]