"""Inline the offline app build (JS, CSS) and the recording into ONE self-contained HTML file.
Usage: py -3.12 pack_offline.py <build dir> <rec.json> <out.html>"""
import re
import sys
from pathlib import Path

build, rec_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
page = build / "offline-export" / "index.html"
html = page.read_text(encoding="utf-8")
safe = lambda s: s.replace("</script", "<\\/script").replace("<!--", "<\\!--")   # text inside <script> must not close it


def inline(kind):
    def f(m):
        src = (page.parent / m.group(1)).resolve()
        if kind == "css":
            return "<style>" + src.read_text(encoding="utf-8") + "</style>"
        return '<script type="module">' + safe(src.read_text(encoding="utf-8")) + "</script>"
    return f


html = re.sub(r'<link rel="stylesheet"[^>]*href="([^"]+)"[^>]*>', inline("css"), html)
html = re.sub(r'<script type="module"[^>]*src="([^"]+)"[^>]*></script>', inline("js"), html)
html = re.sub(r'<link rel="(icon|apple-touch-icon)"[^>]*>', "", html)       # icons would point at files beside it
assert "assets/" not in re.sub(r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.S), "an asset was left outside the file"
# the recording must exist before the app's module runs (modules run after the document is parsed)
html = html.replace("<head>", "<head><script>window.__REC__=" + safe(rec_path.read_text(encoding="utf-8")) + ";</script>", 1)
out.write_text(html, encoding="utf-8")
print("saved", out, round(len(html.encode()) / 1e6, 1), "MB")
