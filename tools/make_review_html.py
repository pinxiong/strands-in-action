#!/usr/bin/env python3
"""Render a finished article into a standalone review HTML for Pin to read in a browser.

Usage
-----
    python3 tools/make_review_html.py <article.md> [options]

Options
-------
    --slug NAME          image folder name under static/images/ (default: usecase dir, minus NN-)
    --images-dir PATH    explicit image folder (default: pinxiong.github.io/static/images/<slug>)
    --out PATH           output file (default: <article dir>/review/article-preview.html)
    --label TEXT         left-hand label in the top bar (default: "UC05 · Strands Agents series")
    --status TEXT        right-hand status (default: "draft")

Design notes
------------
* Single self-contained file: every image is base64 inlined, so it opens offline,
  can be AirDropped to a phone, and prints without missing assets.
* Code blocks and figures break out of the text column by 90px, but only above
  1050px viewport width. Do NOT go back to `width:min(92vw,...)` + translateX:
  that pushes the document scrollWidth past innerWidth on narrow windows.
* Standalone images become <figure> with the alt text printed as a caption,
  so alt quality is reviewable at the same time as the figure.
"""
from __future__ import annotations

import argparse
import base64
import html as html_mod
import json
import re
from pathlib import Path

import markdown

SITE = Path("/Users/pinxiong/Documents/Important/pinxiong.github.io")
IMAGES_ROOT = SITE / "static/images"


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        m = re.match(r'^([A-Za-z_][\w-]*)\s*:\s*(.+?)\s*$', line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw.startswith('"') and raw.endswith('"') and len(raw) > 1:
            try:
                raw = json.loads(raw)          # handles \" and \\ escapes properly
            except json.JSONDecodeError:
                raw = raw[1:-1].replace('\\"', '"')
        elif raw.startswith("'") and raw.endswith("'") and len(raw) > 1:
            raw = raw[1:-1]
        meta[key] = raw
    return meta, text[end + 5 :]


def data_uri(path: Path) -> str:
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
    }.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def slugify_usecase(name: str) -> str:
    return re.sub(r"^\d+-", "", name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("article")
    ap.add_argument("--slug")
    ap.add_argument("--images-dir")
    ap.add_argument("--out")
    ap.add_argument("--label")
    ap.add_argument("--status", default="draft")
    args = ap.parse_args()

    article = Path(args.article).expanduser().resolve()
    if args.images_dir:
        images = Path(args.images_dir).expanduser()
    elif args.slug:
        images = IMAGES_ROOT / args.slug
    else:
        # article.md lives in usecases/05-<slug>/; a site draft is <slug>.md under content/posts
        candidates = [IMAGES_ROOT / article.stem, IMAGES_ROOT / slugify_usecase(article.parent.name)]
        images = next((c for c in candidates if c.is_dir()), candidates[0])
    out = Path(args.out).expanduser() if args.out else article.parent / "review/article-preview.html"

    text = article.read_text(encoding="utf-8")
    meta, body_md = parse_front_matter(text)

    h1 = re.search(r"^# (.+)$", body_md, re.M)
    title = h1.group(1).strip() if h1 else meta.get("title", article.stem)
    if h1:
        body_md = body_md[: h1.start()] + body_md[h1.end() :]
    body_md = body_md.lstrip("\n")

    # ---- inline every image referenced from the article -------------------
    missing: list[str] = []

    def inline_images(html: str) -> str:
        def repl(m: re.Match[str]) -> str:
            src = m.group(1)
            if src.startswith("data:"):
                return m.group(0)
            name = src.lstrip("/")
            candidates = []
            if src.startswith("/images/"):
                candidates.append(SITE / "static" / name)
                candidates.append(IMAGES_ROOT / name.split("/", 2)[-1])
            candidates.append(article.parent / name)
            for cand in candidates:
                if cand.is_file():
                    return m.group(0).replace(src, data_uri(cand), 1)
            missing.append(src)
            return m.group(0)

        return re.sub(r'<img[^>]+src="([^"]+)"', repl, html)

    html_body = markdown.markdown(
        body_md,
        extensions=["fenced_code", "tables", "sane_lists", "attr_list", "toc"],
        output_format="html5",
    )
    # site-relative links only resolve on the live site
    html_body = html_body.replace('href="/', 'href="https://xiongpin.dev/')
    html_body = re.sub(
        r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', html_body
    )
    html_body = inline_images(html_body)

    def to_figure(m: re.Match[str]) -> str:
        alt, src = m.group(1), m.group(2)
        return (
            f'<figure class="fig"><img alt="{alt}" src="{src}">'
            f"<figcaption>{html_mod.escape(alt)}</figcaption></figure>"
        )

    html_body = re.sub(
        r'<p><img alt="([^"]*)" src="([^"]*)"\s*/?></p>', to_figure, html_body
    )

    # ---- cover panel -----------------------------------------------------
    covers: list[tuple[str, str]] = []
    for fname, label in (
        ("cover.png", "Blog / og:image"),
        ("cover-devto.png", "Dev.to"),
        ("cover-medium.png", "Medium / Builder Center"),
    ):
        p = images / fname
        if p.is_file():
            covers.append((data_uri(p), f"{label} · {p.stat().st_size // 1024} KB"))
    cover_html = ""
    if covers:
        cards = "".join(
            f'<figure class="cv"><img src="{uri}" alt="{html_mod.escape(cap)} cover">'
            f"<figcaption>{html_mod.escape(cap)}</figcaption></figure>"
            for uri, cap in covers
        )
        cover_html = (
            '<details class="assets"><summary>Cover assets</summary>'
            f'<div class="assets-grid">{cards}</div></details>'
        )

    # ---- metadata --------------------------------------------------------
    plain = re.sub(r"```.*?```", "", body_md, flags=re.S)
    plain = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", plain)
    plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", plain)
    words = len(re.findall(r"[A-Za-z0-9'’\-]+", plain))
    minutes = max(1, round(words / 230))
    sections = len(re.findall(r"^## ", body_md, re.M))
    label = args.label or f"{article.parent.name} · review copy"

    css = CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.is_file() else ""
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html_mod.escape(title)} · review copy</title>
<style>{css}</style>
</head>
<body>
<div class="bar">
  <span class="tag">REVIEW COPY</span>
  <span>{html_mod.escape(label)}</span>
  <span class="sep">/</span>
  <span>~{minutes} min read</span>
  <span class="sep">/</span>
  <span>{sections} sections</span>
  <span class="right">
    <span>status: {html_mod.escape(args.status)}</span>
    <span>{article.relative_to(article.parents[2]) if len(article.parents) > 2 else article.name}</span>
  </span>
