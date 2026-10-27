#!/usr/bin/env python3
"""Sync sitemap.xml <lastmod> (and BlogPosting dateModified) with git history.

Quality report 2026-10-24 #28: lastmod went backwards and edited pages kept old
dates. Run from the repo root before every push that touches public pages:

    python3 _growth/tools/sync-lastmod.py          # report only
    python3 _growth/tools/sync-lastmod.py --write  # apply

Date source: the last commit that changed the page's *content*. Commits whose
changed lines differ only in hrefs, dates (lastmod/dateModified) or the footer
copyright line / og:site_name meta are ignored (quality report 2026-10-26 #16). A page with
uncommitted content changes gets today's date. The date is set exactly, so it
can move backwards when an earlier bump was not a real content change.
Refuses to run on a shallow clone (dates would be wrong).
"""
import datetime, re, subprocess, sys

if subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                  capture_output=True, text=True).stdout.strip() == "true":
    sys.exit("shallow clone: run git fetch --unshallow")

TRIVIAL = [
    re.compile(r'href="[^"]*"'),
    re.compile(r'"date(Modified|Published)"\s*:\s*"[^"]*"'),
    re.compile(r"<lastmod>[^<]*</lastmod>"),
    re.compile(r'content="\d{4}-\d{2}-\d{2}[^"]*"'),
]
FOOTER = re.compile(r"(©|جميع الحقوق|الحقوق محفوظة|og:site_name)")


def norm(line):
    for r in TRIVIAL:
        line = r.sub("", line)
    return re.sub(r"\s+", " ", line).strip()


def is_trivial(diff_lines):
    minus = sorted(norm(l[1:]) for l in diff_lines if l.startswith("-") and not FOOTER.search(l))
    plus = sorted(norm(l[1:]) for l in diff_lines if l.startswith("+") and not FOOTER.search(l))
    minus = [l for l in minus if l]
    plus = [l for l in plus if l]
    return minus == plus


def changed_lines(args):
    out = subprocess.run(["git"] + args, capture_output=True, text=True).stdout
    return [l for l in out.splitlines()
            if l[:1] in "+-" and not l.startswith(("+++", "---"))]

SITE = "https://khayyal-alatraf.sa/"
write = "--write" in sys.argv
today = datetime.date.today().isoformat()


def page_date(path):
    dirty = subprocess.run(["git", "status", "--porcelain", "--", path],
                           capture_output=True, text=True).stdout.strip()
    if dirty and not is_trivial(changed_lines(["diff", "-U0", "HEAD", "--", path])):
        return today
    log = subprocess.run(["git", "log", "--format=%H %cs", "--", path],
                         capture_output=True, text=True).stdout.split("\n")
    last = None
    for row in log:
        if not row.strip():
            continue
        h, d = row.split()
        last = d
        if not is_trivial(changed_lines(["show", "--format=", "-U0", h, "--", path])):
            return d
    return last  # only trivial commits: fall back to the oldest (creation)


def loc_to_path(loc):
    rel = loc[len(SITE):] if loc.startswith(SITE) else loc
    if rel == "" or rel.endswith("/"):
        rel += "index.html"
    return rel


sm = open("sitemap.xml", encoding="utf-8").read()
changes = []


def fix_url(m):
    block = m.group(0)
    loc = re.search(r"<loc>(.*?)</loc>", block).group(1)
    path = loc_to_path(loc)
    new = page_date(path)
    cur = re.search(r"<lastmod>(.*?)</lastmod>", block)
    if not new:
        return block
    if cur and cur.group(1) == new:
        return block
    changes.append(f"sitemap {path}: {cur.group(1) if cur else '-'} -> {new}")
    if cur:
        return block.replace(cur.group(0), f"<lastmod>{new}</lastmod>")
    return block.replace("</loc>", f"</loc>\n    <lastmod>{new}</lastmod>")


sm2 = re.sub(r"<url>.*?</url>", fix_url, sm, flags=re.S)

# BlogPosting dateModified in blog/*.html
blog = subprocess.run(["git", "ls-files", "blog/*.html"],
                      capture_output=True, text=True).stdout.split()
edits = {}
for path in blog:
    html = open(path, encoding="utf-8").read()
    m = re.search(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
    new = page_date(path)
    if m and new and m.group(1) != new:
        changes.append(f"dateModified {path}: {m.group(1)} -> {new}")
        edits[path] = html.replace(m.group(0), m.group(0)[:-10] + new, 1)

for c in changes:
    print(c)
print(f"{len(changes)} change(s){'' if write else ' (dry run; add --write)'}")
if write:
    if sm2 != sm:
        open("sitemap.xml", "w", encoding="utf-8").write(sm2)
    for p, h in edits.items():
        open(p, "w", encoding="utf-8").write(h)
