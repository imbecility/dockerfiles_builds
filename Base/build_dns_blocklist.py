import argparse
import re
from pathlib import Path
import httpx

DOMAIN_REGEX = re.compile(r"^(?:0\.0\.0\.0|127\.0\.0\.1|\|\|)?\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
}

def load_lines(file_path: Path) -> list[str]:
    if not file_path.exists():
        return []
    return [
        line.strip().lower()
        for line in file_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

def is_whitelisted(domain: str, whitelist: set[str]) -> bool:
    if domain in whitelist:
        return True
    return any(domain.endswith("." + w) for w in whitelist)

def main():
    parser = argparse.ArgumentParser(description="DNS Blocklist Builder with Whitelist support")
    parser.add_argument("--sources", required=True, type=Path, help="Файл со списком URL источников")
    parser.add_argument("--whitelist", required=True, type=Path, help="Файл со списком исключений (whitelist)")
    parser.add_argument("--output", required=True, type=Path, help="Путь для итогового hosts-файла")
    args = parser.parse_args()

    sources = load_lines(args.sources)
    whitelist = set(load_lines(args.whitelist))

    print(f"[*] Загружено правил Whitelist: {len(whitelist)}")
    print(f"[*] Источников для скачивания: {len(sources)}")

    blocked_domains = set()

    with httpx.Client(timeout=30.0, follow_redirects=True, headers=HEADERS) as client:
        for url in sources:
            try:
                print(f"  → Загрузка: {url}")
                r = client.get(url)
                if r.status_code != 200:
                    print(f"  [!] Пропуск {url}: HTTP {r.status_code}")
                    continue

                for line in r.text.splitlines():
                    line = line.strip()
                    if not line or line.startswith(("#", "!", ";")):
                        continue
                    m = DOMAIN_REGEX.match(line)
                    if m:
                        domain = m.group(1).lower().rstrip("^")
                        if not is_whitelisted(domain, whitelist):
                            blocked_domains.add(domain)
            except Exception as e:
                print(f"  [!] Ошибка загрузки {url}: {e}")

    print(f"[*] Собрано уникальных доменов: {len(blocked_domains)}")

    # Запись в формате /etc/hosts (0.0.0.0 domain)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for domain in sorted(blocked_domains):
            f.write(f"0.0.0.0 {domain}\n")

    print(f"[✓] Файл успешно сохранен в: {args.output}")

if __name__ == "__main__":
    main()