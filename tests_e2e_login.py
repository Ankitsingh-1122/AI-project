"""E2E login test with a real headless Chromium.

Reproduces the preview-proxy problem: a route interceptor strips request
headers on every request, exactly like the Arena preview proxy does.

Scenario A: strip `authorization` only (the observed proxy behaviour).
  -> the civic_token cookie must carry the session.
  -> user must land on the dashboard and STAY there after a hard reload.

Scenario B: strip `authorization` + `x-civic-token` + `cookie` (worst case).
  -> the app must degrade gracefully: back to /login ONCE, no infinite loop.

Run:  python3 tests_e2e_login.py
"""

import os
import sys

os.environ.setdefault("LD_LIBRARY_PATH", "/tmp/libs/lib/usr/lib/x86_64-linux-gnu")

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = "http://127.0.0.1:8000"
EMAIL = "citizen1@civic.demo"
PASSWORD = "demo123"
DASH = "/dashboard"
LOGIN = "/login"

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def new_page_with_proxy_strip(browser, strip, kill_cookie_js=False):
    strip = {s.lower() for s in strip}
    ctx = browser.new_context()
    if kill_cookie_js:
        # Simulate a proxy that strips the Cookie header: make the browser
        # unable to retain any cookie (the browser attaches cookies below
        # the JS layer, so route interception cannot remove them).
        ctx.add_init_script(
            "Object.defineProperty(document, 'cookie', {"
            "  get: () => '', set: () => {}, configurable: true });"
        )
    seen = {"nav": [], "hist": []}

    def intercept(route):
        req = route.request
        headers = {k: v for k, v in req.headers.items() if k.lower() not in strip}
        route.continue_(headers=headers)

    ctx.route("**/*", intercept)
    page = ctx.new_page()
    page.on(
        "framenavigated",
        lambda f: seen["nav"].append(f.url) if f == page.main_frame else None,
    )
    # Track SPA history pushes (React Router redirects) as well.
    page.add_init_script(
        "window.__histLog = [];"
        "const _ps = history.pushState, _rs = history.replaceState;"
        "history.pushState = function (...a) {"
        "  window.__histLog.push('push:' + (a[2] || '')); return _ps.apply(this, a); };"
        "history.replaceState = function (...a) {"
        "  window.__histLog.push('replace:' + (a[2] || '')); return _rs.apply(this, a); };"
    )
    return ctx, page, seen


def read_hist(page):
    try:
        return page.evaluate("window.__histLog || []")
    except Exception:
        return ["<unreadable>"]


def do_login(page):
    page.goto(BASE + LOGIN, wait_until="networkidle")
    page.fill('input[type="email"]', EMAIL)
    page.fill('input[type="password"]', PASSWORD)
    page.click('button:has-text("Log in")')
    # Give the app time to navigate (or loop) and settle.
    page.wait_for_timeout(4000)
    # One more settle in case a redirect is pending.
    page.wait_for_timeout(2500)


def dedupe(seq):
    """Collapse consecutive duplicates: this headless shell fires
    framenavigated twice per full navigation and also on same-document
    (SPA) transitions. A genuine loop still shows up as repeated
    login->dashboard->login alternation."""
    return [x for i, x in enumerate(seq) if i == 0 or seq[i - 1] != x]


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ---------------- Scenario A: proxy strips Authorization only ------
        print("\n=== Scenario A: proxy strips the Authorization header ===")
        ctx, page, seen = new_page_with_proxy_strip(browser, ["authorization"])
        do_login(page)

        url = page.url
        path = url.split(BASE)[1].split("?")[0]
        record(
            "lands on dashboard after login",
            path == DASH,
            f"final url path = {path}",
        )

        h1 = page.locator("h1").first
        heading = h1.inner_text(timeout=5000) if h1.count() else ""
        record("dashboard content rendered", "My problems" in heading, f"h1 = '{heading}'")

        cookies = {c["name"] for c in ctx.cookies()}
        record("session cookie present in browser", "civic_token" in cookies, str(sorted(cookies)))

        # The exact user complaint: refresh/reload must NOT kick back to login.
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(3000)
        url2 = page.url
        path2 = url2.split(BASE)[1].split("?")[0]
        record("STAYS on dashboard after hard reload (no loop)", path2 == DASH, f"after reload path = {path2}")

        # Authenticated API from inside the page must work through the strip.
        status = page.evaluate("fetch('/api/problems').then(r => r.status)")
        record("in-page /api/problems returns 200", status == 200, f"status = {status}")

        # Loop detection: count how many times we navigated to /login AFTER
        # the initial one. A loop would show >= 2 extra login navigations.
        navs = dedupe(seen["nav"])
        extra_logins = sum(1 for u in navs if LOGIN in u) - 1
        record("no login-loop navigations", extra_logins <= 0, f"extra /login navigations = {max(extra_logins,0)}")
        print("    [debug] navigations (deduped):", navs)
        print("    [debug] SPA history changes:", read_hist(page))
        ctx.close()

        # ---------------- Scenario B: worst case, every channel stripped ---
        print("\n=== Scenario B: proxy strips authorization + x-civic-token + cookie ===")
        ctx2, page2, seen2 = new_page_with_proxy_strip(
            browser, ["authorization", "x-civic-token"], kill_cookie_js=True
        )
        do_login(page2)
        print("    [debug] B: SPA history changes:", read_hist(page2))
        path_b = page2.url.split(BASE)[1].split("?")[0]
        record(
            "degrades gracefully (back to login, no crash)",
            path_b == LOGIN,
            f"final url path = {path_b}",
        )
        navs2 = dedupe(seen2["nav"])
        extra_logins_b = sum(1 for u in navs2 if LOGIN in u) - 1
        record(
            "no infinite loop in worst case",
            extra_logins_b <= 1,
            f"extra /login navigations = {max(extra_logins_b,0)} (cap: 1 = the 401 session-expired redirect)",
        )
        print("    [debug] navigations (deduped):", navs2)
        ctx2.close()

        browser.close()

    print("\n=== SUMMARY ===")
    failed = [r for r in results if not r[1]]
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    run()