</div>
<main class="wrap">
<h1>{html_mod.escape(title)}</h1>
{html_body}
</main>
{cover_html}
<div class="foot">Self-contained review copy · images inlined · prints clean · source: {html_mod.escape(str(article))}</div>
</body>
</html>
"""

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    size = out.stat().st_size / 1024
    print(f"written {out}  ({size:,.0f} KB)  words={words}  reading={minutes}min  sections={sections}")
    if missing:
        print("WARNING missing images: " + ", ".join(missing))


CSS_PATH = Path(__file__).with_name("review_html.css")

CSS = """
:root{
  --ink:#1b1f24; --ink-soft:#4a5462; --ink-faint:#6b7684;
  --bg:#fbfaf7; --paper:#ffffff; --line:#e6e2da; --line-soft:#efece5;
  --accent:#1f6f6b; --accent-soft:#e8f2f1; --code-bg:#f6f5f1; --code-ink:#22303c;
  --mark:#fff6d9;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB",Helvetica,Arial,sans-serif;
  font-size:19px; line-height:1.75; text-rendering:optimizeLegibility;
  -webkit-font-smoothing:antialiased;
}
.bar{
  position:sticky; top:0; z-index:20; display:flex; gap:18px; align-items:center;
  padding:10px 22px; background:rgba(251,250,247,.92); backdrop-filter:saturate(180%) blur(8px);
  border-bottom:1px solid var(--line); font-size:13px; color:var(--ink-faint);
  letter-spacing:.02em;
}
.bar .tag{
  background:var(--accent-soft); color:var(--accent); font-weight:600;
  padding:3px 9px; border-radius:999px; letter-spacing:.03em;
}
.bar .sep{color:#cfcabf}
.bar .right{margin-left:auto; display:flex; gap:16px}
.wrap{max-width:760px; margin:0 auto; padding:0 26px 90px}
h1{
  font-size:2.05em; line-height:1.22; letter-spacing:-.018em; font-weight:700;
  margin:52px 0 10px;
}
h1 + blockquote{margin-top:22px}
h2{
  font-size:1.36em; line-height:1.3; letter-spacing:-.01em; font-weight:650;
  margin:2.4em 0 .7em; padding-top:.2em;
}
h2::before{
  content:""; display:block; width:38px; height:3px; border-radius:2px;
  background:var(--accent); opacity:.55; margin-bottom:14px;
}
p{margin:0 0 1.15em}
blockquote{
  margin:0 0 1.6em; padding:16px 20px; background:var(--paper);
  border-left:3px solid var(--accent); border-radius:0 8px 8px 0;
  color:var(--ink-soft); font-size:.94em; line-height:1.7;
}
blockquote p{margin:0}
blockquote code{background:var(--code-bg)}
a{color:var(--accent); text-decoration:none; border-bottom:1px solid rgba(31,111,107,.28)}
a:hover{border-bottom-color:var(--accent); background:var(--accent-soft)}
code{
  font-family:"SF Mono",ui-monospace,Menlo,Consolas,"Liberation Mono",monospace;
  font-size:.86em; background:var(--code-bg); color:var(--code-ink);
  padding:.12em .34em; border-radius:4px; border:1px solid var(--line-soft);
}
pre{
  margin:0 0 1.55em; padding:18px 22px;
  background:var(--paper); border:1px solid var(--line); border-radius:10px;
  overflow-x:auto; line-height:1.65;
}
pre code{
  display:block; background:none; border:0; padding:0; font-size:.72em;
  color:var(--code-ink); white-space:pre;
}
pre code::-moz-selection{background:var(--mark)}
figure{margin:2em 0}
img{max-width:100%; height:auto}
p img{
  display:block; margin:1.8em auto; border:1px solid var(--line);
  border-radius:10px; background:var(--paper);
}
figure.fig{margin:2.2em 0}
figure.fig img{
  display:block; width:100%; height:auto; border:1px solid var(--line);
  border-radius:10px; background:var(--paper);
}
figure.fig figcaption{
  font-size:12.5px; line-height:1.6; color:var(--ink-faint);
  margin-top:9px; padding:0 2px;
}
figure.fig figcaption::before{content:"ALT · "; color:var(--accent); letter-spacing:.08em}
ul{margin:0 0 1.4em; padding-left:1.15em}
li{margin:.5em 0; padding-left:.15em}
li::marker{color:var(--accent)}
hr{border:0; border-top:1px solid var(--line); margin:2.5em 0}
.foot{
  max-width:760px; margin:0 auto; padding:8px 26px 70px;
  font-size:13px; color:var(--ink-faint);
}
details.assets{
  max-width:760px; margin:0 auto 10px; padding:0 26px;
}
details.assets summary{
  cursor:pointer; font-size:13px; letter-spacing:.04em; text-transform:uppercase;
  color:var(--ink-faint); padding:18px 0; border-top:1px solid var(--line);
  list-style:none;
}
details.assets summary::-webkit-details-marker{display:none}
details.assets summary::before{content:"▸ "; color:var(--accent)}
details.assets[open] summary::before{content:"▾ "}
.assets-grid{display:grid; gap:20px; padding-bottom:28px;
  grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
figure.cv{margin:0}
figure.cv img{display:block; width:100%; height:auto; border:1px solid var(--line); border-radius:8px}
figure.cv figcaption{font-size:12px; color:var(--ink-faint); margin-top:7px; letter-spacing:.03em}
@media (max-width:640px){
  body{font-size:17px}
  h1{font-size:1.66em}
  .wrap{padding:0 18px 70px}
  .bar{font-size:11.5px; gap:10px; padding:8px 14px}
  .bar .right{display:none}
}
/* wide viewports: let code blocks and figures outgrow the text column */
@media (min-width:1050px){
  pre, figure.fig{margin-left:-90px; margin-right:-90px}
}
html,body{overflow-x:hidden}
@media print{
  .bar,.foot,details.assets{display:none}
  body{background:#fff; font-size:11pt}
  pre,blockquote{break-inside:avoid}
  h2{break-after:avoid}
}
"""

if __name__ == "__main__":
    if not CSS_PATH.is_file():
        CSS_PATH.write_text(CSS.strip() + "\n", encoding="utf-8")
    main()
