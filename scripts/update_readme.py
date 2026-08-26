"""Собирает benchmark_results/<service>/report.json со всех сервисов
и вставляет/обновляет markdown-таблицу в README.md между маркерами:

    <!-- BENCHMARK_TABLE_START -->
    ...
    <!-- BENCHMARK_TABLE_END -->

Если маркеров в README.md ещё нет — добавляет их в конец файла.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT_DIR / "benchmark_results"
README_PATH = ROOT_DIR / "README.md"

START_MARKER = "<!-- BENCHMARK_TABLE_START -->"
END_MARKER = "<!-- BENCHMARK_TABLE_END -->"

# порядок и подписи колонок для сайтов-детекторов
SITE_COLUMNS = [
    ("stealth-probe", "stealth-probe"),
    ("sannysoft", "Sannysoft"),
    ("incolumitas", "Incolumitas"),
    ("browserscan", "BrowserScan"),
    ("deviceandbrowserinfo", "DeviceAndBrowserInfo"),
    ("recaptcha_v3", "reCAPTCHA v3"),
]


def cell(site_result: dict | None) -> str:
    if site_result is None:
        return "—"
    if site_result.get("error"):
        return "⚠️ error"
    mark = "✅" if site_result["passed"] else "❌"
    score = site_result.get("score")
    return f"{mark} ({score})" if score is not None else mark


def load_reports() -> list[dict]:
    reports = []
    if not RESULTS_DIR.exists():
        return reports
    for service_dir in sorted(RESULTS_DIR.iterdir()):
        report_file = service_dir / "report.json"
        if report_file.exists():
            try:
                reports.append(json.loads(report_file.read_text(encoding="utf-8")))
            except Exception as e:  # noqa: BLE001
                print(f"⚠️ не удалось прочитать {report_file}: {e}")
    return reports


def build_table(reports: list[dict]) -> str:
    if not reports:
        return "_Нет данных бенчмарка. Запустите workflow «Stealth Benchmark»._"

    header = ["Сервис", "Connect (ms)", "Avg Nav (ms)", "Pass rate"] + [label for _, label in SITE_COLUMNS]
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * len(header)) + "|",
    ]

    for r in reports:
        sites_by_name = {s["site"]: s for s in r.get("sites", [])}
        summary = r.get("summary", {})
        row = [
            r.get("service", "?"),
            str(r.get("connect_time_ms", "—")),
            str(summary.get("avg_nav_ms", "—")),
            f"{summary.get('passed', 0)}/{summary.get('total', 0)}",
        ]
        for key, _ in SITE_COLUMNS:
            row.append(cell(sites_by_name.get(key)))
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def update_readme(table_md: str) -> None:
    if not README_PATH.exists():
        README_PATH.write_text(f"# Результаты бенчмарка\n\n{START_MARKER}\n{table_md}\n{END_MARKER}\n",
                                encoding="utf-8")
        return

    content = README_PATH.read_text(encoding="utf-8")
    block = f"{START_MARKER}\n\n## 🕵️ Результаты stealth-бенчмарка\n\n{table_md}\n\n{END_MARKER}"

    if START_MARKER in content and END_MARKER in content:
        pre = content.split(START_MARKER)[0]
        post = content.split(END_MARKER)[1]
        new_content = pre + block + post
    else:
        sep = "\n\n" if not content.endswith("\n\n") else ""
        new_content = content.rstrip("\n") + "\n" + sep + block + "\n"

    README_PATH.write_text(new_content, encoding="utf-8")


def main() -> None:
    reports = load_reports()
    table_md = build_table(reports)
    update_readme(table_md)
    print(f"README.md обновлён ({len(reports)} сервисов).")


if __name__ == "__main__":
    main()
