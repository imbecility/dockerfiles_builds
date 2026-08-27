# ./FortressBrowser/serve.py
import os
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

import tilion_fortress

# --- Патч внутренней функции скачивания tilion_fortress для устранения бага с путями ---
def custom_download(plat, host, tag):
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "tilion-fortress" / tag / plat
    cache_dir.mkdir(parents=True, exist_ok=True)

    direct_launcher = cache_dir / "tilion"
    sub_launcher = cache_dir / "tilion-fortress" / "tilion"

    # Если бинарник уже скачан и распакован
    if direct_launcher.exists() or sub_launcher.exists():
        target = direct_launcher if direct_launcher.exists() else sub_launcher
        target.chmod(0o755)
        if (cache_dir / "chrome").exists():
            (cache_dir / "chrome").chmod(0o755)
        sub_launcher.parent.mkdir(parents=True, exist_ok=True)
        if not sub_launcher.exists() and direct_launcher.exists():
            try:
                sub_launcher.symlink_to(direct_launcher)
            except Exception:
                pass
        return target

    # Скачивание архива релиза
    url = f"https://github.com/tiliondev/fortress/releases/download/{tag}/tilion-fortress-{plat}.tar.gz"
    tar_path = cache_dir / f"tilion-fortress-{plat}.tar.gz"
    print(f"[fortress] Скачивание {url} ...", flush=True)
    urllib.request.urlretrieve(url, tar_path)

    # Распаковка
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(cache_dir)
    tar_path.unlink(missing_ok=True)

    # Установка прав и создание симлинков
    if direct_launcher.exists():
        direct_launcher.chmod(0o755)
        if (cache_dir / "chrome").exists():
            (cache_dir / "chrome").chmod(0o755)
        sub_launcher.parent.mkdir(parents=True, exist_ok=True)
        if not sub_launcher.exists():
            try:
                sub_launcher.symlink_to(direct_launcher)
            except Exception:
                pass
        return direct_launcher

    if sub_launcher.exists():
        sub_launcher.chmod(0o755)
        return sub_launcher

    raise RuntimeError(f"Лаунчер не найден в {cache_dir}")

# Применяем патч
tilion_fortress._download = custom_download
if hasattr(tilion_fortress, "__init__"):
    setattr(tilion_fortress.__init__, "_download", custom_download)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--download-only":
        tag = getattr(tilion_fortress, "DEFAULT_TAG", "v149.0.7827.232")
        print(f"[fortress] Предварительное скачивание бинарников ({tag})...", flush=True)
        custom_download("linux-x64", "127.0.0.1", tag)
        print("[fortress] Предварительное скачивание завершено.", flush=True)
        sys.exit(0)

    from tilion_fortress import Fortress

    INTERNAL_PORT = 9223
    EXTERNAL_PORT = int(os.environ.get("PORT", "9222"))

    print("[fortress] Запуск Fortress CDP сервера...", flush=True)

    extra_args = [
        f"--remote-debugging-port={INTERNAL_PORT}",
        "--remote-allow-origins=*",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]

    ext_dir = Path("/app/extensions")
    if ext_dir.exists():
        ext_paths = [str(p) for p in ext_dir.iterdir() if p.is_dir()]
        if ext_paths:
            joined = ",".join(ext_paths)
            extra_args.extend([f"--load-extension={joined}", f"--disable-extensions-except={joined}"])
            print(f"[fortress] Загружено расширений: {len(ext_paths)}", flush=True)

    try:
        f = Fortress(extra_args=extra_args)
    except TypeError:
        try:
            f = Fortress(port=INTERNAL_PORT)
        except TypeError:
            f = Fortress()

    f.start()
    print(f"[fortress] Fortress успешно запущен: {f.cdp_url}", flush=True)

    actual_port = f.cdp_url.split(":")[-1].split("/")[0] if ":" in f.cdp_url else str(INTERNAL_PORT)

    if str(actual_port) != str(EXTERNAL_PORT):
        print(f"[fortress] Публикация порта через socat: 0.0.0.0:{EXTERNAL_PORT} -> 127.0.0.1:{actual_port}", flush=True)
        socat = subprocess.Popen([
            "socat",
            f"TCP-LISTEN:{EXTERNAL_PORT},fork,reuseaddr,bind=0.0.0.0",
            f"TCP:127.0.0.1:{actual_port}"
        ])

    def cleanup(sig, frame):
        print("[fortress] Остановка сервера...", flush=True)
        try:
            f.stop()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    while True:
        time.sleep(1)