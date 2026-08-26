import importlib.metadata as lib_metadata
from argparse import ArgumentParser
from json import loads
from pathlib import Path
from re import search, IGNORECASE
from sys import exit
from time import time, sleep


def probe_ws(url: str, timeout: int = 30) -> str | None:
    from playwright.sync_api import sync_playwright

    start = time()
    while time() - start < timeout:
        try:
            with sync_playwright() as p:
                browser = p.firefox.connect(url, timeout=3000)
                browser.close()
                import playwright
                return playwright.__version__
        except Exception as e:
            err_msg = str(e)
            match = search(r"server version:\s*v?([0-9]+(?:\.[0-9]+)+)", err_msg, IGNORECASE)
            if match:
                return match.group(1)
            sleep(1)
    return None


def probe_container_fs() -> str | None:
    # Вариант А: установлен ли сам пакет playwright?
    try:
        return lib_metadata.version("playwright")
    except Exception:
        pass

    # Вариант Б: это Camoufox — читаем манифест драйвера из .cache или метаданных
    cache_dir = Path("/root/.cache/camoufox")
    if cache_dir.exists():
        for pkg_path in cache_dir.rglob("package.json"):
            try:
                d = loads(pkg_path.read_text(encoding="utf-8"))
                if "playwright" in d.get("name", "") or "version" in d:
                    return d["version"]
            except Exception:
                pass

    # Вариант В: узнаем зависимость playwright из метаданных camoufox
    try:
        reqs = lib_metadata.requires("camoufox") or []
        for r in reqs:
            if "playwright" in r:
                return r
    except Exception:
        pass

    return None


def main() -> None:
    parser = ArgumentParser(description="Детекция и синхронизация версии Playwright")
    parser.add_argument("--url", help="WebSocket URL запущенного Playwright-сервера", default=None)
    parser.add_argument("--timeout", type=int, default=60, help="Таймаут ожидания WS в секундах")
    args, _ = parser.parse_known_args()

    version = None
    if args.url:
        version = probe_ws(args.url, timeout=args.timeout)
    else:
        version = probe_container_fs()

    if version:
        print(version)
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()
