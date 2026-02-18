#!/usr/bin/env python3
"""Build the static provara.dev site with zero-JS reading pages."""

from __future__ import annotations

import datetime as dt
import gzip
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sites" / "provara.dev"
BASE_URL = "https://provara.dev"


@dataclass
class Rendered:
    html: str
    toc: list[tuple[int, str, str]]


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-") or "section"


def inline_md(text: str) -> str:
    tokens: list[str] = []

    def code_repl(m: re.Match[str]) -> str:
        tokens.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"@@CODE{len(tokens)-1}@@"

    text = re.sub(r"`([^`]+)`", code_repl, text)
    text = html.escape(text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
        text,
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)

    for idx, token in enumerate(tokens):
        text = text.replace(f"@@CODE{idx}@@", token)

    return text


def markdown_to_html(md: str) -> Rendered:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    toc: list[tuple[int, str, str]] = []

    in_code = False
    in_ul = False
    in_ol = False
    i = 0

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            close_lists()
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            i += 1
            continue

        if in_code:
            out.append(html.escape(line))
            i += 1
            continue

        if not stripped:
            close_lists()
            i += 1
            continue

        # table
        if "|" in stripped and i + 1 < len(lines):
            sep = lines[i + 1].strip()
            if re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$", sep):
                close_lists()
                headers = [c.strip() for c in stripped.strip("|").split("|")]
                out.append("<table><thead><tr>")
                for h in headers:
                    out.append(f"<th>{inline_md(h)}</th>")
                out.append("</tr></thead><tbody>")
                i += 2
                while i < len(lines) and "|" in lines[i]:
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    out.append("<tr>")
                    for c in cells:
                        out.append(f"<td>{inline_md(c)}</td>")
                    out.append("</tr>")
                    i += 1
                out.append("</tbody></table>")
                continue

        # headings
        m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if m:
            close_lists()
            level = len(m.group(1))
            text = m.group(2).strip()
            hid = slugify(text)
            toc.append((level, text, hid))
            out.append(f"<h{level} id=\"{hid}\">{inline_md(text)}</h{level}>")
            i += 1
            continue

        if stripped in {"---", "***"}:
            close_lists()
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith(">"):
            close_lists()
            out.append(f"<blockquote>{inline_md(stripped.lstrip('>').strip())}</blockquote>")
            i += 1
            continue

        um = re.match(r"^[-*+]\s+(.+)$", stripped)
        if um:
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline_md(um.group(1))}</li>")
            i += 1
            continue

        om = re.match(r"^\d+\.\s+(.+)$", stripped)
        if om:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{inline_md(om.group(1))}</li>")
            i += 1
            continue

        close_lists()
        out.append(f"<p>{inline_md(stripped)}</p>")
        i += 1

    close_lists()
    if in_code:
        out.append("</code></pre>")

    return Rendered("\n".join(out), toc)


def shell(
    title: str,
    description: str,
    canonical_path: str,
    body: str,
    *,
    extra_head: str = "",
    page_class: str = "",
) -> str:
    canonical = f"{BASE_URL}{canonical_path}"
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{html.escape(title)}</title>
  <meta name=\"description\" content=\"{html.escape(description)}\">
  <meta property=\"og:type\" content=\"website\">
  <meta property=\"og:title\" content=\"{html.escape(title)}\">
  <meta property=\"og:description\" content=\"{html.escape(description)}\">
  <meta property=\"og:url\" content=\"{html.escape(canonical)}\">
  <link rel=\"canonical\" href=\"{html.escape(canonical)}\">
  <link rel=\"alternate\" type=\"application/rss+xml\" title=\"Provara Blog\" href=\"{BASE_URL}/rss.xml\">
  <link rel=\"stylesheet\" href=\"/assets/site.css\">
  {extra_head}
</head>
<body class=\"{page_class}\">
<header class=\"site-header\">
  <div class=\"wrap\">
    <a href=\"/\" class=\"brand\">Provara</a>
    <nav>
      <a href=\"/spec/v1.0/\">Spec v1.0</a>
      <a href=\"/docs/\">Docs</a>
      <a href=\"/blog/\">Blog</a>
      <a href=\"https://github.com/provara-protocol/provara\">GitHub</a>
    </nav>
  </div>
</header>
<main class=\"wrap\">{body}</main>
<footer class=\"site-footer\">
  <div class=\"wrap\">
    <p>Apache 2.0. <a href=\"https://github.com/provara-protocol/provara\">GitHub</a>. Anthropic-free zone.</p>
  </div>
</footer>
</body>
</html>
"""


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_markdown_page(
    *,
    title: str,
    description: str,
    source_md: Path,
    out_path: Path,
    canonical_path: str,
    sidebar: str = "",
    extra_head: str = "",
) -> None:
    rendered = markdown_to_html(source_md.read_text(encoding="utf-8"))
    body = f"""
<div class=\"doc-layout\">
  <aside class=\"sidebar\">{sidebar}</aside>
  <article class=\"prose\">{rendered.html}</article>
