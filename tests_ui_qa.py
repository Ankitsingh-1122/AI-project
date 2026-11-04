"""Visual QA: screenshot the new UI in light & dark themes + mobile drawer."""
import os

os.environ.setdefault("LD_LIBRARY_PATH", "/tmp/libs/lib/usr/lib/x86_64-linux-gnu")

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = "/home/user/civic-platform/screenshots"
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # ---------- desktop: landing (light) ----------
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(700)  # let entrance animations settle
    page.screenshot(path=f"{OUT}/landing-light.png")
    print("1. landing-light.png")

    # ---------- desktop: login as admin -> /admin ----------
    page.goto(BASE + "/login", wait_until="networkidle")
    page.fill('input[type="email"]', "admin@civic.demo")
    page.fill('input[type="password"]', "admin123")
    page.click('button:has-text("Log in")')
    page.wait_for_url("**/admin", timeout=20000)
    # The AI/ML evaluation endpoint is slow on a cold model — wait for real content.
    page.wait_for_selector("text=Problems by category", timeout=180000)
    page.wait_for_timeout(1500)  # stat-card stagger + chart entrance
    page.screenshot(path=f"{OUT}/admin-light.png", full_page=False)
    print("2. admin-light.png")

    # ---------- desktop: toggle to dark ----------
    page.click(".theme-btn")
    page.wait_for_timeout(900)
    page.screenshot(path=f"{OUT}/admin-dark.png", full_page=False)
    print("3. admin-dark.png")

    # scroll to charts in dark mode
    page.mouse.wheel(0, 500)
    page.wait_for_timeout(600)
    page.screenshot(path=f"{OUT}/admin-dark-charts.png")
    print("4. admin-dark-charts.png")

    # citizen dashboard dark (sidebar sections check)
    page.goto(BASE + "/dashboard", wait_until="networkidle")
    page.wait_for_timeout(900)
    page.screenshot(path=f"{OUT}/citizen-dark.png")
    print("5. citizen-dark.png")

    # team recommended light (nav group check)
    page.click(".theme-btn")  # back to light
    page.goto(BASE + "/team/recommended", wait_until="networkidle")
    page.wait_for_timeout(900)
    page.screenshot(path=f"{OUT}/teamrec-light.png")
    print("6. teamrec-light.png")
    ctx.close()

    # ---------- mobile: drawer open ----------
    mctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    mpage = mctx.new_page()
    mpage.goto(BASE + "/login", wait_until="networkidle")
    mpage.fill('input[type="email"]', "admin@civic.demo")
    mpage.fill('input[type="password"]', "admin123")
    mpage.click('button:has-text("Log in")')
    mpage.wait_for_url("**/admin", timeout=20000)
    mpage.wait_for_timeout(800)
    mpage.screenshot(path=f"{OUT}/mobile-admin.png")
    print("7. mobile-admin.png")
    mpage.click(".hamburger")
    mpage.wait_for_timeout(600)
    mpage.screenshot(path=f"{OUT}/mobile-drawer.png")
    print("8. mobile-drawer.png")
    mctx.close()

    browser.close()
print("ALL SCREENSHOTS DONE")
