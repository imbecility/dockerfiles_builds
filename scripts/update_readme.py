# ./scripts/update_readme.py
from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT_DIR / "benchmark_results"
README_PATH = ROOT_DIR / "README.md"

START_MARKER = "<!-- BENCHMARK_TABLE_START -->"
END_MARKER = "<!-- BENCHMARK_TABLE_END -->"

SITE_COLUMNS = [
    ("stealthprobe", "stealth-probe"),
    ("sannysoft", "Sannysoft"),
    ("incolumitas", "Incolumitas"),
    ("browserscan", "BrowserScan"),
    ("deviceandbrowserinfo", "DeviceAndBrowserInfo"),
    ("recaptchav3", "reCAPTCHA v3"),
]


def norm(key: str) -> str:
    return key.lower().replace("-", "").replace("_", "")


def cell(site_result: dict | None) -> str:
    if site_result is None:
        return "—"
    if site_result.get("error"):
        return "⚠️ error"
    mark = "✅" if site_result["passed"] else "❌"
    score = site_result.get("score")
    return f"{mark} ({score})" if score is not None else mark


def extract_ram(usage_str: str | None) -> str:
    if not usage_str or "/" not in usage_str:
        return usage_str or "—"
    return usage_str.split("/")[0].strip()


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


def build_markdown(reports: list[dict]) -> str:
    if not reports:
        return "_Нет данных бенчмарка. Запустите workflow «Stealth Benchmark»._"

    # --- Таблица 1: Stealth Checks ---
    h1 = ["Сервис", "Pass Rate"] + [label for _, label in SITE_COLUMNS]
    t1_lines = [
        "### 🕵️ Stealth & Bot-Detection",
        "",
        "| " + " | ".join(h1) + " |",
        "|" + "|".join(["---"] * len(h1)) + "|",
    ]

    for r in reports:
        sites_map = {norm(s.get("site", "")): s for s in r.get("sites", [])}
        summary = r.get("summary", {})
        passed = summary.get("passed", 0)
        total = summary.get("total", 0)
        rate = f"{passed}/{total} ({round(passed / total * 100)}%)" if total else "—"

        row = [r.get("service", "?"), rate]
        for key, _ in SITE_COLUMNS:
            row.append(cell(sites_map.get(key)))
        t1_lines.append("| " + " | ".join(row) + " |")

    # --- Таблица 2: Resources & Performance ---
    h2 = ["Сервис", "Образ (сжат / диск)", "Транспорт", "Connect (ms)", "Avg Nav (ms)", "RAM (Старт)", "RAM (Пик)", "CPU (Пик)"]
    t2_lines = [
        "",
        "### ⚡ Производительность и ресурсы",
        "",
        "| " + " | ".join(h2) + " |",
        "|" + "|".join(["---"] * len(h2)) + "|",
    ]

    for r in reports:
        summary = r.get("summary", {})
        stats = r.get("container_stats", {})
        at_connect = stats.get("at_connect", {})
        after_run = stats.get("after_run", {})
        img_size = r.get("image_size", {}).get("display", "—")

        ram_init = extract_ram(at_connect.get("mem_usage"))
        ram_peak = extract_ram(after_run.get("mem_usage"))
        cpu_peak = after_run.get("cpu", "—")

        row2 = [
            r.get("service", "?"),
            img_size,
            f"`{r.get('transport', '—')}`",
            str(r.get("connect_time_ms", "—")),
            str(summary.get("avg_nav_ms", "—")),
            ram_init,
            ram_peak,
            cpu_peak,
        ]
        t2_lines.append("| " + " | ".join(row2) + " |")

    return "\n".join(t1_lines + t2_lines)


def update_readme(md_content: str) -> None:
    if not README_PATH.exists():
        README_PATH.write_text(f"# Результаты бенчмарка\n\n{START_MARKER}\n{md_content}\n{END_MARKER}\n", encoding="utf-8")
        return

    content = README_PATH.read_text(encoding="utf-8")
    block = f"{START_MARKER}\n\n## 📊 Результаты бенчмарка браузеров\n\n{md_content}\n\n{END_MARKER}"

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
    md_content = build_markdown(reports)
    update_readme(md_content)
    print(f"README.md успешно обновлён ({len(reports)} сервисов).")


if __name__ == "__main__":
    main()