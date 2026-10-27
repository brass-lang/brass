"""Build the GitHub Pages site into site/.

The README becomes the home page and every other Markdown file outside tools-and-testing/ is
rendered the way GitHub renders it (its own Markdown API, github-markdown-css). The two HTML
pages in docs/ are served from the site root. Links into tools-and-testing/ go to the repository.
"""
import json
import os
import re
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
REPO = "brass-lang/brass"
TREE = f"https://github.com/{REPO}/tree/main/"
CSS = "https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown.min.css"
SKIP = {"tools-and-testing", "site", ".github", ".git"}

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{css}">
<style>
body{{margin:0;background:#fff}}
@media (prefers-color-scheme: dark){{body{{background:#0d1117}}}}
.markdown-body{{box-sizing:border-box;max-width:980px;margin:0 auto;padding:45px}}
@media (max-width:767px){{.markdown-body{{padding:15px}}}}
</style>
</head>
<body>
<article class="markdown-body">
{body}
</article>
</body>
</html>
"""


def render(md: str) -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is required to render Markdown")
    req = urllib.request.Request(
        "https://api.github.com/markdown",
        data=json.dumps({"text": md, "mode": "gfm", "context": REPO}).encode(),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": REPO},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()


def relink(html: str, depth: int) -> str:
    """Point .md links at their rendered pages and tools-and-testing links at GitHub."""
    def fix(m):
        href = m.group(1)
        if re.match(r"^(https?:|mailto:|#)", href):
            return m.group(0)
        path, _, frag = href.partition("#")
        up = "../" * depth
        if path.startswith("tools-and-testing/") or path.startswith(up + "tools-and-testing/"):
            return f'href="{TREE}{path.removeprefix(up)}{"#" + frag if frag else ""}"'
        if path.endswith(".md"):
            path = path[:-3] + ".html"
            if path.endswith("README.html"):
                path = path[: -len("README.html")] + "index.html"
        return f'href="{path}{"#" + frag if frag else ""}"'
    return re.sub(r'href="([^"]*)"', fix, html)


def title_of(md: str, fallback: str) -> str:
    m = re.search(r"^# (.+)$", md, re.M)
    return m.group(1).strip() if m else fallback


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    count = 0
    for src in sorted(ROOT.rglob("*.md")):
        rel = src.relative_to(ROOT)
        if rel.parts[0] in SKIP:
            continue
        out = SITE / rel.with_suffix(".html")
        if src.name == "README.md":
            out = out.with_name("index.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        md = src.read_text()
        html = relink(render(md), depth=len(rel.parts) - 1)
        out.write_text(TEMPLATE.format(title=title_of(md, rel.stem), css=CSS, body=html))
        count += 1
    for src in sorted((ROOT / "docs").glob("*.html")) + sorted((ROOT / "docs").glob("*.js")):
        shutil.copy(src, SITE / src.name)
    shutil.copytree(ROOT / "docs" / "images", SITE / "docs" / "images")
    for name in ("LICENSE", "LICENSE-docs"):
        shutil.copy(ROOT / name, SITE / name)
    (SITE / ".nojekyll").write_text("")
    cname = ROOT / "CNAME"
    if cname.exists():
        shutil.copy(cname, SITE / "CNAME")
    print(f"rendered {count} pages into {SITE}")


if __name__ == "__main__":
    main()
