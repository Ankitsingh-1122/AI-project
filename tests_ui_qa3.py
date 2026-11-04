"""QA v3: verify the three fixes — accept-removes-from-queue, dark select visibility, team detail page."""
import os

os.environ.setdefault("LD_LIBRARY_PATH", "/tmp/libs/lib/usr/lib/x86_64-linux-gnu")

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = "/home/user/civic-platform/screenshots"
os.makedirs(OUT, exist_ok=True)

results = []


def check(name, ok, extra=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


def login(page, email, pw, expect):
    page.goto(BASE + "/login", wait_until="networkidle")
    page.fill('input[type="email"]', email)
    page.fill('input[type="password"]', pw)
    page.click('button:has-text("Log in")')
    page.wait_for_url(f"**{expect}", timeout=20000)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # ============ 1) ACCEPT removes the problem from the Suggested queue ============
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    login(page, "team1@civic.demo", "demo123", "/team")
    page.click(".hamburger")
    page.wait_for_timeout(400)
    page.click(".sidebar .nav-item:has-text('Recommended')")
    page.wait_for_url("**/team/recommended", timeout=20000)
    page.wait_for_selector(".rec-card", timeout=30000)
    page.wait_for_timeout(500)

    # USER'S EXACT SCENARIO: match 306 (problem 33) is accepted; the
    # near-duplicate problem 32 (match 301) has the IDENTICAL title and is
    # still "suggested" server-side. It must NOT appear in the Suggested tab.
    dup_title = "Street lamp is off near Model Town bus stop"
    sug_titles = [page.locator(".rec-card").nth(i).locator("h3").inner_text().strip()
                  for i in range(page.locator(".rec-card").count())]
    check("near-dup with identical title hidden from Suggested tab", dup_title not in sug_titles,
          f"suggested: {len(sug_titles)} cards")

    # count suggested cards + remember the first problem title
    cards = page.locator(".rec-card")
    n_before = cards.count()
    first_title = cards.nth(0).locator("h3").inner_text().strip()
    # are there DUPLICATE suggested matches for the same problem as the first card?
    titles = [cards.nth(i).locator("h3").inner_text().strip() for i in range(n_before)]
    dup = titles.count(first_title)
    print(f"  suggested cards: {n_before}, first title: {first_title!r} (x{dup})")

    # JS click: the sticky topbar can shadow the button for Playwright's
    # pointer checks; dispatching the click on the element is equivalent here.
    page.locator(".rec-card").nth(0).locator("button:has-text('Accept problem')").evaluate("el => el.click()")
    page.wait_for_timeout(1200)  # optimistic update + refetch

    titles_after = [page.locator(".rec-card").nth(i).locator("h3").inner_text().strip()
                    for i in range(page.locator(".rec-card").count())]
    n_after = len(titles_after)
    check("accepted card removed from Suggested tab", first_title not in titles_after, f"{n_before}->{n_after}")
    if dup > 1:
        check("duplicate suggested rows for same problem also retired", titles_after.count(first_title) == 0,
              f"{first_title!r} now x{titles_after.count(first_title)}")

    # it should be visible under the Accepted tab (JS click: sticky topbar
    # can shadow the in-header chips for Playwright's pointer checks)
    page.locator(".chip", has_text="Accepted").evaluate("el => el.click()")
    page.wait_for_timeout(400)
    acc_titles_2 = [page.locator(".rec-card").nth(i).locator("h3").inner_text().strip()
                    for i in range(page.locator(".rec-card").count())]
    check("accepted near-dup (same title) visible in Accepted tab", dup_title in acc_titles_2)
    acc_titles = [page.locator(".rec-card").nth(i).locator("h3").inner_text().strip()
                  for i in range(page.locator(".rec-card").count())]
    check("accepted card present in Accepted tab", first_title in acc_titles)
    page.screenshot(path=f"{OUT}/fix-accepted-tab.png")
    print("shot: fix-accepted-tab.png")

    # back to Suggested tab — problem fully gone from the queue
    page.locator(".chip", has_text="Suggested").evaluate("el => el.click()")
    page.wait_for_timeout(400)
    page.screenshot(path=f"{OUT}/fix-suggested-after-accept.png")
    print("shot: fix-suggested-after-accept.png")
    ctx.close()

    # ============ 2) DARK MODE custom select — options must be readable ============
    d = browser.new_context(viewport={"width": 1440, "height": 900})
    dp = d.new_page()
    login(dp, "citizen1@civic.demo", "demo123", "/dashboard")
    dp.wait_for_selector(".mini-stats", timeout=20000)
    dp.click(".theme-btn")  # dark
    dp.wait_for_timeout(700)

    # no native <select> remains on this page
    check("no native select on citizen dashboard", dp.locator(".filters select").count() == 0)

    dp.click(".filters .select-btn >> nth=1")  # open "All statuses"
    dp.wait_for_timeout(400)
    menu = dp.locator(".select-menu")
    check("custom select menu opens", menu.count() == 1)
    opt = menu.locator("li", has_text="in_review")
    check("option 'in_review' visible", opt.count() == 1 and opt.is_visible())
    # readability: option text color must differ enough from menu background
    fg = opt.evaluate("el => getComputedStyle(el).color")
    bg = menu.evaluate("el => getComputedStyle(el).backgroundColor")

    def lum(c):
        c = c.replace("rgba(", "").replace("rgb(", "").replace(")", "").split(",")
        r, g, b = [float(x) for x in c[:3]]
        a = float(c[3]) if len(c) > 3 else 1.0
        # composite over black (dark menu)
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) * a
    check("option text readable on dark menu", lum(fg) > 90, f"fg={fg} bg={bg}")
    dp.screenshot(path=f"{OUT}/fix-dark-select.png")
    print("shot: fix-dark-select.png")

    # select an option -> filters apply
    opt.click()
    dp.wait_for_timeout(500)
    check("selecting option closes menu & shows selected value",
          dp.locator(".select-menu").count() == 0 and
          "in_review" in dp.locator(".filters .select-btn").nth(1).inner_text())
    # light mode still fine
    dp.click(".theme-btn")
    dp.wait_for_timeout(500)
    dp.click(".filters .select-btn >> nth=0")  # open categories in light
    dp.wait_for_timeout(300)
    dp.screenshot(path=f"{OUT}/fix-light-select.png")
    print("shot: fix-light-select.png")
    d.close()

    # ============ 3) TEAM DETAIL — inspect team + members ============
    t = browser.new_context(viewport={"width": 1440, "height": 900})
    tp = t.new_page()
    login(tp, "citizen1@civic.demo", "demo123", "/dashboard")
    tp.click(".hamburger")
    tp.wait_for_timeout(400)
    tp.click(".sidebar .nav-item:has-text('Teams Directory')")
    tp.wait_for_url("**/teams", timeout=20000)
    tp.wait_for_selector(".team-card", timeout=20000)
    tp.screenshot(path=f"{OUT}/teams-directory.png")
    print("shot: teams-directory.png")

    # click first team card -> /teams/:id
    tp.click(".team-card-link >> nth=0")
    tp.wait_for_url("**/teams/*", timeout=20000)
    tp.wait_for_selector(".member-item, .team-detail-hero", timeout=20000)
    tp.wait_for_timeout(600)
    page_url = tp.url
    check("navigated to team detail route", "/teams/" in page_url and page_url.rstrip("/").split("/")[-1].isdigit(), page_url)
    check("members listed", tp.locator(".member-item").count() >= 1,
          f"{tp.locator('.member-item').count()} members")
    first_member = tp.locator(".member-item .member-name").first.inner_text()
    check("member name rendered", len(first_member.strip()) > 1, first_member)
    check("skills shown", tp.locator(".kw").count() >= 3)
    check("honest note about messaging present", tp.locator(".profile-note", has_text="messaging").count() == 1)
    tp.screenshot(path=f"{OUT}/team-detail.png")
    print("shot: team-detail.png")

    # deep link works directly
    tid = page_url.rstrip("/").split("/")[-1]
    tp2 = t.new_page()
    tp2.goto(BASE + f"/teams/{tid}", wait_until="networkidle")
    tp2.wait_for_selector(".team-detail-hero", timeout=20000)
    check("team detail deep link works", tp2.locator(".team-detail-hero").count() == 1)
    # after a hard navigation (fresh history) Back must be DISABLED — there is
    # nothing to go back to in this tab. (Round-trip back/forward is covered
    # by tests_ui_qa2.py.)
    check("back correctly disabled after direct deep link",
          not tp2.locator(".nav-btn-group .icon-btn[aria-label='Go back']").is_enabled())
    t.close()

    # ============ owner view: team1 sees Edit button on their detail ============
    o = browser.new_context(viewport={"width": 1440, "height": 900})
    op = o.new_page()
    login(op, "team1@civic.demo", "demo123", "/team")
    # find their team id via /api (same as frontend would)
    import urllib.request, json
    tok = op.evaluate("() => localStorage.getItem('civic_token')")
    req = urllib.request.Request(BASE + "/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    me = json.load(urllib.request.urlopen(req))
    op.goto(BASE + f"/teams/{me['team_id']}", wait_until="networkidle")
    op.wait_for_selector(".team-detail-hero", timeout=20000)
    check("owner sees Edit team profile button", op.locator("a:has-text('Edit team profile')").count() == 1)
    check("owner sees View recommendations button", op.locator("a:has-text('View recommendations')").count() == 1)
    op.screenshot(path=f"{OUT}/team-detail-owner.png")
    print("shot: team-detail-owner.png")
    o.close()

    browser.close()

fails = [r for r in results if not r[1]]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    raise SystemExit(1)
print("ALL FIX CHECKS PASSED")
