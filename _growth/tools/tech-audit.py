import os,re,json,sys,glob
from html.parser import HTMLParser
root=sys.argv[1]; os.chdir(root)
pages=sorted([p for p in glob.glob('*.html')+glob.glob('blog/*.html') if not p.startswith('google')])
sm=open('sitemap.xml').read()
smurls=set(re.findall(r'<loc>([^<]+)</loc>',sm))
base='https://khayyal-alatraf.sa/'
issues={}
def add(k,v): issues.setdefault(k,[]).append(v)
titles={};descs={}
for p in pages:
    h=open(p,encoding='utf-8').read()
    t=re.findall(r'<title>(.*?)</title>',h,re.S)
    d=re.findall(r'<meta\s+name="description"\s+content="([^"]*)"',h)
    c=re.findall(r'<link\s+rel="canonical"\s+href="([^"]+)"',h)
    h1=len(re.findall(r'<h1[\s>]',h))
    noindex='noindex' in h
    if not t: add('no_title',p)
    else:
        tl=len(t[0].strip()); titles.setdefault(t[0].strip(),[]).append(p)
        if tl>65: add('title_long(>65)',f'{p} ({tl})')
    if not d: add('no_description',p)
    else:
        dl=len(d[0]); descs.setdefault(d[0],[]).append(p)
        if dl>160 or dl<70: add('desc_len(70-160)',f'{p} ({dl})')
    if not c: add('no_canonical',p)
    else:
        exp=base+('' if p=='index.html' else p)
        if c[0] not in (exp, exp.replace('.html','')): add('canonical_mismatch',f'{p} -> {c[0]}')
    if h1!=1: add('h1_count!=1',f'{p} ({h1})')
    imgs=re.findall(r'<img\b[^>]*>',h)
    for im in imgs:
        if 'alt=' not in im: add('img_no_alt',p)
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>',h,re.S):
        try: json.loads(m)
        except Exception as e: add('jsonld_invalid',f'{p}: {str(e)[:50]}')
    if not noindex:
        u=base+('' if p=='index.html' else p)
        if u not in smurls: add('not_in_sitemap',p)
    for href in re.findall(r'href="([^"#?]+)',h):
        if href.startswith(('http','mailto','tel','//','data:','javascript')): 
            if href.startswith(base): href='/'+(href[len(base):] or 'index.html')
            else: continue
        tgt=os.path.normpath(os.path.join(os.path.dirname(p),href.lstrip('/') if not href.startswith('/') else '')) if not href.startswith('/') else href.lstrip('/')
        if tgt in ('','.'): tgt='index.html'
        if tgt.endswith('/'): tgt+='index.html'
        if not os.path.exists(tgt) and not os.path.exists(tgt+'.html'): add('broken_internal_link',f'{p} -> {href}')
    wa=re.findall(r'href="(https://wa\.me/[^"]*)"',h)
    if any('text=' not in w for w in wa): add('wa_link_no_text',p)
for t,ps in titles.items():
    if len(ps)>1: add('dup_title',' | '.join(ps))
for t,ps in descs.items():
    if len(ps)>1: add('dup_desc',' | '.join(ps))
for u in smurls:
    rel=u[len(base):] or 'index.html'
    if not os.path.exists(rel): add('sitemap_dead_url',u)
print(len(pages),'pages', len(smurls),'sitemap urls')
for k,v in issues.items():
    print(f'## {k}: {len(v)}')
    for x in sorted(set(v))[:12]: print('  -',x)
