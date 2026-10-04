#!/usr/bin/env python3
"""
Build script for the Becoming an Engineer static blog.

No dependencies, just Python 3. Run from this folder:

    python3 build.py            # builds into public/
    python3 build.py docs       # builds into docs/ (for GitHub Pages)

Reads posts/*.md and about.md, writes the finished site to the output folder.
landing.html is copied as-is to become the homepage (index.html); the post
listing is written to blog.html. Also writes posts.json, the machine-readable
feed the homepage (landing.html) renders its article cards from.
Supported front matter keys: title, date (YYYY-MM-DD), tags (comma-separated),
description, readtime, placeholder.
"""

import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"

SITE_TITLE = "Becoming an Engineer"
SITE_TAGLINE = "A performance tester learning in public, on the road to becoming an SDET."
SITE_URL = "https://becominganengineer.in"
AUTHOR = "Arjun"

FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
    "%3Crect width='100' height='100' rx='22' fill='%231d4ed8'/%3E"
    "%3Ctext x='50' y='70' font-size='58' text-anchor='middle' fill='white' "
    "font-family='sans-serif' font-weight='bold'%3EB%3C/text%3E%3C/svg%3E"
)


# ---------------------------------------------------------------------------
# Markdown to HTML (small built-in converter, no dependencies)
# Supports: headings (##, ###), bold, italic, inline code, fenced and
# indented code blocks, bulleted and numbered lists, blockquotes,
# links, images, horizontal rules, paragraphs.
# ---------------------------------------------------------------------------

def inline(raw):
    """Convert inline Markdown in a single chunk of text to HTML."""
    t = html.escape(raw, quote=False)
    parts = re.split(r"(`[^`\n]+`)", t)
    out = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            out.append("<code>" + part[1:-1] + "</code>")
        else:
            part = re.sub(
                r"!\[([^\]\n]*)\]\(([^)\s]+)\)",
                r'<img src="\2" alt="\1" loading="lazy">',
                part,
            )
            part = re.sub(
                r"\[([^\]\n]+)\]\(([^)\s]+)\)",
                r'<a href="\2">\1</a>',
                part,
            )
            part = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", part)
            part = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", part)
            out.append(part)
    return "".join(out)


def md_to_html(md):
    """Convert a Markdown document to an HTML fragment."""
    md = md.replace("\r\n", "\n").replace("\r", "\n")

    # Pull out fenced code blocks first so their contents are never parsed.
    blocks = {}

    def fence_repl(m):
        lang = (m.group(1) or "").strip()
        code = html.escape(m.group(2).rstrip("\n"))
        cls = f' class="language-{lang}"' if lang else ""
        key = f"\x00FENCED{len(blocks)}\x00"
        blocks[key] = f"<pre><code{cls}>{code}</code></pre>"
        return "\n" + key + "\n"

    md = re.sub(r"^```(\w*)[ \t]*\n(.*?)^```[ \t]*$", fence_repl, md,
                flags=re.M | re.S)
    lines = md.split("\n")

    def parse_blocks(lines):
        out = []
        para = []
        cur_list = None
        code_buf = None

        def flush_para():
            if para:
                out.append("<p>" + inline(" ".join(l.strip() for l in para)) + "</p>")
                para.clear()

        def close_list():
            nonlocal cur_list
            if cur_list:
                out.append("</" + cur_list + ">")
                cur_list = None

        def flush_code():
            nonlocal code_buf
            if code_buf is not None:
                out.append("<pre><code>"
                           + html.escape("\n".join(code_buf).strip("\n"))
                           + "</code></pre>")
                code_buf = None

        i, n = 0, len(lines)
        while i < n:
            raw = lines[i]
            s = raw.strip()

            if s in blocks:
                flush_para()
                close_list()
                flush_code()
                out.append(blocks[s])
                i += 1
                continue

            if code_buf is not None:
                if raw.startswith("    ") or s == "":
                    code_buf.append(raw[4:] if raw.startswith("    ") else "")
                    i += 1
                    continue
                flush_code()
                # fall through and parse this line normally

            if s == "":
                flush_para()
                close_list()
                i += 1
                continue

            m = re.match(r"^(#{1,3})\s+(.+)$", s)
            if m:
                flush_para()
                close_list()
                lvl = len(m.group(1))
                out.append(f"<h{lvl}>" + inline(m.group(2).strip()) + f"</h{lvl}>")
                i += 1
                continue

            if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
                flush_para()
                close_list()
                out.append("<hr>")
                i += 1
                continue

            if s.startswith(">"):
                flush_para()
                close_list()
                q = []
                while i < n and lines[i].strip().startswith(">"):
                    q.append(re.sub(r"^>\s?", "", lines[i].strip()))
                    i += 1
                out.append("<blockquote>\n" + parse_blocks(q) + "</blockquote>")
                continue

            m = re.match(r"^([-*+])\s+(.+)$", s)
            if m:
                flush_para()
                if cur_list != "ul":
                    close_list()
                    out.append("<ul>")
                    cur_list = "ul"
                out.append("<li>" + inline(m.group(2).strip()) + "</li>")
                i += 1
                continue

            m = re.match(r"^(\d+)\.\s+(.+)$", s)
            if m:
                flush_para()
                if cur_list != "ol":
                    close_list()
                    out.append("<ol>")
                    cur_list = "ol"
                out.append("<li>" + inline(m.group(2).strip()) + "</li>")
                i += 1
                continue

            if raw.startswith("    "):
                flush_para()
                close_list()
                code_buf = [raw[4:]]
                i += 1
                continue

            para.append(raw)
            i += 1

        flush_para()
        close_list()
        flush_code()
        return "\n".join(out)

    return parse_blocks(lines)