</div>
"""
    write(out_path, shell(title, description, canonical_path, body, extra_head=extra_head, page_class="doc-page"))


def build_landing() -> None:
    body = """
<section class=\"hero\">
  <p class=\"eyebrow\">Provara Protocol</p>
  <h1>Self-sovereign cryptographic event logs</h1>
  <p class=\"subtitle\">Provara Protocol makes memory tamper-evident, replayable, and readable on a 50-year horizon.</p>
  <div class=\"cta\">
    <a class=\"btn primary\" href=\"/playground/\">Try Playground</a>
    <a class=\"btn\" href=\"/spec/v1.0/\">Read Spec</a>
    <a class=\"btn\" href=\"/docs/quickstart/\">Install (pip/npm)</a>
  </div>
</section>
<section class=\"cards\">
  <article class=\"card\"><h2>Tamper-Evident</h2><p>Every event is signed and hash-chained. Evidence can be verified independently.</p></article>
  <article class=\"card\"><h2>Self-Sovereign</h2><p>Vault operators own keys and logs. No hosted dependency is required for verification.</p></article>
  <article class=\"card\"><h2>50-Year Horizon</h2><p>Append-only NDJSON, deterministic replay, and non-normative indexes for scale.</p></article>
</section>
"""
    write(
        OUT / "index.html",
        shell(
            "Provara Protocol",
            "Self-sovereign cryptographic event logs.",
            "/",
            body,
        ),
    )


def build_spec() -> None:
    source = ROOT / "docs" / "BACKPACK_PROTOCOL_v1.0.md"
    rendered = markdown_to_html(source.read_text(encoding="utf-8"))

    toc_items = []
    for level, text, hid in rendered.toc:
        if level <= 3:
            toc_items.append(f'<li class="toc-l{level}"><a href="#{hid}">{html.escape(text)}</a></li>')
    toc_html = "<ul class=\"toc\">" + "".join(toc_items) + "</ul>"

    citation_meta = """
<meta name=\"DC.title\" content=\"BACKPACK Protocol v1.0\">
<meta name=\"DC.identifier\" content=\"https://provara.dev/spec/v1.0/\">
<meta name=\"DC.publisher\" content=\"Provara\">
<meta name=\"DC.language\" content=\"en\">
<meta name=\"citation_title\" content=\"BACKPACK Protocol v1.0\">
<meta name=\"citation_public_url\" content=\"https://provara.dev/spec/v1.0/\">
"""

    body = f"""
<div class=\"spec-banner\">
  <strong>Version-Locked URL:</strong> <code>https://provara.dev/spec/v1.0/</code> (immutable)
</div>
<div class=\"doc-layout\">
  <aside class=\"sidebar\">
    <h2>Contents</h2>
    {toc_html}
  </aside>
  <article class=\"prose spec-prose\">{rendered.html}</article>
</div>
"""

    write(
        OUT / "spec" / "v1.0" / "index.html",
        shell(
            "Provara Protocol Spec v1.0",
            "Version-locked Provara Protocol specification for citation.",
            "/spec/v1.0/",
            body,
            extra_head=citation_meta,
            page_class="spec-page",
        ),
    )
    redirect = """<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"0; url=/spec/v1.0/\"><link rel=\"canonical\" href=\"https://provara.dev/spec/v1.0/\"></head><body><p>Redirecting to <a href=\"/spec/v1.0/\">/spec/v1.0/</a>...</p></body></html>"""
    write(OUT / "spec" / "index.html", redirect)


def build_docs() -> None:
    docs_sidebar = """
<h2>Documentation</h2>
<ul>
  <li><a href=\"/docs/\">Hub</a></li>
  <li><a href=\"/docs/quickstart/\">Quickstart</a></li>
  <li><a href=\"/docs/tutorials/\">Tutorials</a></li>
  <li><a href=\"/docs/api-reference/\">API Reference</a></li>
  <li><a href=\"/docs/cookbook/\">Cookbook</a></li>
</ul>
"""

    hub = """
<section class=\"hero hero-small\">
  <p class=\"eyebrow\">Documentation</p>
  <h1>Read, run, and verify</h1>
  <p class=\"subtitle\">Core docs rendered from repository markdown.</p>
</section>
<section class=\"cards\">
  <article class=\"card\"><h2><a href=\"/docs/quickstart/\">Quickstart</a></h2><p>Install, bootstrap, append, and verify.</p></article>
  <article class=\"card\"><h2><a href=\"/docs/tutorials/\">Tutorials</a></h2><p>Step-by-step operational guides.</p></article>
  <article class=\"card\"><h2><a href=\"/docs/api-reference/\">API Reference</a></h2><p>Module-level API docs for Python interfaces.</p></article>
  <article class=\"card\"><h2><a href=\"/docs/cookbook/\">Cookbook</a></h2><p>Applied patterns and deployment recipes.</p></article>
</section>
"""
    write(OUT / "docs" / "index.html", shell("Provara Docs", "Documentation hub for Provara.", "/docs/", hub))

    render_markdown_page(
        title="Quickstart | Provara Docs",
        description="Provara quickstart.",
        source_md=ROOT / "docs" / "QUICKSTART.md",
        out_path=OUT / "docs" / "quickstart" / "index.html",
        canonical_path="/docs/quickstart/",
        sidebar=docs_sidebar,
    )
    render_markdown_page(
        title="Tutorials | Provara Docs",
        description="Provara tutorials index.",
        source_md=ROOT / "docs" / "tutorials" / "README.md",
        out_path=OUT / "docs" / "tutorials" / "index.html",
        canonical_path="/docs/tutorials/",
        sidebar=docs_sidebar,
    )
    render_markdown_page(
        title="API Reference | Provara Docs",
        description="Provara API reference hub.",
        source_md=ROOT / "docs" / "api-reference" / "index.md",
        out_path=OUT / "docs" / "api-reference" / "index.html",
        canonical_path="/docs/api-reference/",
        sidebar=docs_sidebar,
    )
    render_markdown_page(
        title="Cookbook | Provara Docs",
        description="Provara cookbook index.",
        source_md=ROOT / "docs" / "cookbook" / "README.md",
        out_path=OUT / "docs" / "cookbook" / "index.html",
        canonical_path="/docs/cookbook/",
        sidebar=docs_sidebar,
    )


