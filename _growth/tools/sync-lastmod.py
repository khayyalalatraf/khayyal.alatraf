#!/usr/bin/env python3
"""Sync sitemap.xml <lastmod> and BlogPosting datePublished/dateModified with git history.

Run from the repo root before every push that touches public pages:

    python3 _growth/tools/sync-lastmod.py          # report only (dry run)
    python3 _growth/tools/sync-lastmod.py --write  # apply

Rules (quality reports 2026-10-24 #28, 2026-10-26 #16, q20261104 #13):
- Dates are the commit *author* time (%at) in Asia/Riyadh (UTC+3).
- Each commit is judged by comparing whole-file snapshots (h^:path vs h:path),
  not line diffs. The first commit of a file always counts.
- dateModified (blog/*.html BlogPosting): last commit that changed the
  *visible text* (no <head>, <script>, <style>, tags or attributes; the footer
  copyright line is ignored).
- sitemap lastmod: last commit that changed the visible text, OR the JSON-LD
  content (date fields excluded), OR the internal link targets (relative hrefs
  or hrefs to the site; hrefs with ?text= and external hrefs are ignored), OR
  the head metadata search engines read (<title>, meta description,
  og:title, og:description).
  For blog pages lastmod is never earlier than dateModified.
- datePublished, when missing, = author date of the file's first commit.
  Missing datePublished/dateModified are inserted into the BlogPosting JSON-LD.
- Uncommitted significant changes date the page today.
- Dates are set exactly, so they can move backwards after a non-content bump.
Writing only changes date fields, which both rules ignore, so a second dry run
after --write reports 0 changes.
Refuses to run on a shallow clone (dates would be wrong).
"""
import datetime, html as htmlmod, json, os, re, subprocess, sys

if subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                  capture_output=True, text=True).stdout.strip() == "true":
    sys.exit("shallow clone: run git fetch --unshallow")

SITE = "https://khayyal-alatraf.sa/"
write = "--write" in sys.argv
RIYADH = datetime.timezone(datetime.timedelta(hours=3))  # KSA, no DST
today = datetime.datetime.now(RIYADH).date().isoformat()

FOOTER = re.compile(r"(©|&copy;|جميع الحقوق|الحقوق محفوظة)")
DATE_KEYS = {"datePublished", "dateModified", "dateCreated", "uploadDate"}
LD_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I)

# ---------- git object access (one persistent cat-file process) ----------
_cat = subprocess.Popen(["git", "cat-file", "--batch"], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE)
_blob_cache = {}


def blob(rev_path):
    if rev_path in _blob_cache:
        return _blob_cache[rev_path]
    _cat.stdin.write((rev_path + "\n").encode())
    _cat.stdin.flush()
    header = _cat.stdout.readline().decode().split()
    if len(header) < 3 or header[-1] == "missing" or header[1] != "blob":
        out = None
    else:
        size = int(header[2])
        out = _cat.stdout.read(size).decode("utf-8", "replace")
        _cat.stdout.read(1)
    _blob_cache[rev_path] = out
    return out


# ---------- content signatures ----------
def visible_text(src):
    s = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    s = re.sub(r"<head\b.*?</head>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", s, flags=re.S | re.I)
    parts = []
    for seg in re.split(r"<[^>]*>", s):
        seg = re.sub(r"\s+", " ", htmlmod.unescape(seg)).strip()
        if seg and not FOOTER.search(seg):
            parts.append(seg)
    return " ".join(parts)


def _strip_dates(o):
    if isinstance(o, dict):
        return {k: _strip_dates(v) for k, v in o.items() if k not in DATE_KEYS}
    if isinstance(o, list):
        return [_strip_dates(v) for v in o]
    return o


def ld_content(src):
    out = []
    for raw in LD_RE.findall(src):
        try:
            out.append(json.dumps(_strip_dates(json.loads(raw)), sort_keys=True, ensure_ascii=False))
        except ValueError:
            raw = re.sub(r'"(%s)"\s*:\s*"[^"]*"\s*,?' % "|".join(DATE_KEYS), "", raw)
            out.append(re.sub(r"\s+", " ", raw).strip())
    return out


def internal_links(src):
    links = []
    for h in re.findall(r'\bhref\s*=\s*["\']([^"\']*)["\']', src, flags=re.I):
        h = htmlmod.unescape(h).strip()
        if "?text=" in h:
            continue  # WhatsApp prefill text
        if re.match(r"^[a-z][a-z0-9+.-]*:", h, re.I) or h.startswith("//"):
            if not h.startswith(SITE):
                continue  # external / mailto / tel
        links.append(h)
    return links


def head_meta(src):
    """<title> + meta description / og:title / og:description (q20261104 #13 audit)."""
    out = []
    m = re.search(r"<title\b[^>]*>(.*?)</title>", src, flags=re.S | re.I)
    out.append(re.sub(r"\s+", " ", htmlmod.unescape(m.group(1))).strip() if m else "")
    for tag in re.findall(r"<meta\b[^>]*>", src, flags=re.I):
        k = re.search(r'\b(?:name|property)\s*=\s*["\']([^"\']+)["\']', tag, flags=re.I)
        if not k or k.group(1).lower() not in ("description", "og:title", "og:description"):
            continue
        c = re.search(r'\bcontent\s*=\s*"([^"]*)"', tag, flags=re.I) or \
            re.search(r"\bcontent\s*=\s*'([^']*)'", tag, flags=re.I)
        out.append(k.group(1).lower() + "=" + re.sub(r"\s+", " ", htmlmod.unescape(c.group(1) if c else "")).strip())
    return tuple(sorted(out[1:]) + [out[0]])


_sig_cache = {}


