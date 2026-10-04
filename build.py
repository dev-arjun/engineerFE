#!/usr/bin/env python3
"""
Build script for the Becoming an Engineer static blog.

No dependencies, just Python 3. Run from this folder:

    python3 build.py            # builds into public/
    python3 build.py docs       # builds into docs/ (for GitHub Pages)

Reads posts/*.md and about.md, writes the finished site to the output folder.
landing.html is copied as-is to become the homepage (index.html); the post
listing is written to blog.html. admin.html (the private, unlisted post editor)
is copied as-is to admin.html. Also writes posts.json, the machine-readable
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


def base(title, body, description="", prefix="", canonical_path="", article_date=""):
    """Page shell in the site's Tailwind dark theme.

    canonical_path like "posts/my-post.html" ("" = homepage).
    article_date "YYYY-MM-DD" marks the page as an article for OG/JSON-LD.
    """
    desc = html.escape(description or SITE_TAGLINE, quote=True)
    t = html.escape(title)
    canon = f"{SITE_URL}/{canonical_path}" if canonical_path else SITE_URL + "/"
    og_type = "article" if article_date else "website"
    ld = ""
    if article_date:
        ld = (
            '\n  <script type="application/ld+json">\n  {\n'
            f'    "@context": "https://schema.org",\n'
            f'    "@type": "BlogPosting",\n'
            f'    "headline": {json.dumps(title)},\n'
            f'    "description": {json.dumps(description or SITE_TAGLINE)},\n'
            f'    "datePublished": "{article_date}",\n'
            f'    "author": {{"@type": "Person", "name": "{AUTHOR}", "url": "{SITE_URL}/"}},\n'
            f'    "mainEntityOfPage": "{canon}"\n'
            '  }\n  </script>'
        )
    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t} | {SITE_TITLE}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{canon}">
<meta property="og:title" content="{t} | {SITE_TITLE}">
<meta property="og:description" content="{desc}">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="application/rss+xml" title="{SITE_TITLE} - RSS feed" href="{prefix}feed.xml">
<link rel="icon" href="{FAVICON}">
<script src="https://cdn.tailwindcss.com"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script>
tailwind.config = {{ darkMode: 'class', theme: {{ extend: {{ fontFamily: {{ sans: ['"Plus Jakarta Sans"', 'sans-serif'], mono: ['"JetBrains Mono"', 'monospace'] }} }} }} }};
</script>
<style>
body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
.post-body h1 {{ font-size: 1.875rem; font-weight: 800; color: #fff; margin: 1.75rem 0 0.75rem; letter-spacing: -0.01em; }}
.post-body h2 {{ font-size: 1.5rem; font-weight: 700; color: #fff; margin: 1.5rem 0 0.6rem; }}
.post-body h3 {{ font-size: 1.2rem; font-weight: 700; color: #f1f5f9; margin: 1.25rem 0 0.5rem; }}
.post-body p {{ margin: 0.9rem 0; line-height: 1.8; color: #cbd5e1; }}
.post-body a {{ color: #34d399; }}
.post-body a:hover {{ text-decoration: underline; }}
.post-body ul {{ list-style: disc; margin: 0.9rem 0; padding-left: 1.5rem; }}
.post-body ol {{ list-style: decimal; margin: 0.9rem 0; padding-left: 1.5rem; }}
.post-body li {{ margin: 0.35rem 0; color: #cbd5e1; line-height: 1.7; }}
.post-body blockquote {{ border-left: 3px solid #10b981; padding: 0.25rem 0 0.25rem 1rem; color: #94a3b8; margin: 1.1rem 0; }}
.post-body pre {{ background: #0b1120; border: 1px solid #1e293b; border-radius: 0.75rem; padding: 1rem; overflow-x: auto; margin: 1.1rem 0; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; line-height: 1.6; color: #a7f3d0; }}
.post-body p code, .post-body li code, .post-body h1 code, .post-body h2 code, .post-body h3 code {{ font-family: 'JetBrains Mono', monospace; background: #1e293b; padding: 0.15rem 0.4rem; border-radius: 0.375rem; font-size: 0.85em; color: #6ee7b7; }}
.post-body img {{ border-radius: 0.75rem; margin: 1.1rem 0; }}
.post-body hr {{ border-color: #1e293b; margin: 1.75rem 0; }}
</style>{ld}
</head>
<body class="bg-[#06080F] text-slate-200 min-h-screen flex flex-col">
<header class="sticky top-0 z-40 border-b border-slate-800/70" style="background: rgba(11,15,25,.85); backdrop-filter: blur(12px);">
<div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
<div class="flex items-center justify-between h-16">
<a href="{prefix}index.html" class="flex items-center gap-2.5">
<span class="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 via-teal-500 to-cyan-500 flex items-center justify-center text-white font-extrabold text-lg">B</span>
<span class="font-extrabold tracking-tight text-white">becominganengineer<span class="text-emerald-500">.in</span></span>
</a>
<nav class="flex items-center gap-5 text-sm">
<a href="{prefix}blog.html" class="text-slate-400 hover:text-emerald-400 transition">Blog</a>
<a href="{prefix}about.html" class="text-slate-400 hover:text-emerald-400 transition">About</a>
</nav>
</div>
</div>
</header>
<main class="flex-grow w-full max-w-3xl mx-auto px-4 sm:px-6 py-10">
{body}
</main>
<footer class="border-t border-slate-800/70 py-8">
<div class="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
<div class="flex items-center gap-2">
<span class="font-bold text-white">becominganengineer.in</span><span>&bull;</span><span>Curated by {AUTHOR}</span>
</div>
<a href="{prefix}index.html" class="hover:text-emerald-400 transition">Back to home</a>
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

    # Admin page: private post editor, copied as-is. Not linked from the
    # site and marked noindex so only the owner uses it.
    admin = ROOT / "admin.html"
    if admin.exists():
        shutil.copy(admin, out / "admin.html")

    # Blog page: newest posts first.
    items = []
    for p in posts:
        badge = ' <span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/30">Placeholder</span>' if p["placeholder"] else ""
        items.append(
            '<article class="rounded-2xl bg-[#111726] border border-slate-800 p-6 hover:border-emerald-500/40 transition">\n'
            f'<h2 class="text-xl font-bold text-white mb-1.5"><a class="hover:text-emerald-400 transition" href="posts/{p["slug"]}.html">{html.escape(p["title"])}</a>{badge}</h2>\n'
            f'<div class="text-xs text-slate-500 mb-2.5"><time datetime="{p["date_str"]}">{p["date_human"]}</time> &bull; {html.escape(p["readtime"])}</div>\n'
            f'<p class="text-sm text-slate-400 leading-relaxed">{html.escape(p["excerpt"])}</p>\n'
            "</article>"
        )
    blog_body = (
        '<h1 class="text-3xl font-extrabold text-white tracking-tight mb-2">Blog</h1>\n'
        f'<p class="text-slate-400 text-sm mb-8">{html.escape(SITE_TAGLINE)}</p>\n'
        '<section class="space-y-5">\n' + "\n".join(items) + "\n</section>"
    )
    (out / "blog.html").write_text(base("Blog", blog_body, canonical_path="blog.html"), encoding="utf-8")

    # Individual post pages.
    for p in posts:
        badge_block = (
            '<p class="mb-4"><span class="px-2 py-0.5 rounded text-[11px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/30">Placeholder post</span></p>\n'
            if p["placeholder"] else ""
        )
        tags_block = ""
        if p["tags"]:
            tags_block = (
                '<div class="flex flex-wrap gap-1.5 mb-2">'
                + "".join(
                    f'<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-900 text-slate-400 border border-slate-800">#{html.escape(tag)}</span>'
                    for tag in p["tags"]
                )
                + "</div>\n"
            )
        body = (
            '<p class="mb-8"><a class="text-sm font-semibold text-emerald-400 hover:text-emerald-300 transition" href="../blog.html">&larr; All posts</a></p>\n'
            + badge_block
            + "<article>\n"
            f'<div class="flex items-center gap-2 text-xs text-slate-500 mb-3"><span class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono font-bold">{p["date_human"]}</span><span>&bull;</span><span>{html.escape(p["readtime"])}</span></div>\n'
            f'<h1 class="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight mb-4">{html.escape(p["title"])}</h1>\n'
            + tags_block
            + f'<div class="post-body">{p["html"]}</div>\n'
            + "</article>\n"
            '<p class="mt-10 pt-6 border-t border-slate-800/70"><a class="text-sm font-semibold text-emerald-400 hover:text-emerald-300 transition" href="../blog.html">&larr; All posts</a></p>'
        )
        (out / "posts" / f"{p['slug']}.html").write_text(
            base(p["title"], body, description=p["excerpt"], prefix="../",
                 canonical_path=f"posts/{p['slug']}.html", article_date=p["date_str"]),
            encoding="utf-8",
        )

    # About page.
    meta, about_body = parse_front_matter(ROOT / "about.md")
    about_html = (
        f"<h1 class=\"text-3xl font-extrabold text-white tracking-tight mb-4\">{html.escape(meta.get('title', 'About'))}</h1>\n"
        f'<div class="post-body">{md_to_html(about_body)}</div>'
    )
    (out / "about.html").write_text(base("About", about_html, canonical_path="about.html"), encoding="utf-8")

    # Simple 404 page.
    (out / "404.html").write_text(
        base("Not found",
             '<div class="text-center py-16">\n'
             '<h1 class="text-4xl font-extrabold text-white mb-3">Not found</h1>\n'
             '<p class="text-slate-400 text-sm mb-6">That page does not exist.</p>\n'
             '<a class="text-sm font-semibold text-emerald-400 hover:text-emerald-300 transition" href="index.html">Back home</a>\n'
             "</div>"),
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
