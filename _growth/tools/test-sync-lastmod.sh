#!/usr/bin/env bash
# Regression test for sync-lastmod.py page_dates (q20261105 #21):
# a commit with an OLDER author date placed AFTER a newer one in graph order
# (as after a rebase) must not hide the newer date. Expect dateModified = newest.
set -euo pipefail
TOOL="$(cd "$(dirname "$0")" && pwd)/sync-lastmod.py"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cd "$T"; git init -q; git config user.email t@t; git config user.name t
mkdir blog
page(){ printf '<html><head><title>t</title><script type="application/ld+json">{"@type":"BlogPosting","datePublished":"2026-01-01","dateModified":"2026-01-01"}</script></head><body><p>%s</p></body></html>\n' "$1" > blog/a.html; }
printf '<?xml version="1.0"?><urlset><url><loc>https://khayyal-alatraf.sa/blog/a.html</loc><lastmod>2026-01-01</lastmod></url></urlset>\n' > sitemap.xml
page v1; git add -A; GIT_AUTHOR_DATE='2026-01-01T12:00:00+03:00' git commit -qm c1
page v2; git add -A; GIT_AUTHOR_DATE='2026-03-10T12:00:00+03:00' git commit -qm newer-text
page v3; git add -A; GIT_AUTHOR_DATE='2026-02-05T12:00:00+03:00' git commit -qm older-date-rebased-on-top
python3 "$TOOL" --write >/dev/null
grep -q '"dateModified": *"2026-03-10"' blog/a.html || { echo "FAIL: dateModified"; cat blog/a.html; exit 1; }
grep -q '"datePublished": *"2026-01-01"' blog/a.html || { echo "FAIL: datePublished"; exit 1; }
grep -q '<lastmod>2026-03-10</lastmod>' sitemap.xml || { echo "FAIL: lastmod"; cat sitemap.xml; exit 1; }
echo PASS
