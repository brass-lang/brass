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

GITHUB = """<!doctype html>
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
.top{{box-sizing:border-box;display:flex;justify-content:space-between;align-items:center;max-width:980px;margin:0 auto;padding:12px 45px 0;
  font:14px -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif}}
.top a{{color:#59636e;text-decoration:none}}
.top a:hover{{color:#0969da;text-decoration:underline}}
.top .name{{font-weight:600;color:#1f2328}}
@media (prefers-color-scheme: dark){{.top a{{color:#9198a1}}.top .name{{color:#f0f6fc}}.top a:hover{{color:#4493f8}}}}
@media (max-width:767px){{.top{{padding:10px 15px 0}}}}
</style>
</head>
<body>
<nav class="top"><a class="name" href="{root}index.html">Brass</a><a href="https://github.com/{repo}">GitHub</a></nav>
<article class="markdown-body">
{body}
</article>
</body>
</html>
"""

BRASS = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Inconsolata:wght@400;500;600&family=Barlow+Condensed:wght@500;600;700&display=swap">
<style>
:root{{
  --paper:#FFFFF8; --ink:#111110; --soft:#4A4A45; --faint:#8C8B84; --rule:#CFCFC2; --wash:#F2F1EA; --wash2:#E9E8DF;
  --keel:#1C4FB8; --code-tint:#F6F5EE;
  --sign:"Barlow Condensed","Arial Narrow","Helvetica Neue",sans-serif;
  --serif:"EB Garamond","Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --mono:Inconsolata,ui-monospace,"SF Mono",Menlo,monospace;
}}
@media (prefers-color-scheme: dark){{
  :root{{ --paper:#151513; --ink:#ECEAE0; --soft:#B4B2A8; --faint:#85847C; --rule:#3E3D38; --wash:#1E1E1B; --wash2:#2A2A26;
    --keel:#6FA0FF; --code-tint:#1C1C1A; color-scheme:dark; }}
}}
html{{ background:var(--paper); }}
body{{ margin:0; background:var(--paper); color:var(--ink); font-family:var(--serif); font-size:19px; line-height:1.5;
  font-variant-numeric:oldstyle-nums proportional-nums; padding-inline:clamp(16px,5vw,64px); padding-block:28px 80px; }}
.top{{ display:flex; justify-content:space-between; align-items:baseline; max-width:980px; margin:0 auto 2.6rem; padding-bottom:.6rem; border-bottom:1px solid var(--rule);
  font-family:var(--sign); font-weight:600; font-size:.82rem; letter-spacing:.18em; text-transform:uppercase; }}
.top a{{ color:var(--soft); text-decoration:none; }}
.top a:hover{{ color:var(--keel); }}
.top .name{{ color:var(--ink); }}
.markdown-body{{ max-width:980px; margin:0 auto; }}
h1{{ font-weight:500; font-size:2.6rem; line-height:1.1; margin:0 0 1.2rem; letter-spacing:-.005em; text-wrap:balance; }}
h2{{ font-weight:500; font-style:italic; font-size:1.8rem; line-height:1.2; margin:3.2rem 0 .7rem; text-wrap:balance; }}
h3{{ font-weight:500; font-style:italic; font-size:1.35rem; line-height:1.25; margin:2.2rem 0 .5rem; text-wrap:balance; }}
h4, h5, h6{{ font-weight:600; font-size:1.05rem; margin:1.8rem 0 .4rem; }}
p, ul, ol, blockquote{{ margin:0 0 1rem; }}
ul, ol{{ padding-left:1.3rem; }} li{{ margin-bottom:.45rem; }}
strong, b{{ font-weight:600; }}
a{{ color:var(--keel); }}
hr{{ border:0; border-top:1px solid var(--rule); margin:2.6rem 0; }}
blockquote{{ border-left:2px solid var(--rule); padding-left:1rem; color:var(--soft); }}
img{{ max-width:100%; height:auto; border:1px solid var(--rule); border-radius:3px; }}
code{{ font-family:var(--mono); font-size:.86em; color:var(--soft); background:var(--code-tint); padding:.02em .22em; border-radius:2px; }}
pre{{ font-family:var(--mono); font-size:.8rem; line-height:1.55; margin:.6rem 0 1rem; padding:.8rem 1rem; background:var(--wash); border-radius:3px;
  overflow-x:auto; white-space:pre; font-variant-numeric:lining-nums; color:var(--ink); }}
pre code{{ font-size:inherit; color:inherit; background:none; padding:0; }}
.highlight pre{{ margin:0; }} .highlight{{ margin:.6rem 0 1rem; }}
table{{ border-collapse:collapse; font-size:.9rem; line-height:1.38; margin:.6rem 0 1rem; display:block; max-width:100%; overflow-x:auto; }}
thead th{{ font-weight:400; font-style:italic; text-align:left; padding:.2rem 1.2rem .35rem 0; border-top:1.5px solid var(--ink); border-bottom:1px solid var(--ink); white-space:nowrap; }}
tbody td{{ padding:.32rem 1.2rem .32rem 0; vertical-align:top; border-bottom:1px solid var(--wash2); }}
tbody tr:last-child td{{ border-bottom:1.5px solid var(--ink); }}
.markdown-body > :first-child{{ margin-top:0; }}
</style>
</head>
<body>
<nav class="top"><a class="name" href="{root}index.html">Brass</a><a href="https://github.com/{repo}">GitHub</a></nav>
<article class="markdown-body">
{body}
</article>
</body>
</html>
"""

# The look of the rendered Markdown pages. "brass" matches the two reader pages (serif on paper);
# "github" is the plain GitHub rendering. Flip this one line to revert.
THEME = "github"
THEMES = {"github": GITHUB, "brass": BRASS}
TEMPLATE = THEMES[THEME]


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
        out.write_text(TEMPLATE.format(title=title_of(md, rel.stem), css=CSS, body=html, root=root, repo=REPO))
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
