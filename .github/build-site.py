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

# The top bar every page shares, the two reader pages included: full width, the same margins everywhere,
# and the current page underlined rather than bold, so no link moves between pages.
TOPBAR_CSS = """
.top{{box-sizing:border-box;display:flex;justify-content:space-between;align-items:flex-start;padding:12px clamp(16px,5vw,64px) 0;
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif;letter-spacing:normal}}
.top .links, .top .group{{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:2px 18px}}
.top a{{color:#59636e;text-decoration:none}}
.top a:hover, .top a[aria-current]{{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:.4em}}
.top a:hover{{color:#1C4FB8}}
.top .name{{font-weight:600;color:#1f2328}}
.top a[aria-current]{{color:#1f2328}}
@media (prefers-color-scheme: dark){{.top a{{color:#9198a1}}.top .name, .top a[aria-current]{{color:#f0f6fc}}.top a:hover{{color:#6FA0FF}}}}
@media (max-width:767px){{.top .links, .top .group{{column-gap:14px}}}}
"""
# Two groups: the essays, then the reference documents.
NAV = [[("Welcome", "welcome-to-brass-language.html"), ("Token efficiency", "ai-token-efficiency-of-brass.html")],
       [("Spec", "docs/brass-core-spec.html"), ("Grammar", "docs/brass-core-grammar.html")]]


def topbar(root: str, here: str) -> str:
    """The bar for the page at site path `here`; its own entry is marked as the current page."""
    current = ' aria-current="page"'
    def link(label, path):
        return f'<a href="{root}{path}"{current if path == here else ""}>{label}</a>'
    essays, docs = ("".join(link(label, path) for label, path in group) for group in NAV)
    return (f'<nav class="top"><a class="name" href="{root}index.html">Brass</a><span class="links">'
            f'<span class="group">{essays}</span>'
            f'<span class="group">{docs}<a href="https://github.com/{REPO}">GitHub</a></span></span></nav>')

# "paper" keeps GitHub's rendering on the reader pages' warm ground; "github" is GitHub's own white.
PAPER_CSS = """
body{{background:#FFFFF8}}
.markdown-body{{--bgColor-default:#FFFFF8;--bgColor-muted:#F3F2EA;--borderColor-default:#DAD9CC;--borderColor-muted:#DAD9CCb3;--fgColor-accent:#1C4FB8}}
@media (prefers-color-scheme: dark){{
  body{{background:#151513}}
  .markdown-body{{--bgColor-default:#151513;--bgColor-muted:#1E1E1B;--borderColor-default:#3E3D38;--borderColor-muted:#3E3D38b3;--fgColor-accent:#6FA0FF}}
}}
"""
THEME = "paper"

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{css}">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:wght@500&display=swap">
<style>
body{{margin:0;background:#fff}}
@media (prefers-color-scheme: dark){{body{{background:#0d1117}}}}
.markdown-body{{box-sizing:border-box;max-width:980px;margin:0 auto;padding:57px 45px 45px}}
@media (max-width:767px){{.markdown-body{{padding:45px 15px 15px}}}}
.markdown-body h1{{font-family:"EB Garamond","Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;font-weight:500;font-size:2.6rem;
  line-height:1.1;letter-spacing:-.005em;text-wrap:balance;border-bottom:0;padding-bottom:0}}
""" + TOPBAR_CSS + (PAPER_CSS if THEME == "paper" else "") + """</style>
</head>
<body>
{nav}
<article class="markdown-body">
{body}
</article>
</body>
</html>
"""

# The reader pages pad their body (48px top, the bar's side margins); the bar steps out of that padding.
# Below it, the label and title land where a Markdown page's title does.
READER_CSS = ("<style>" + TOPBAR_CSS + """
body > .top{{margin:-48px calc(-1 * clamp(16px,5vw,64px)) 30px}}
@media (max-width:767px){{body > .top{{margin-bottom:18px}}}}
</style>
""").format()


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


def anchor_headings(html: str) -> str:
    """Give each heading the id GitHub's page scripts would: lowercased, punctuation dropped,
    spaces to hyphens, duplicates suffixed -1, -2. The Markdown API leaves headings without ids."""
    seen = {}

    def slug(text: str) -> str:
        s = re.sub(r"<[^>]+>", "", text).lower()
        s = re.sub(r"[^\w\- ]", "", s).replace(" ", "-")
        n = seen.get(s, 0)
        seen[s] = n + 1
        return s if n == 0 else f"{s}-{n}"

    return re.sub(r'<h([1-6])([^>]*)>(.*?)</h\1>',
                  lambda m: f'<h{m.group(1)}{m.group(2)} id="{slug(m.group(3))}">{m.group(3)}</h{m.group(1)}>',
                  html, flags=re.S)


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
        html = anchor_headings(relink(render(md), depth=len(rel.parts) - 1))
        root = "../" * (len(rel.parts) - 1)
        out.write_text(TEMPLATE.format(title=title_of(md, rel.stem), css=CSS, body=html,
                                       nav=topbar(root, out.relative_to(SITE).as_posix())))
        count += 1
    for src in sorted((ROOT / "docs").glob("*.html")):
        page = src.read_text()
        if page.count("<body>\n<article>\n") != 1:
            sys.exit(f"{src.name}: expected the page to open with <body> then <article>, to put the top bar in")
        (SITE / src.name).write_text(page.replace("<body>\n<article>\n", "<body>\n" + READER_CSS + topbar("", src.name) + "\n<article>\n"))
    for src in sorted((ROOT / "docs").glob("*.js")):
        shutil.copy(src, SITE / src.name)
    shutil.copytree(ROOT / "docs" / "images", SITE / "docs" / "images")
    for name in ("LICENSE", "LICENSE-docs"):
        shutil.copy(ROOT / name, SITE / name)
    missing = [path for group in NAV for _, path in group if not (SITE / path).exists()]
    if missing:
        sys.exit(f"top bar links to pages the build did not make: {missing}")
    (SITE / ".nojekyll").write_text("")
    cname = ROOT / "CNAME"
    if cname.exists():
        shutil.copy(cname, SITE / "CNAME")
    print(f"rendered {count} pages into {SITE}")


if __name__ == "__main__":
    main()
