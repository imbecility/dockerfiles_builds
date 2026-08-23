"""
Универсальный скрипт извлечения версии установленного пакета или модуля.

Запускается внутри контейнера через передачу в stdin:
    docker run -i --rm <image> python - <package_name> < scripts/pkg_version.py
"""
from importlib import import_module
from importlib.metadata import version as pkg_version
from sys import argv, stderr, exit


def extract_version(pkg_name: str) -> str | None:
    pkg_name = pkg_name.strip()
    if not pkg_name:
        return None

    # Варианты написания имени (например: my-pkg vs my_pkg)
    candidates = list(dict.fromkeys([
        pkg_name,
        pkg_name.replace("_", "-"),
        pkg_name.replace("-", "_")
    ]))

    # Способ 1: Стандартные метаданные pip/wheel (dist-info)
    for name in candidates:
        try:
            return pkg_version(name)
        except Exception:
            pass

    # Способ 2: Импорт модуля и чтение атрибутов версий
    for name in candidates:
        try:
            mod = import_module(name)
            for attr in ("__version__", "VERSION", "version", "__VERSION__"):
                val = getattr(mod, attr, None)
                if val is not None:
                    if callable(val):
                        try:
                            val = val()
                        except Exception:
                            continue
                    if isinstance(val, (tuple, list)):
                        return ".".join(map(str, val))
                    return str(val).strip()
        except Exception:
            pass

    return None


def main() -> None:
    if len(argv) < 2:
        print("❌ не передан аргумент с именем пакета.", file=stderr)
        exit(1)

    pkg_name = argv[1]
    version = extract_version(pkg_name)

    if version:
        print(version)
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()