# ---------------------------------------------------------------------------
# Posts, pages, templates
# ---------------------------------------------------------------------------

def parse_front_matter(path):
    text = path.read_text(encoding="utf-8")
    meta = {}
    body = text
    m = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", text, re.S)
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip().strip('"').strip("'")
        body = text[m.end():]
    return meta, body


def excerpt_from(body, meta):
    if meta.get("description"):
        return meta["description"]
    for line in body.split("\n"):
        s = line.strip()
        if not s or s.startswith(("#", ">", "```", "-", "*", "1.")):
            continue
        s = re.sub(r"[*_`\[\]()#>!-]", "", s).strip()
        if s:
            return s[:180] + ("..." if len(s) > 180 else "")
    return ""


def parse_post(path):
    meta, body = parse_front_matter(path)
    title = meta.get("title") or path.stem.replace("-", " ").title()
    date_str = meta.get("date", "")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise SystemExit(
            f"Error: {path.name} needs a date like 2026-10-04 in its front matter."
        )
    tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    return {
        "slug": path.stem,
        "title": title,
        "date_str": date_str,
        "date_human": dt.strftime("%B %d, %Y").replace(" 0", " "),
        "dt": dt,
        "readtime": meta.get("readtime", "5 min read"),
        "tags": tags,
        "excerpt": excerpt_from(body, meta),
        "code": first_code_block(body),
        "html": md_to_html(body),
        "placeholder": meta.get("placeholder", "").lower() == "true",
    }


def first_code_block(body):
    """Return the contents of the first fenced code block, or ''."""
    m = re.search(r"^```\w*[ \t]*\n(.*?)^```[ \t]*$", body, flags=re.M | re.S)
    return m.group(1).rstrip("\n") if m else ""


def base(title, body, description="", prefix=""):
    desc = html.escape(description or SITE_TAGLINE, quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} | {SITE_TITLE}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="{prefix}style.css">
