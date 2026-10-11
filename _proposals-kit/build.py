"""Build a proposal PDF: python3 build.py body.html out.pdf "<title>"
body.html may contain {{ABOUT}} and {{CONTACT}} placeholders (see example_body.html).
Fonts: sparse-clone google/fonts (ofl/tajawal, ofl/notokufiarabic) to /home/claude/google/fonts first."""
import sys, os
from playwright.sync_api import sync_playwright
K = os.path.dirname(os.path.abspath(__file__))
FONTS = os.environ.get('FONTS_DIR', '/home/claude/google/fonts')
body, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
rd = lambda n: open(os.path.join(K, n), encoding='utf-8').read()
html = rd('head.html').replace('{{FONTS}}', 'file://' + FONTS).replace('{{TITLE}}', title)
html += open(body, encoding='utf-8').read().replace('{{ABOUT}}', rd('about.html')).replace('{{CONTACT}}', rd('contact.html'))
html += '\n</body>\n</html>\n'
tmp = os.path.abspath(out) + '.html'
open(tmp, 'w', encoding='utf-8').write(html)
exe = None
for p in ['/opt/pw-browsers/chromium-1194/chrome-linux/chrome']:
    if os.path.exists(p): exe = p
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
    pg = b.new_page(); pg.goto('file://' + tmp); pg.wait_for_timeout(800)
    pg.pdf(path=out, format='A4', print_background=True, prefer_css_page_size=True); b.close()
print('ok', out)
