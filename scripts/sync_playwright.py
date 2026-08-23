import importlib.metadata as lib_metadata
from json import loads
from pathlib import Path
from sys import exit

# Вариант А: установлен ли сам пакет playwright?
try:
  print(lib_metadata.version("playwright"))
  exit(0)
except Exception:
  pass

# Вариант Б: это Camoufox — читаем манифест драйвера из .cache или метаданных
cache_dir = Path("/root/.cache/camoufox")
if cache_dir.exists():
    # rglob рекурсивно находит все файлы с именем package.json
    for pkg_path in cache_dir.rglob("package.json"):
        try:
            # Читаем и парсим JSON прямо из объекта Path
            d = loads(pkg_path.read_text(encoding="utf-8"))
            if "playwright" in d.get("name", "") or "version" in d:
                print(d["version"])
                exit(0)
        except Exception:
            pass

# Вариант В: узнаем зависимость playwright из метаданных camoufox
try:
  reqs = lib_metadata.requires("camoufox") or []
  for r in reqs:
      if "playwright" in r:
          print(r)
          exit(0)
except Exception:
  pass