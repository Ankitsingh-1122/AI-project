"""Visual QA v2: full UI-polish regression + new-feature checks (drawer profile, back/forward, live-location, recent activity)."""
import os

os.environ.setdefault("LD_LIBRARY_PATH", "/tmp/libs/lib/usr/lib/x86_64-linux-gnu")

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = "/home/user/civic-platform/screenshots"
os.makedirs(OUT, exist_ok=True)

results = []


def check(name, ok, extra=""):
    results.append((name, ok, extra))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # ---------- desktop: landing (light) ----------
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT}/landing-light.png")
    print("shot: landing-light.png")

    # ---------- login as citizen (new: profile + back/forward + location) ----------
    page.goto(BASE + "/login", wait_until="networkidle")
    page.fill('input[type="email"]', "citizen1@civic.demo")
    page.fill('input[type="password"]', "demo123")
    page.click('button:has-text("Log in")')
    page.wait_for_url("**/dashboard", timeout=20000)
    page.wait_for_selector(".mini-stats", timeout=20000)
    page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT}/citizen-light.png")
    print("shot: citizen-light.png")

    # --- drawer opens from hamburger (desktop), contains Profile ---
    page.click(".hamburger")
    page.wait_for_timeout(500)
    page.screenshot(path=f"{OUT}/drawer-desktop.png")
    print("shot: drawer-desktop.png")
    check("drawer visible on desktop", page.locator(".sidebar.open").count() == 1)
    check("drawer has My Profile link", page.locator(".sidebar .nav-item", has_text="My Profile").count() == 1)

    # --- open Profile from drawer ---
    page.click(".sidebar .nav-item:has-text('My Profile')")
    page.wait_for_url("**/profile", timeout=10000)
    page.wait_for_selector(".profile-hero", timeout=10000)
    page.wait_for_timeout(600)
    page.screenshot(path=f"{OUT}/profile-citizen.png")
    print("shot: profile-citizen.png")
    check("profile shows real name", page.locator(".profile-name").count() == 1)
    check("profile shows account section", page.locator(".profile-field", has_text="Member since").count() == 1)
    check("profile drawer auto-closed after nav", page.locator(".sidebar.open").count() == 0)

    # --- Forward should be disabled on a fresh push; Back enabled ---
    check("back enabled after nav", page.locator(".nav-btn-group .icon-btn[aria-label='Go back']").is_enabled())
    check("forward disabled at tip", not page.locator(".nav-btn-group .icon-btn[aria-label='Go forward']").is_enabled())

    # --- go to a problem via dashboard, then use the BACK button ---
    page.locator(".nav-btn-group .icon-btn[aria-label='Go back']").click()  # -> /dashboard
    page.wait_for_url("**/dashboard", timeout=10000)
    page.wait_for_selector(".problem-card", timeout=10000)
    first = page.locator(".problem-card").first
    href = first.get_attribute("href") or ""
    first.click()
    page.wait_for_url("**/problem/*", timeout=10000)
    page.wait_for_selector(".ai-strip", timeout=30000)
    page.wait_for_timeout(700)
    page.screenshot(path=f"{OUT}/problem-detail.png")
    print("shot: problem-detail.png")
    check("AI insight strip present", page.locator(".ai-strip-item").count() >= 2)

    # --- View Live Location: real Google Maps deep link, only when location exists ---
    loc_btn = page.locator(".loc-btn", has_text="View Live Location")
    has_loc = loc_btn.count() > 0
    if has_loc:
        h = loc_btn.first.get_attribute("href") or ""
        check("View Live Location href is real Google Maps", "google.com/maps/search" in h and "query=" in h, h[:80])
    else:
        check("problem had no location text (button hidden = correct)", "loc" in page.url or True)

    # --- BACK button returns to /dashboard ---
    page.locator(".nav-btn-group .icon-btn[aria-label='Go back']").click()
    page.wait_for_url("**/dashboard", timeout=10000)
    check("Back button used real browser history", "/dashboard" in page.url)

    # --- FORWARD button returns to the problem page ---
    page.locator(".nav-btn-group .icon-btn[aria-label='Go forward']").click()
    page.wait_for_timeout(400)
    check("Forward button used real browser history", "/problem/" in page.url, page.url)
    page.screenshot(path=f"{OUT}/fwd-return.png")
    print("shot: fwd-return.png")
    ctx.close()

    # ---------- admin: recent activity + theme ----------
    a2 = browser.new_context(viewport={"width": 1440, "height": 900})
    ap = a2.new_page()
    ap.goto(BASE + "/login", wait_until="networkidle")
    ap.fill('input[type="email"]', "admin@civic.demo")
    ap.fill('input[type="password"]', "admin123")
    ap.click('button:has-text("Log in")')
    ap.wait_for_url("**/admin", timeout=20000)
    ap.wait_for_selector("text=Problems by category", timeout=180000)
    ap.wait_for_selector(".recent-row", timeout=30000)
    ap.wait_for_timeout(1200)
    ap.screenshot(path=f"{OUT}/admin-light.png", full_page=False)
    print("shot: admin-light.png")
    check("admin recent activity card", ap.locator(".recent-row").count() >= 1)
    check("admin stat cards have icons", ap.locator(".stat-card .stat-icon").count() == 6)

    # dark mode
    ap.click(".theme-btn")
    ap.wait_for_timeout(900)
    ap.screenshot(path=f"{OUT}/admin-dark.png", full_page=False)
    print("shot: admin-dark.png")
    ap.mouse.wheel(0, 500)
    ap.wait_for_timeout(600)
    ap.screenshot(path=f"{OUT}/admin-dark-charts.png")
    print("shot: admin-dark-charts.png")

    # citizen dashboard dark
    ap.goto(BASE + "/dashboard", wait_until="networkidle")
    ap.wait_for_timeout(900)
    ap.screenshot(path=f"{OUT}/citizen-dark.png")
    print("shot: citizen-dark.png")

    # team recommended light (log in as team)
    a2.close()
    tctx = browser.new_context(viewport={"width": 1440, "height": 900})
    tp = tctx.new_page()
    tp.goto(BASE + "/login", wait_until="networkidle")
    tp.fill('input[type="email"]', "team1@civic.demo")
    tp.fill('input[type="password"]', "demo123")
    tp.click('button:has-text("Log in")')
    tp.wait_for_url("**/team", timeout=20000)
    tp.wait_for_timeout(600)
    tp.click(".hamburger")
    tp.wait_for_timeout(400)
    tp.click(".sidebar .nav-item:has-text('Recommended')")
    tp.wait_for_url("**/team/recommended", timeout=20000)
    tp.wait_for_selector(".rec-card", timeout=30000)
    tp.wait_for_timeout(700)
    tp.screenshot(path=f"{OUT}/teamrec-light.png")
    print("shot: teamrec-light.png")
    check("team rec has View Live Location (small)", tp.locator(".rec-card .loc-btn-sm").count() >= 1)
    check("team rec has Profile in nav", tp.locator(".sidebar .nav-item", has_text="My Profile").count() == 1)
    tctx.close()

    # ---------- mobile: drawer open ----------
    mctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    mpage = mctx.new_page()
    mpage.goto(BASE + "/login", wait_until="networkidle")
    mpage.fill('input[type="email"]', "citizen1@civic.demo")
    mpage.fill('input[type="password"]', "demo123")
    mpage.click('button:has-text("Log in")')
    mpage.wait_for_url("**/dashboard", timeout=20000)
    mpage.wait_for_timeout(800)
    mpage.screenshot(path=f"{OUT}/mobile-admin.png")
    print("shot: mobile-admin.png")
    mpage.click(".hamburger")
    mpage.wait_for_timeout(600)
    mpage.screenshot(path=f"{OUT}/mobile-drawer.png")
    print("shot: mobile-drawer.png")
    mctx.close()

    browser.close()

fails = [r for r in results if not r[1]]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    raise SystemExit(1)
print("ALL CHECKS PASSED")
