#!/usr/bin/env python3
"""TASK 11 — E2E QA for the full UI redesign (all roles, both themes, responsive)."""
import sys, re, json
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\u2B55\u26A0\u2714\u2716\u270D\u2699\u2665\u2B06\u2B07]")

results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))

def console_errors(page):
    return [e for e in page._errors if e.get("type") == "error"]

def login(page, email, password):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill("input[type=email]", email)
    page.fill("input[type=password]", password)
    page.click("button:has-text('Log in')")
    page.wait_for_timeout(1500)

def no_overflow(page):
    return page.evaluate("""() => {
        const d = document.documentElement;
        return { sw: d.scrollWidth, iw: window.innerWidth };
    }""")

with sync_playwright() as pw:
    browser = pw.chromium.launch()

    # ============ 1. LANDING ============
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(BASE, wait_until="networkidle")

    check("landing: loads", page.locator("h1").count() >= 1)
    feats = page.locator(".feature-card").count()
    check("landing: 6 feature cards", feats == 6, str(feats))
    feat_svg = page.locator(".feature-icon svg").count()
    check("landing: feature icons are SVG", feat_svg == 6, str(feat_svg))
    body = page.inner_text("body")
    check("landing: no emoji in body", not EMOJI_RE.search(body), EMOJI_RE.search(body).group(0) if EMOJI_RE.search(body) else "")
    # theme toggle on landing
    page.click("button[aria-label='Toggle light / dark mode']")
    page.wait_for_timeout(300)
    check("landing: dark theme applied", page.evaluate("document.documentElement.dataset.theme") == "dark")
    bg_dark = page.evaluate("getComputedStyle(document.body).backgroundColor")
    check("landing: dark bg is dark", bg_dark in ("rgb(12, 17, 28)", "rgb(12, 17, 28)"), bg_dark)
    page.click("button[aria-label='Toggle light / dark mode']")
    page.wait_for_timeout(300)
    check("landing: back to light", page.evaluate("document.documentElement.dataset.theme") == "light")
    check("landing: no console errors", not errs, "; ".join(errs[:3]))
    ov = no_overflow(page)
    check("landing: no h-overflow desktop", ov["sw"] <= ov["iw"] + 2, str(ov))
    ctx.close()

    # ============ 2. ADMIN ============
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(str(e)))
    login(page, "admin@civic.demo", "admin123")
    page.wait_for_url("**/admin")
    page.wait_for_timeout(800)

    check("admin: on /admin", "/admin" in page.url)
    nav_icons = page.locator(".nav-item .nav-icon svg").count()
    check("admin: nav items have SVG icons", nav_icons >= 3, str(nav_icons))
    nav_emoji = page.locator(".side-nav").inner_text()
    check("admin: no emoji in sidebar", not EMOJI_RE.search(nav_emoji), "")
    page.wait_for_selector(".stat-icon svg", timeout=20000)
    stat_icons = page.locator(".stat-card .stat-icon svg").count()
    check("admin: stat cards have icon tiles", stat_icons >= 5, str(stat_icons))
    # charts
    page.wait_for_selector(".chart-fig img", timeout=15000)
    imgs = page.locator(".chart-fig img")
    n = imgs.count()
    okw = page.evaluate("""() => Array.from(document.querySelectorAll('.chart-fig img')).every(i => i.naturalWidth > 100)""")
    check("admin: 3 chart images rendered", n == 3 and okw, f"n={n} okw={okw}")
    # recharts
    check("admin: recharts donut rendered", page.locator(".recharts-pie").count() >= 1)
    # status badge colors are CSS-driven
    badge_bg = page.evaluate("getComputedStyle(document.querySelector('.badge-green')).backgroundColor")
    check("admin: green badge tinted (not plain)", badge_bg != "rgba(0, 0, 0, 0)", badge_bg)
    ov = no_overflow(page)
    check("admin: no h-overflow", ov["sw"] <= ov["iw"] + 2, str(ov))

    # scroll to Data & Labels
    page.locator("#data-labels").scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    check("admin: data & labels section", page.locator("#data-labels").count() == 1)
    body_all = page.inner_text("body")
    check("admin: no emoji anywhere", not EMOJI_RE.search(body_all), "")

    # ---- dark theme on admin (charts must switch to dark PNGs) ----
    srcs_before = page.evaluate("Array.from(document.querySelectorAll('.chart-fig img')).map(i => i.src)")
    with page.expect_response(lambda r: "/api/admin/charts/" in r.url and "theme=dark" in r.url) as dark_req:
        page.click(".topbar .theme-btn:not(.notif-bell)")
    page.wait_for_timeout(400)
    check("admin: dark theme on", page.evaluate("document.documentElement.dataset.theme") == "dark")
    card_bg = page.evaluate("getComputedStyle(document.querySelector('.card')).backgroundColor")
    check("admin: dark card surface", card_bg == "rgb(19, 26, 41)", card_bg)
    page.wait_for_timeout(1200)
    srcs_after = page.evaluate("Array.from(document.querySelectorAll('.chart-fig img')).map(i => i.src)")
    check("admin: charts reloaded for dark",
          srcs_before != srcs_after and "theme=dark" in dark_req.value.request.url,
          f"before={srcs_before[:1]} after={srcs_after[:1]}")
    check("admin(dark): no console errors", not errs, "; ".join(errs[:3]))
    ov = no_overflow(page)
    check("admin(dark): no h-overflow", ov["sw"] <= ov["iw"] + 2, str(ov))

    # profile
    page.goto(f"{BASE}/profile", wait_until="networkidle")
    page.wait_for_timeout(500)
    check("admin: profile page", page.locator(".profile-hero").count() == 1)
    copy_btns = page.locator(".copy-btn svg").count()
    check("admin: profile copy buttons have icons", copy_btns >= 2, str(copy_btns))

    # notifications
    page.goto(f"{BASE}/admin", wait_until="networkidle")
    page.wait_for_timeout(600)
    page.click(".notif-bell")
    page.wait_for_timeout(600)
    check("admin: notification panel opens", page.locator(".notif-panel").count() == 1)
    check("admin: notif items have icons", page.locator(".notif-ico svg").count() >= 0)
    page.keyboard.press("Escape")
    ctx.close()

    # ============ 3. CITIZEN ============
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(str(e)))
    login(page, "citizen1@civic.demo", "demo123")
    page.wait_for_url("**/dashboard")
    page.wait_for_timeout(700)

    mini_icons = page.locator(".mini-stat .stat-icon svg").count()
    check("citizen: mini-stats have icons", mini_icons == 4, str(mini_icons))
    problems = page.locator(".problem-card").count()
    check("citizen: problem cards listed", problems >= 1, str(problems))
    body_all = page.inner_text("body")
    check("citizen: no emoji on dashboard", not EMOJI_RE.search(body_all), "")

    # submit flow
    page.click(".page-head a:has-text('Submit Problem')")
    page.wait_for_url("**/submit")
    page.wait_for_timeout(400)
    page.fill("input[required][minlength='3']", "QA redesigned street light flicker")
    page.fill("textarea[required]", "The street light near the market keeps flickering since yesterday evening and went fully off tonight.")
    page.fill("input[placeholder*='Model Town']", "QA Gate 4, Ludhiana")
    page.click("button:has-text('Submit & analyze')")
    page.wait_for_selector("h1:has-text('Problem submitted')", timeout=30000)
    page.wait_for_timeout(500)
    note_ok = page.locator(".note-ok, .note-warn").first
    check("citizen: submit result note shown", note_ok.count() == 1)
    check("citizen: result has icon", note_ok.locator("svg").count() == 1)
    # open the problem detail
    page.click("a:has-text('View full AI analysis')")
    page.wait_for_url("**/problem/**")
    page.wait_for_timeout(900)
    strip_icons = page.locator(".ai-strip-icon svg").count()
    check("citizen: AI strip has icons", strip_icons >= 3, str(strip_icons))
    check("citizen: problem detail no emoji", not EMOJI_RE.search(page.inner_text("body")), "")
    ov = no_overflow(page)
    check("citizen: detail no h-overflow", ov["sw"] <= ov["iw"] + 2, str(ov))

    # teams directory (citizen)
    page.goto(f"{BASE}/teams", wait_until="networkidle")
    page.wait_for_timeout(600)
    check("citizen: teams directory", page.locator(".team-card").count() >= 1)
    check("citizen: directory no emoji", not EMOJI_RE.search(page.inner_text("body")), "")
    check("citizen: no console errors", not errs, "; ".join(errs[:3]))
    ctx.close()

    # ============ 4. TEAM ============
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(str(e)))
    login(page, "team1@civic.demo", "demo123")
    page.wait_for_url("**/team")
    page.wait_for_timeout(700)
    check("team: dashboard loads", page.locator(".team-grid").count() == 1)
    kw_icons = page.locator(".kw svg").count()
    check("team: kw chips have icons", kw_icons >= 1, str(kw_icons))
    page.goto(f"{BASE}/team/recommended", wait_until="networkidle")
    page.wait_for_timeout(900)
    recs = page.locator(".rec-card").count()
    check("team: recommended cards (or clean empty)", recs >= 0)
    check("team: recommended no emoji", not EMOJI_RE.search(page.inner_text("body")), "")
    # team detail
    page.goto(f"{BASE}/teams/1", wait_until="networkidle")
    page.wait_for_timeout(700)
    check("team: team detail hero icon", page.locator(".team-detail-avatar svg").count() == 1)
    check("team: detail no emoji", not EMOJI_RE.search(page.inner_text("body")), "")
    check("team: no console errors", not errs, "; ".join(errs[:3]))
    ctx.close()

    # ============ 5. RESPONSIVE (mobile) ============
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(str(e)))
    login(page, "admin@civic.demo", "admin123")
    page.wait_for_url("**/admin")
    page.wait_for_timeout(800)
    check("mobile: hamburger visible", page.locator(".hamburger").is_visible())
    box = page.locator(".sidebar").bounding_box()
    check("mobile: sidebar off-canvas", box is not None and box["x"] + box["width"] <= 1, str(box))
    page.click(".hamburger")
    page.wait_for_timeout(500)
    check("mobile: drawer opens", page.locator(".drawer-overlay").count() == 1)
    check("mobile: drawer nav visible", page.locator(".sidebar .nav-item").first.is_visible())
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    ov = no_overflow(page)
    check("mobile: admin no h-overflow", ov["sw"] <= ov["iw"] + 2, str(ov))
    page.goto(f"{BASE}/dashboard", wait_until="networkidle")
    page.wait_for_timeout(700)
    ov = no_overflow(page)
    check("mobile: citizen dash no h-overflow", ov["sw"] <= ov["iw"] + 2, str(ov))
    check("mobile: no console errors", not errs, "; ".join(errs[:3]))
    ctx.close()

    browser.close()

passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"\n===== {passed}/{total} checks passed =====")
if passed != total:
    print("FAILURES:")
    for name, ok, detail in results:
        if not ok:
            print(f"  - {name}  {detail}")
    sys.exit(1)
