"""End-to-end browser journey (Phase 5 verification).

Requires: API on http://127.0.0.1:8000 and frontend on http://[::1]:5173
(or set FRONTEND_URL). Skips gracefully when servers are not reachable.
Run: .venv/bin/python tests/test_e2e.py
"""
from __future__ import annotations

import os
import sys
import urllib.request

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://[::1]:5173")
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")


def servers_up() -> bool:
    try:
        urllib.request.urlopen(API_URL + "/api/health", timeout=5)
        urllib.request.urlopen(FRONTEND_URL + "/", timeout=5)
        return True
    except Exception:
        return False


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        check.failed = True


check.failed = False


def main() -> int:
    if not servers_up():
        print("SKIP: servers not reachable "
              f"(API {API_URL}, frontend {FRONTEND_URL})")
        return 0
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.firefox.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))
        try:
            # 1. Landing
            page.goto(FRONTEND_URL + "/", wait_until="networkidle")
            check("landing: heading", "THE UNMAPPED" in page.content())
            check("landing: CTA", page.get_by_text("Discover my skills").count() > 0)
            page.get_by_text("Discover my skills").first.click()

            # 2. Discover
            page.wait_for_url("**/discover", timeout=10000)
            page.get_by_text("Try an example description").click()
            ta = page.locator("#desc")
            check("discover: example filled", ta.input_value().startswith("For two years"))
            page.get_by_role("button", name="Analyse my description").click()

            # 3. Results (model is pre-built; allow 60 s)
            try:
                page.wait_for_url("**/results", timeout=60000)
            except Exception:
                err_text = page.locator('[role="alert"]').all_text_contents()
                print("FORM ERRORS:", err_text)
                print("CONSOLE:", console_errors[:5])
                page.screenshot(path="/tmp/e2e_fail.png")
                raise
            # wait for the prediction cards to render before snapshotting
            page.wait_for_selector("text=model score", timeout=30000)
            body = page.content()
            check("results: Financial Accounting", "Financial Accounting" in body)
            check("results: skill IDs shown", "SKL-" in body)
            check("results: direct evidence", "direct match" in body.lower())
            check("results: uncalibrated label", "uncalibrated" in body.lower())
            check("results: confidence badge",
                  "high confidence" in body.lower() or "needs review" in body.lower())
            page.get_by_text("Plan a career move").click()

            # 4. Career
            page.wait_for_url("**/career", timeout=15000)
            check("career: skills carried over",
                  page.locator("text=Financial Accounting").count() > 0)
            page.locator("#occ").fill("Accountants and Auditors")
            page.locator("#occ").press("Enter")
            page.get_by_role("button", name="Show my transition plan").click()
            page.wait_for_selector("text=Prioritized learning pathway", timeout=120000)
            body = page.content()
            check("career: matched/missing", "Matching skills" in body and "Missing skills" in body)
            check("career: heuristic not probability", "not a probability" in body.lower())
            check("career: pathway steps", "priority" in body.lower())
            check("career: 12-month unavailable",
                  "unavailable" in body.lower() and "Twelve-month feasibility" in body)

            # 5. Dashboard
            page.goto(FRONTEND_URL + "/dashboard", wait_until="networkidle")
            page.wait_for_selector("svg", timeout=30000)
            body = page.content()
            check("dashboard: charts rendered", page.locator("svg").count() >= 2,
                  f"{page.locator('svg').count()} svg elements")
            check("dashboard: caveats", "time series" in body.lower())
            check("dashboard: source", "Indian Skills Dataset" in body)
            page.get_by_label("Filter domains").fill("Health")
            page.wait_for_timeout(800)
            check("dashboard: filter works",
                  "Healthcare" in page.content() or "No domains match" in page.content())

            # console errors
            errors: list[str] = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(1500)
            check("no console errors on dashboard", len(errors) == 0, "; ".join(errors[:3]))
        finally:
            browser.close()
    print("E2E:", "ALL PASS" if not check.failed else "FAILURES PRESENT")
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
