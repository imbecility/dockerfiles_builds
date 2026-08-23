"""
Извлекает первый порт из вывода `docker inspect --format '{{json .Config.ExposedPorts}}'`.

Используется как в шаге Optimize Docker Image, так и в Verify Minified Image —
раньше один и тот же однострочник был продублирован в обоих местах.

Использование:
    docker inspect <image> --format '{{json .Config.ExposedPorts}}' | python3 scripts/extract_port.py
"""
from json import load
from sys import stdin, stderr, exit

data = load(stdin)
if not data:
    print("Не удалось определить порт: EXPOSE в Dockerfile не задан.", file=stderr)
    exit(1)

print(list(data.keys())[0].split("/")[0])