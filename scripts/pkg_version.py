import re
import subprocess
from importlib import import_module
from importlib.metadata import version as pkg_version
from pathlib import Path
from sys import argv, exit, stderr


def extract_version(target: str) -> str | None:
    target = target.strip()
    if not target:
        return None

    # Способ 1: Если передан путь к бинарнику или бинарник есть в PATH
    if "/" in target or Path(target).exists():
        try:
            out = subprocess.check_output([target, "--version"], text=True, stderr=subprocess.STDOUT)
            match = re.search(r"\d+\.\d+\.\d+\.\d+", out)
            if match:
                return match.group(0)
        except Exception:
            pass

    # Способ 2: Стандартные метаданные pip/wheel (dist-info)
    candidates = list(dict.fromkeys([
        target,
        target.replace("_", "-"),
        target.replace("-", "_")
    ]))

    for name in candidates:
        try:
            return pkg_version(name)
        except Exception:
            pass

    # Способ 3: Импорт модуля и чтение атрибутов версий (__version__)
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
        print("❌ не передан аргумент с именем пакета или путем к бинарнику.", file=stderr)
        exit(1)

    version = extract_version(argv[1])
    if version:
        print(version)
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()