<link rel="alternate" type="application/rss+xml" title="{SITE_TITLE} - RSS feed" href="{prefix}feed.xml">
<link rel="icon" href="{FAVICON}">
</head>
<body>
<header class="site">
<div class="wrap">
<a class="site-title" href="{prefix}index.html">{SITE_TITLE}</a>
<nav>
<a href="{prefix}index.html">Home</a>
<a href="{prefix}blog.html">Blog</a>
<a href="{prefix}about.html">About</a>
<a href="{prefix}feed.xml">RSS</a>
</nav>
</div>
</header>
<main class="wrap">
{body}
</main>
<footer class="site">
<div class="wrap">
<p>&copy; 2026 {AUTHOR}. Built by hand, hosted for free.</p>
</div>
</footer>
</body>
</html>
"""


def build_feed(posts):
    items = []
    for p in posts:
        pub = format_datetime(p["dt"].replace(tzinfo=timezone.utc))
        url = f"{SITE_URL}/posts/{p['slug']}.html"
        items.append(
            "<item>\n"
            f"<title>{html.escape(p['title'])}</title>\n"
            f"<link>{url}</link>\n"
            f"<guid>{url}</guid>\n"
            f"<pubDate>{pub}</pubDate>\n"
            f"<description>{html.escape(p['excerpt'], quote=True)}</description>\n"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<rss version=\"2.0\">\n"
        "<channel>\n"
        f"<title>{SITE_TITLE}</title>\n"
        f"<link>{SITE_URL}/</link>\n"
        f"<description>{html.escape(SITE_TAGLINE)}</description>\n"
        "<language>en</language>\n"
        + "\n".join(items)
        + "\n</channel>\n</rss>\n"
    )


def main():
    out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "public"
    if out.exists():
        shutil.rmtree(out)
    (out / "posts").mkdir(parents=True)
    shutil.copy(ROOT / "style.css", out / "style.css")

    posts = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        posts.append(parse_post(path))
    posts.sort(key=lambda p: p["dt"], reverse=True)

    # Landing page: Arjun's custom homepage, copied as-is.
    landing = ROOT / "landing.html"
    if not landing.exists():
        raise SystemExit("Error: landing.html is missing. It is the site's homepage.")
    shutil.copy(landing, out / "index.html")

    # Blog page: newest posts first.
    items = []
    for p in posts:
        badge = ' <span class="badge">Placeholder</span>' if p["placeholder"] else ""
        items.append(
            "<article>\n"
            f"<h2><a href=\"posts/{p['slug']}.html\">{html.escape(p['title'])}</a>{badge}</h2>\n"
            f"<time datetime=\"{p['date_str']}\">{p['date_human']}</time>\n"
            f"<p>{html.escape(p['excerpt'])}</p>\n"
            "</article>"
        )
    blog_body = (
        "<h1>Blog</h1>\n"
        f'<p class="tagline">{html.escape(SITE_TAGLINE)}</p>\n'
        '<section class="post-list">\n' + "\n".join(items) + "\n</section>"
    )
    (out / "blog.html").write_text(base("Blog", blog_body), encoding="utf-8")

    # Individual post pages.
    for p in posts:
        badge_block = (
            '<p><span class="badge">Placeholder post</span></p>\n'
            if p["placeholder"] else ""
        )
        body = (
            '<p><a href="../blog.html">&larr; All posts</a></p>\n'
            '<article class="post">\n'
            f"<h1>{html.escape(p['title'])}</h1>\n"
            f"<time datetime=\"{p['date_str']}\">{p['date_human']}</time>\n"
            + badge_block + p["html"] + "\n</article>\n"
            '<p><a href="../blog.html">&larr; All posts</a></p>'
        )
        (out / "posts" / f"{p['slug']}.html").write_text(
            base(p["title"], body, description=p["excerpt"], prefix="../"),
            encoding="utf-8",
        )

    # About page.
    meta, about_body = parse_front_matter(ROOT / "about.md")
    about_html = f"<h1>{html.escape(meta.get('title', 'About'))}</h1>\n" + md_to_html(about_body)
    (out / "about.html").write_text(base("About", about_html), encoding="utf-8")

    # Simple 404 page (used by Cloudflare Pages and GitHub Pages).
    (out / "404.html").write_text(
        base("Not found",
             "<h1>Not found</h1>\n<p>That page does not exist. "
             '<a href="index.html">Back home</a>.</p>'),
        encoding="utf-8",
    )

    # Tells GitHub Pages about the custom domain. Harmless elsewhere.
    (out / "CNAME").write_text("becominganengineer.in\n", encoding="utf-8")

    # RSS feed.
    (out / "feed.xml").write_text(build_feed(posts), encoding="utf-8")

    # posts.json: machine-readable feed the homepage renders its cards from.
    feed_items = [
        {
            "slug": p["slug"],
            "title": p["title"],
            "date": p["date_str"],
            "readTime": p["readtime"],
            "tags": p["tags"],
            "summary": p["excerpt"],
            "code": p["code"],
        }
        for p in posts
    ]
    (out / "posts.json").write_text(
        json.dumps(feed_items, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Built {len(posts)} post(s) into {out}")


if __name__ == "__main__":
    main()
