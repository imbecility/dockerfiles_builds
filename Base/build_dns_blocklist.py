#!/usr/bin/env python3
import argparse
from pathlib import Path
import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
GUARANTEED_BLOCKS = {"doubleclick.net", "mc.yandex.ru"}


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--whitelist", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    sources = load_lines(args.sources)
    whitelist = set(load_lines(args.whitelist))
    blocked_domains = set(GUARANTEED_BLOCKS)

    with httpx.Client(timeout=30.0, follow_redirects=True, headers=HEADERS) as client:
        for url in sources:
            try:
                r = client.get(url)
                if r.status_code != 200:
                    continue

                for line in r.text.splitlines():
                    line = line.strip().lower()
                    if not line or line.startswith(("#", "!", ";")):
                        continue

                    parts = line.split()
                    if len(parts) > 1 and parts[0] in ("0.0.0.0", "127.0.0.1"):
                        domain = parts[1]
                    else:
                        domain = parts[0]

                    if domain.startswith("*."):
                        domain = domain[2:]
                    if domain.startswith("||"):
                        domain = domain[2:]
                    domain = domain.split("^")[0]

                    if "." in domain and not is_whitelisted(domain, whitelist):
                        blocked_domains.add(domain)
            except Exception:
                pass

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for domain in sorted(blocked_domains):
            f.write(f"address=/{domain}/0.0.0.0\n")
            f.write(f"address=/{domain}/::\n")

    print("="*42)
    print("записано в файл:")
    with open(args.output, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 10:
                break
            print(line, end="")
    print("="*42)

if __name__ == "__main__":
    main()