def sigs(src):
    """(visible_text, full_signature) for a file snapshot (None if absent)."""
    if src is None:
        return None
    key = hash(src)
    if key not in _sig_cache:
        v = visible_text(src)
        _sig_cache[key] = (v, (v, tuple(ld_content(src)), tuple(internal_links(src)), head_meta(src)))
    return _sig_cache[key]


def differs(a, b, idx):
    if a is None or b is None:
        return a is not b
    return a[idx] != b[idx]


# ---------- per-page dates ----------
def day(ts):
    return datetime.datetime.fromtimestamp(int(ts), RIYADH).date().isoformat()


_dates_cache = {}


def page_dates(path):
    """-> (dateModified, lastmod, datePublished) or None if not tracked."""
    if path in _dates_cache:
        return _dates_cache[path]
    rows = subprocess.run(["git", "log", "--format=%H %P|%at", "--", path],
                          capture_output=True, text=True).stdout.splitlines()
    commits = []
    for r in rows:
        if not r.strip():
            continue
        hp, ts = r.split("|")
        hp = hp.split()
        commits.append((hp[0], hp[1:], int(ts)))
    if not commits:
        _dates_cache[path] = None
        return None
    # q20261105 #21: git log lists commits in graph order, so a rebased or
    # merged commit can come after an older-dated one. Judge newest author
    # time first, so the first qualifying commit is the latest date (max).
    commits.sort(key=lambda c: c[2], reverse=True)
    dm = lm = None
    head = sigs(blob("HEAD:" + path))
    if os.path.exists(path):
        work = sigs(open(path, encoding="utf-8").read())
        if differs(work, head, 0):
            dm = today
        if differs(work, head, 1):
            lm = today
    for h, parents, ts in commits:
        if dm and lm:
            break
        cur = sigs(blob(f"{h}:{path}"))
        prevs = [sigs(blob(f"{p}:{path}")) for p in parents] or [None]
        if not dm and all(differs(cur, p, 0) for p in prevs):
            dm = day(ts)
        if not lm and all(differs(cur, p, 1) for p in prevs):
            lm = day(ts)
    created = day(min(c[2] for c in commits))
    dm = dm or created
    lm = max(lm or created, dm)
    _dates_cache[path] = (dm, lm, created)
    return _dates_cache[path]


def loc_to_path(loc):
    rel = loc[len(SITE):] if loc.startswith(SITE) else loc
    if rel == "" or rel.endswith("/"):
        rel += "index.html"
    return rel


changes = []

# ---------- sitemap lastmod ----------
sm = open("sitemap.xml", encoding="utf-8").read()


def fix_url(m):
    block = m.group(0)
    path = loc_to_path(re.search(r"<loc>(.*?)</loc>", block).group(1))
    d = page_dates(path)
    if not d:
        return block
    new = d[1]
    cur = re.search(r"<lastmod>(.*?)</lastmod>", block)
    if cur and cur.group(1) == new:
        return block
    changes.append(f"sitemap {path}: {cur.group(1) if cur else '-'} -> {new}")
    if cur:
        return block.replace(cur.group(0), f"<lastmod>{new}</lastmod>")
    return block.replace("</loc>", f"</loc>\n    <lastmod>{new}</lastmod>")


sm2 = re.sub(r"<url>.*?</url>", fix_url, sm, flags=re.S)

# ---------- BlogPosting datePublished / dateModified ----------
blog = subprocess.run(["git", "ls-files", "blog/*.html"],
                      capture_output=True, text=True).stdout.split()
edits = {}
for path in blog:
    if not os.path.exists(path):
        continue
    src = open(path, encoding="utf-8").read()
    d = page_dates(path)
    if not d:
        continue
    dm_new, _, pub_new = d
    out = src
    for m in LD_RE.finditer(src):
        raw = m.group(1)
        if not re.search(r'"@type"\s*:\s*"BlogPosting"', raw):
            continue
        new_raw = raw
        mm = re.search(r'("dateModified"\s*:\s*")(\d{4}-\d{2}-\d{2})', new_raw)
        if mm:
            if mm.group(2) != dm_new:
                changes.append(f"dateModified {path}: {mm.group(2)} -> {dm_new}")
                new_raw = new_raw[:mm.start(2)] + dm_new + new_raw[mm.end(2):]
        add = []
        if not re.search(r'"datePublished"\s*:', new_raw):
            add.append(("datePublished", pub_new))
            changes.append(f"datePublished {path}: - -> {pub_new}")
        if not mm and not re.search(r'"dateModified"\s*:', new_raw):
            add.append(("dateModified", dm_new))
            changes.append(f"dateModified {path}: - -> {dm_new}")
        if add:
            t = re.search(r'([ \t]*)"@type"\s*:\s*"BlogPosting"', new_raw)
            ins = "".join(f',\n{t.group(1)}"{k}": "{v}"' for k, v in add)
            new_raw = new_raw[:t.end()] + ins + new_raw[t.end():]
        if new_raw != raw:
            json.loads(new_raw)  # must stay valid JSON
            out = out.replace(m.group(0), m.group(0).replace(raw, new_raw, 1), 1)
        break  # first BlogPosting block only
    if out != src:
        edits[path] = out

for c in changes:
    print(c)
print(f"{len(changes)} change(s){'' if write else ' (dry run; add --write)'}")
if write:
    if sm2 != sm:
        open("sitemap.xml", "w", encoding="utf-8").write(sm2)
    for p, h in edits.items():
        open(p, "w", encoding="utf-8").write(h)
    for p in edits:  # verify every ld+json block still parses
        for raw in LD_RE.findall(open(p, encoding="utf-8").read()):
            json.loads(raw)
