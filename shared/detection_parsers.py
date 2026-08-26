from __future__ import annotations

import re
import time
from typing import Any

from playwright.sync_api import Page

STEALTH_PROBE_URL = "https://iuseonly-bots.static.hf.space/index.html"


def parse_stealth_probe(page: Page) -> dict[str, Any]:
    page.goto(STEALTH_PROBE_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector("#jsonResult", timeout=15000)
    data = page.evaluate("window.__stealthProbeResult || {}") or {}
    is_bot = bool(data.get("isBot", False))
    return {
        "site": "stealth-probe",
        "passed": not is_bot if data else False,
        "score": None,
        "detail": data.get("details", {}),
    }


def parse_sannysoft(page: Page) -> dict[str, Any]:
    page.goto("https://bot.sannysoft.com", wait_until="networkidle", timeout=30000)
    time.sleep(3)
    results = page.evaluate(
        """() => {
            const rows = document.querySelectorAll('table tr');
            const failed = [];
            let total = 0;
            rows.forEach(r => {
                const cells = r.querySelectorAll('td');
                if (cells.length >= 2) {
                    total++;
                    const cls = cells[1].className || '';
                    if (cls.includes('failed')) failed.push(cells[0].innerText.trim());
                }
            });
            return {total, failed};
        }"""
    )
    failed = results["failed"]
    total = results["total"] or 1
    score = round(1 - len(failed) / total, 3)
    # score >= 0.95 считается успешным прохождением (учитывая кросс-браузерные различия Gecko/Chromium)
    return {
        "site": "sannysoft",
        "passed": score >= 0.95,
        "score": score,
        "detail": {"failed_checks": failed, "total_checks": results["total"]},
    }


def parse_incolumitas(page: Page) -> dict[str, Any]:
    KNOWN_ACCEPTABLE = {"WEBDRIVER", "connectionRTT"}
    page.goto("https://bot.incolumitas.com", wait_until="networkidle", timeout=30000)
    time.sleep(12)
    results = page.evaluate(
        """() => {
            const text = document.body.innerText;
            const okMatches = text.match(/"\\w+":\\s*"OK"/g) || [];
            const failMatches = text.match(/"\\w+":\\s*"FAIL"/g) || [];
            const failedTests = failMatches.map(m => m.match(/"(\\w+)"/)[1]);
            return {passed: okMatches.length, failed: failMatches.length, failedTests};
        }"""
    )
    failed_names = results["failedTests"]
    real_failures = [f for f in failed_names if f not in KNOWN_ACCEPTABLE]
    total = results["passed"] + results["failed"] or 1
    score = round(1 - len(real_failures) / total, 3)
    return {
        "site": "incolumitas",
        "passed": score >= 0.95,
        "score": score,
        "detail": {"failed": failed_names, "ignored_known": list(KNOWN_ACCEPTABLE)},
    }


def parse_browserscan(page: Page) -> dict[str, Any]:
    page.goto("https://www.browserscan.net/bot-detection", wait_until="networkidle", timeout=30000)
    time.sleep(5)
    results = page.evaluate(
        """() => {
            const text = document.body.innerText;
            const normalMatches = text.match(/Normal/g);
            const abnormalMatches = text.match(/Abnormal/g);
            return {
                normal: normalMatches ? normalMatches.length : 0,
                abnormal: abnormalMatches ? abnormalMatches.length : 0
            };
        }"""
    )
    total = results["normal"] + results["abnormal"] or 1
    return {
        "site": "browserscan",
        "passed": results["abnormal"] == 0,
        "score": round(results["normal"] / total, 3),
        "detail": results,
    }


def parse_device_and_browser_info(page: Page) -> dict[str, Any]:
    page.goto(
        "https://deviceandbrowserinfo.com/are_you_a_bot",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    time.sleep(8)
    raw = page.evaluate(
        """() => {
            const el = document.getElementById('jsonResult');
            return el ? el.textContent : null;
        }"""
    )
    if not raw:
        return {"site": "deviceandbrowserinfo", "passed": False, "score": None,
                 "detail": {"error": "jsonResult element not found"}}

    is_bot_match = re.search(r'"isBot":\s*(true|false)', raw)
    is_bot = is_bot_match and is_bot_match.group(1) == "true"

    flags = {}
    for key in (
        "hasBotUserAgent", "hasWebdriverTrue", "hasWebdriverInFrameTrue", "isPlaywright",
        "hasInconsistentChromeObject", "isPhantom", "isNightmare", "isSequentum",
        "isSeleniumChromeDefault", "isHeadlessChrome", "isWebGLInconsistent",
        "hasInconsistentWebGLShaderLang", "hasInconsistentTimingResolution",
        "isAutomatedWithCDP", "isAutomatedWithCDPInWebWorker", "hasInconsistentClientHints",
        "hasInconsistentGPUFeatures", "isIframeOverridden", "hasInconsistentWorkerValues",
        "hasHighHardwareConcurrency", "hasHeadlessChromeDefaultScreenResolution",
        "hasSuspiciousWeakSignals",
    ):
        m = re.search(r'"%s":\s*(true|false)' % key, raw)
        if m:
            flags[key] = m.group(1) == "true"

    flagged = [k for k, v in flags.items() if v]
    return {
        "site": "deviceandbrowserinfo",
        "passed": not is_bot,
        "score": None,
        "detail": {"isBot": bool(is_bot), "flagged": flagged},
    }


def parse_recaptcha_v3(page: Page) -> dict[str, Any]:
    page.goto(
        "https://recaptcha-demo.appspot.com/recaptcha-v3-request-scores.php",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    time.sleep(8)
    results = page.evaluate(
        """() => {
            const text = document.body.innerText;
            const scoreMatch = text.match(/"score":\\s*(\\d+\\.\\d+)/);
            return {score: scoreMatch ? parseFloat(scoreMatch[1]) : null};
        }"""
    )
    score = results["score"]
    return {
        "site": "recaptcha_v3",
        "passed": score is not None and score >= 0.7,
        "score": score,
        "detail": {"raw_score": score},
    }


ALL_PARSERS = [
    parse_stealth_probe,
    parse_sannysoft,
    parse_incolumitas,
    parse_browserscan,
    parse_device_and_browser_info,
    parse_recaptcha_v3,
]