def build_playground_redirect() -> None:
    target = "https://playground.provara.dev"
    page = f"""<!doctype html>
<html lang=\"en\"><head>
<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Redirecting to Playground</title>
<meta http-equiv=\"refresh\" content=\"0; url={target}\">
<link rel=\"canonical\" href=\"{target}\">
</head><body>
<p>Redirecting to <a href=\"{target}\">{target}</a>...</p>
</body></html>
"""
    write(OUT / "playground" / "index.html", page)
    write(OUT / "playground.html", page)


def blog_posts() -> list[tuple[str, str, str, str]]:
    posts = []
    for md_path in sorted((ROOT / "content" / "blog").glob("*.md")):
        md = md_path.read_text(encoding="utf-8")
        rendered = markdown_to_html(md)
        title = md_path.stem.replace("-", " ").title()
        for level, text, _ in rendered.toc:
            if level == 1:
                title = text
                break
        slug = md_path.stem
        excerpt = ""
        for line in md.splitlines():
            if line.strip() and not line.startswith("#"):
                excerpt = line.strip()
                break
        posts.append((slug, title, excerpt, rendered.html))
    return posts


def build_blog() -> None:
    posts = blog_posts()
    items = []
    rss_items = []
    now = dt.datetime.now(dt.timezone.utc)

    for slug, title, excerpt, body in posts:
        path = f"/blog/{slug}/"
        items.append(f"<article class='post-card'><h2><a href='{path}'>{html.escape(title)}</a></h2><p>{html.escape(excerpt)}</p></article>")

        write(
            OUT / "blog" / slug / "index.html",
            shell(title, excerpt or title, path, f"<article class='prose'>{body}</article>", page_class="blog-page"),
        )

        pub = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
        rss_items.append(
            f"<item><title>{html.escape(title)}</title><link>{BASE_URL}{path}</link><guid>{BASE_URL}{path}</guid><pubDate>{pub}</pubDate><description>{html.escape(excerpt)}</description></item>"
        )

    index_body = "<section class='hero hero-small'><p class='eyebrow'>Blog</p><h1>Provara writing</h1></section>" + "".join(items)
    write(OUT / "blog" / "index.html", shell("Provara Blog", "Posts from the Provara team.", "/blog/", index_body))

    rss = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rss version=\"2.0\"><channel>
<title>Provara Blog</title>
<link>{BASE_URL}/blog/</link>
<description>Protocol, security, and implementation notes from Provara.</description>
{''.join(rss_items)}
</channel></rss>
"""
    write(OUT / "rss.xml", rss)


def build_meta_files(paths: Iterable[str]) -> None:
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    urls = []
    for p in sorted(set(paths)):
        urls.append(f"<url><loc>{BASE_URL}{p}</loc><lastmod>{today}</lastmod></url>")

    sitemap = "<?xml version='1.0' encoding='UTF-8'?>\n" + (
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>" + "".join(urls) + "</urlset>"
    )
    write(OUT / "sitemap.xml", sitemap)
    with gzip.open(OUT / "sitemap.xml.gz", "wb") as gz:
        gz.write(sitemap.encode("utf-8"))

    robots = f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n"
    write(OUT / "robots.txt", robots)
    write(OUT / "CNAME", "provara.dev\n")


def main() -> None:
    build_landing()
    build_spec()
    build_docs()
    build_playground_redirect()
    build_blog()

    paths = [
        "/",
        "/spec/v1.0/",
        "/docs/",
        "/docs/quickstart/",
        "/docs/tutorials/",
        "/docs/api-reference/",
        "/docs/cookbook/",
        "/playground/",
        "/blog/",
    ]
    for slug, _, _, _ in blog_posts():
        paths.append(f"/blog/{slug}/")

    build_meta_files(paths)


if __name__ == "__main__":
    main()
