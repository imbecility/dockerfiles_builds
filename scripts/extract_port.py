"""
Извлекает первый порт из вывода `docker inspect --format '{{json .Config.ExposedPorts}}'`.

Используется как в шаге Optimize Docker Image, так и в Verify Minified Image
Использование:
    docker inspect <image> --format '{{json .Config.ExposedPorts}}' | python3 scripts/extract_port.py
"""
from json import load
from sys import stdin, stderr, exit

data = load(stdin)
if not data:
    print("Не удалось определить порт: EXPOSE в Dockerfile не задан.", file=stderr)
    exit(1)

ports = [k.split("/")[0] for k in data.keys()]

# Приоритет CDP/WS портам (9222, 7861, 7860) над вспомогательными (noVNC 6080, метрики и т.д.)
preferred = ["9222", "7861", "7860"]
for p in preferred:
    if p in ports:
        print(p)
        exit(0)

print(ports[0])