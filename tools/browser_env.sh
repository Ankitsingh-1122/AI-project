#!/usr/bin/env bash
# Rebuilds the headless-Chromium test environment (user-space, no root).
# Playwright's chromium headless shell needs 8 system libs; we extract them
# from Debian .debs into /tmp/libs (rebuilt here because /tmp is not persisted).
set -e

LIBDIR=/tmp/libs
mkdir -p $LIBDIR/debs $LIBDIR/lib

# 1) Current package filenames from the live trixie index
cd $LIBDIR
curl -sf http://deb.debian.org/debian/dists/trixie/main/binary-amd64/Packages.xz -o live.pkgs.xz
xz -d -f live.pkgs.xz
python3 - <<'EOF' > filenames.txt
import re
want = {"libxdamage1", "libasound2t64", "libatk1.0-0t64", "libatk-bridge2.0-0t64",
        "libatspi2.0-0t64", "libnspr4", "libnss3", "libxkbcommon0"}
blocks = open("live.pkgs").read().split("\n\n")
for b in blocks:
    m = re.search(r"^Package: (.+)$", b, re.M)
    if m and m.group(1) in want:
        fn = re.search(r"^Filename: (.+)$", b, re.M).group(1)
        print(fn)
EOF

# 2) Download + extract
cd $LIBDIR/debs
while read -r f; do
  [ -z "$f" ] && continue
  [ -f "$(basename "$f")" ] || curl -sf "http://deb.debian.org/debian/$f" -O
done < ../filenames.txt
for d in *.deb; do dpkg -x "$d" $LIBDIR/lib; done

# 3) Ensure playwright has the browser (re-download if wiped)
python3 -m playwright install chromium 2>&1 | tail -1 || true

# 4) Verify
CHROME=$(find /home/user/.cache/ms-playwright -name "chrome-headless-shell" -type f | head -1)
MISSING=$(LD_LIBRARY_PATH=$LIBDIR/lib/usr/lib/x86_64-linux-gnu ldd "$CHROME" 2>/dev/null | grep -c "not found" || true)
echo "missing libs: $MISSING"
LD_LIBRARY_PATH=$LIBDIR/lib/usr/lib/x86_64-linux-gnu python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto('data:text/html,<h1>ok</h1>')
    print('BROWSER SMOKE:', pg.text_content('h1'))
    b.close()
"
