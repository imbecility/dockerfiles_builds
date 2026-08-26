"""Бенчмарк одного браузерного сервиса: скорость подключения, отклик навигации,
результаты bot-detection сайтов, скриншоты — всё складывается в JSON + PNG.

Использование (внутри CI, после того как контейнер сервиса поднят и порт проброшен):

    python3 scripts/benchmark_browsers.py \
        --service Camoufox \
        --transport ws \
        --url ws://localhost:7861/camoufox \
        --container-id <docker_id_опционально> \
        --out-dir benchmark_results/Camoufox

Транспорт "ws" — playwright.firefox.connect (Camoufox).
Транспорт "cdp" — playwright.chromium.connect_over_cdp (Clearcote, CloakBrowser).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright.sync_api import sync_playwright

from shared.detection_parsers import ALL_PARSERS
from shared.utils import wait_for_cdp_server, wait_for_ws_server


def docker_stats(container_id: str | None) -> dict:
    if not container_id:
        return {}
    try:
        out = subprocess.check_output(
            [
                "docker", "stats", "--no-stream", "--format",
                "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}",
                container_id,
            ],
            timeout=10,
        ).decode().strip()
        cpu, mem_usage, mem_perc = out.split("|")
        return {"cpu": cpu.strip(), "mem_usage": mem_usage.strip(), "mem_percent": mem_perc.strip()}
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}


def run_parser_safe(parser, page, out_dir: Path) -> dict:
    name = parser.__name__.replace("parse_", "").replace("_", "-")
    started = time.time()
    try:
        result = parser(page)
        # унификация имени
        result["site"] = result.get("site", name).replace("_", "-")
        elapsed_ms = round((time.time() - started) * 1000)
        result["elapsed_ms"] = elapsed_ms
        result["error"] = None
    except Exception as e:  # noqa: BLE001
        elapsed_ms = round((time.time() - started) * 1000)
        result = {
            "site": name, "passed": False, "score": None,
            "detail": {}, "elapsed_ms": elapsed_ms, "error": repr(e),
        }

    shot_path = out_dir / f"{name}.png"
    try:
        page.screenshot(path=str(shot_path), full_page=False, type="png", timeout=5000)
        result["screenshot"] = shot_path.name
    except Exception:
        result["screenshot"] = None

    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", required=True)
    ap.add_argument("--transport", required=True, choices=["ws", "cdp"])
    ap.add_argument("--url", required=True)
    ap.add_argument("--container-id", default=None)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--connect-timeout", type=int, default=40)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "service": args.service,
        "transport": args.transport,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "connect_time_ms": None,
        "sites": [],
        "container_stats": {},
    }

    with sync_playwright() as p:
        t0 = time.time()
        if args.transport == "ws":
            browser = wait_for_ws_server(p, args.url, timeout=args.connect_timeout)
            context = browser.new_context()
        else:
            wait_for_cdp_server(args.url, timeout=args.connect_timeout)
            browser = p.chromium.connect_over_cdp(args.url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()

        report["connect_time_ms"] = round((time.time() - t0) * 1000)
        context.set_default_timeout(30000)

        # снимок нагрузки на "холодную" сразу после подключения
        report["container_stats"]["at_connect"] = docker_stats(args.container_id)

        for parser in ALL_PARSERS:
            page = context.new_page()
            try:
                site_result = run_parser_safe(parser, page, out_dir)
            finally:
                page.close()
            report["sites"].append(site_result)
            print(f"[{'OK' if site_result['passed'] else 'FAIL'}] {site_result['site']} "
                  f"({site_result['elapsed_ms']}ms)", flush=True)

        # снимок нагрузки после полного прогона (пиковое использование памяти/CPU)
        report["container_stats"]["after_run"] = docker_stats(args.container_id)

        context.close()
        browser.close()

    passed = sum(1 for s in report["sites"] if s["passed"])
    total = len(report["sites"])
    report["summary"] = {
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total, 3) if total else 0,
        "avg_nav_ms": round(sum(s["elapsed_ms"] for s in report["sites"]) / total) if total else None,
    }

    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n📄 отчёт сохранён: {report_path}")
    print(f"✅ пройдено {passed}/{total} проверок, средняя навигация {report['summary']['avg_nav_ms']}ms")


if __name__ == "__main__":
    main()
