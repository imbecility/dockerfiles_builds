from json import dumps
from os import environ, getenv
from pathlib import Path
from subprocess import check_output

import httpx

event = getenv("EVENT_NAME")
owner = getenv("OWNER", "").lower()
repo = getenv("REPO", "").lower()
token = getenv("GH_TOKEN")
input_service = getenv("INPUT_SERVICE", "all")


def get_pypi_package_name(dir_name: str) -> str | None:
    path = Path(dir_name) / "pypi_package.txt"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception as e:
        print(f"Ошибка чтения {path}: {e}")
        return None


def get_latest_pypi_version(package_name: str) -> str | None:
    try:
        r = httpx.get(f"https://pypi.org/pypi/{package_name}/json", timeout=15)
        if r.status_code == 200:
            return r.json()["info"]["version"]
    except Exception as e:
        print(f"Ошибка получения версии PyPI для {package_name}: {e}")
    return None


def ghcr_tag_exists(package_name: str, target_tag: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    pkg_variants = [
        package_name.lower(),
        f"{repo}/{package_name.lower()}".replace('/', '%2F')
    ]

    for base_endpoint in [f"https://api.github.com/orgs/{owner}/packages/container",
                          f"https://api.github.com/users/{owner}/packages/container"]:
        for pkg in pkg_variants:
            page = 1
            while True:
                url = f"{base_endpoint}/{pkg}/versions?per_page=100&page={page}"
                try:
                    r = httpx.get(url, headers=headers, timeout=15)
                    if r.status_code != 200:
                        break

                    versions = r.json()
                    if not versions:
                        break

                    for v in versions:
                        tags = v.get("metadata", {}).get("container", {}).get("tags", [])
                        if target_tag in tags:
                            return True

                    if len(versions) < 100:
                        break
                    page += 1
                except Exception as e:
                    print(f"❌ ошибка проверки тегов в GHCR ({url}):\n{e}")
                    break
    return False


def main() -> None:
    services_to_build: list[str] = []
    should_build_base = False

    # доступные браузерные сервисы
    all_dirs = sorted([p.parent.name for p in Path(".").glob("*/Dockerfile") if p.parent.name != "."])
    # Base из матрицы исключается
    browser_dirs = [d for d in all_dirs if d != "Base"]

    div = "\n" + "=" * 42 + "\n"
    print(f"{div}🚧 режим запуска: {event} 🚧{div}")

    # проверка существует ли уже base:latest в GHCR
    base_exists = ghcr_tag_exists("base", "latest")
    if not base_exists:
        print("ℹ️ базовый образ base:latest не найден в GHCR: Base отправлен на сборку")
        should_build_base = True

    if event == "schedule":
        print("ℹ️ проверка новых релизов в апстрим PyPI...")
        for dir_name in browser_dirs:
            pypi_pkg = get_pypi_package_name(dir_name)
            if not pypi_pkg:
                continue

            latest_ver = get_latest_pypi_version(pypi_pkg)
            if not latest_ver:
                print(f"❌ [{dir_name}] не удалось получить версию из PyPI.")
                continue

            print(f"☑️ [{dir_name}] актуальная версия {pypi_pkg} на PyPI: {latest_ver}")

            image_name = dir_name.lower()
            if not ghcr_tag_exists(image_name, latest_ver):
                print(f"  → [🧩] тег '{latest_ver}' еще не собран в GHCR: добавлен в очередь!")
                services_to_build.append(dir_name)
            else:
                print(f"  → [✅] образ с тегом '{latest_ver}' уже существует в GHCR.")

    elif event == "workflow_dispatch":
        if input_service and input_service != "all":
            if input_service == "Base":
                should_build_base = True
                services_to_build = browser_dirs
            else:
                services_to_build = [input_service]
        else:
            should_build_base = True
            services_to_build = browser_dirs

    else:  # push
        before = getenv("BEFORE", "")
        sha = getenv("SHA", "")
        if not before or before.startswith("00000000"):
            diff_cmd = ["git", "diff", "--name-only", "HEAD~1", "HEAD"]
        else:
            diff_cmd = ["git", "diff", "--name-only", before, sha]

        try:
            diff_files = check_output(diff_cmd).decode("utf-8")
        except Exception as e:
            print(f"Ошибка git diff: {e}")
            diff_files = ""

        # если Base изменился: пересборка Base и всех браузеров
        if "Base/" in diff_files:
            print("ℹ️ обнаружены изменения в Base: пересборка Base и всех браузеров.")
            should_build_base = True
            services_to_build = browser_dirs
        else:
            for dir_name in browser_dirs:
                if f"{dir_name}/" in diff_files or "shared/" in diff_files or "scripts/" in diff_files:
                    services_to_build.append(dir_name)

    print(f"{div}ФЛАГ СБОРКИ BASE: {should_build_base}")
    print(f"ИТОГОВЫЙ СПИСОК БРАУЗЕРОВ ДЛЯ СБОРКИ:\n{services_to_build}{div}")

    with open(environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"matrix={dumps(services_to_build)}\n")
        f.write(f"should_build_base={'true' if should_build_base else 'false'}\n")


if __name__ == "__main__":
    main()