import os
import re
import shutil
import json
from datetime import datetime
from xml.sax.saxutils import escape

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(SITE_DIR, "_source")
CONFIG_PATH = os.path.join(SOURCE_DIR, "_config.json")
LAYOUT_PATH = os.path.join(SOURCE_DIR, "_layout.html")

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

with open(LAYOUT_PATH, encoding="utf-8") as f:
    LAYOUT = f.read()

SKIP_FILES = {"_layout.html", "_config.json"}


def parse_source(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    if not raw.startswith("---"):
        return None, raw
    end = raw.index("---", 3)
    meta_block = raw[3:end].strip()
    body = raw[end + 3:].strip()
    meta = {}
    for line in meta_block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body


def parse_date(date_str):
    try:
        return datetime.strptime(date_str.strip(), "%d.%m.%Y")
    except ValueError:
        return None


def rfc2822(dt):
    return dt.strftime("%a, %d %b %Y 00:00:00 +0000")


def build_nav(active_key):
    parts = []
    for item in CONFIG["nav"]:
        css = "nav-link active" if item["active_key"] == active_key else "nav-link"
        parts.append(f'<a class="{css}" href="{item["href"]}">{item["label"]}</a>')
    return "\n            ".join(parts)


def build_back_link(category, category_label, archive_href):
    return f"""<div class="back-link-container">
        <a class="back-link" href="{archive_href}">
            &#9668; Back to {category_label} Archive
        </a>
    </div>
"""


def wrap_note_body(title, body):
    return f"""<article class="note-article">
        <header class="note-header">
            <h2 class="section-title">{title}</h2>
        </header>
        <div class="note-body">
            {body}
        </div>
    </article>"""


def render_page(page_title, active_key, content, back_link=""):
    nav = build_nav(active_key)
    page = LAYOUT
    page = page.replace("{{page_title}}", page_title)
    page = page.replace("{{nav}}", nav)
    page = page.replace("{{back_link}}", back_link)
    page = page.replace("{{content}}", content)
    page = page.replace("{{email}}", CONFIG["email"])
    return page


def get_category_label(category):
    return category.replace("-", " ").title()


def get_archive_path(category):
    all_cats = CONFIG["bible_books"] + CONFIG["topic_categories"]
    if category in all_cats:
        return f"/{category}/{category}.html"
    return "/"


def get_archive_href_relative(category):
    return f"{category}.html"


def collect_notes():
    notes = []
    for root, dirs, files in os.walk(SOURCE_DIR):
        dirs[:] = [d for d in dirs if not d.startswith("_")]
        for fname in files:
            if fname.startswith("_") or fname not in [f for f in files]:
                continue
            if fname in SKIP_FILES or not fname.endswith(".html"):
                continue
            fpath = os.path.join(root, fname)
            meta, body = parse_source(fpath)
            if meta is None:
                continue
            if meta.get("static") == "true":
                continue
            rel = os.path.relpath(fpath, SOURCE_DIR)
            notes.append({
                "meta": meta,
                "body": body,
                "source_path": fpath,
                "rel": rel.replace(os.sep, "/"),
            })
    return notes


def build_notes(notes):
    for note in notes:
        meta = note["meta"]
        body = note["body"]
        rel = note["rel"]
        title = meta.get("title", "Untitled")
        active_nav = meta.get("active_nav", "home")
        category = meta.get("category", "")
        category_label = get_category_label(category)

        rel_parts = rel.split("/")
        depth = len(rel_parts) - 1
        if depth == 1:
            archive_href = get_archive_href_relative(category)
        else:
            archive_href = "../" + get_archive_href_relative(category)

        back_link = build_back_link(category, category_label, archive_href)
        content = wrap_note_body(title, body)
        page = render_page(
            f"Ray's Notes - {title}",
            active_nav,
            content,
            back_link=back_link
        )

        out_path = os.path.join(SITE_DIR, rel)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page)

        source_dir = os.path.dirname(note["source_path"])
        out_dir = os.path.dirname(out_path)
        for asset in os.listdir(source_dir):
            if not asset.endswith(".html") and not asset.startswith("_"):
                src = os.path.join(source_dir, asset)
                dst = os.path.join(out_dir, asset)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)

    print(f"  Built {len(notes)} note pages.")


def build_archives(notes):
    all_cats = CONFIG["bible_books"] + CONFIG["topic_categories"]
    for category in all_cats:
        cat_notes = [n for n in notes if n["meta"].get("category") == category]
        cat_notes.sort(
            key=lambda n: parse_date(n["meta"].get("date", "01.01.1970")) or datetime.min,
            reverse=True
        )
        label = get_category_label(category)
        is_bible = category in CONFIG["bible_books"]
        active_nav = "bible" if is_bible else "topics"
        parent_page = "/bible-notes.html" if is_bible else "/topics.html"
        parent_label = "Bible Notes Index" if is_bible else "Topics Index"

        items_html = ""
        for n in cat_notes:
            rel = n["rel"]
            rel_parts = rel.split("/")
            note_filename = rel_parts[-1]
            date_str = n["meta"].get("date", "")
            title = n["meta"].get("title", "Untitled")
            items_html += f"""            <div class="list-item">
                    <span class="list-bullet">&bull;</span>
                    <span class="list-date">{date_str}</span>
                    <a class="list-link" href="{note_filename}">{title}</a>
                </div>\n"""

        content = f"""<section>
            <div class="back-link-container">
                <a class="back-link" href="{parent_page}">
                    &#9668; Back to {parent_label}
                </a>
            </div>
            <h2 class="section-title">{label} - Notes</h2>
            <div class="notes-list-container">
{items_html}            </div>
        </section>"""

        page = render_page(f"Ray's Notes - {label} Notes", active_nav, content)
        out_path = os.path.join(SITE_DIR, category, f"{category}.html")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page)

    print(f"  Built {len(all_cats)} archive pages.")


def build_index_pages(notes):
    bible_books = CONFIG["bible_books"]
    topic_cats = CONFIG["topic_categories"]

    bible_items = ""
    for book in bible_books:
        label = get_category_label(book)
        bible_items += f"""                <li class="book-item">
                        <span class="book-bullet">&bull;</span>
                        <a class="book-link" href="{book}/{book}.html">{label}</a>
                    </li>\n"""

    bible_content = f"""<section>
            <h2 class="section-title">Bible Notes Index</h2>
            <div class="books-container">
                <ul class="books-list">
{bible_items}                </ul>
            </div>
        </section>"""

    page = render_page("Ray's Notes - Bible Notes Index", "bible", bible_content)
    with open(os.path.join(SITE_DIR, "bible-notes.html"), "w", encoding="utf-8") as f:
        f.write(page)

    topics_items = ""
    for cat in topic_cats:
        label = get_category_label(cat)
        topics_items += f"""                <li class="book-item">
                        <span class="book-bullet">&bull;</span>
                        <a class="book-link" href="{cat}/{cat}.html">{label}</a>
                    </li>\n"""

    topics_content = f"""<section>
            <h2 class="section-title">Topics Index</h2>
            <div class="books-container">
                <ul class="books-list">
{topics_items}                </ul>
            </div>
        </section>"""

    page = render_page("Ray's Notes - Topics Index", "topics", topics_content)
    with open(os.path.join(SITE_DIR, "topics.html"), "w", encoding="utf-8") as f:
        f.write(page)

    print("  Built bible-notes.html and topics.html.")


def build_homepage(notes):
    topic_notes = [n for n in notes if n["meta"].get("category") in CONFIG["topic_categories"]]
    dated = [(n, parse_date(n["meta"].get("date", ""))) for n in topic_notes]
    dated = [(n, d) for n, d in dated if d is not None]
    dated.sort(key=lambda x: x[1], reverse=True)
    recent = dated[:5]

    items_html = ""
    for note, dt in recent:
        rel = note["rel"]
        rel_parts = rel.split("/")
        href = "/".join(rel_parts)
        date_str = note["meta"].get("date", "")
        title = note["meta"].get("title", "Untitled")
        items_html += f"""            <div class="list-item">
                    <span class="list-bullet">&bull;</span>
                    <span class="list-date">{date_str}</span>
                    <a class="list-link" href="{href}">{title}</a>
                </div>\n"""

    content = f"""<section>
            <h2 class="section-title">Recent Posts</h2>
            <div class="post-list">
{items_html}            </div>
        </section>"""

    nav_html = build_nav("home")
    page = LAYOUT
    page = page.replace("{{page_title}}", "Ray's Notes")
    page = page.replace("{{nav}}", nav_html)
    page = page.replace("{{back_link}}", "")
    page = page.replace("{{content}}", content)
    page = page.replace("{{email}}", CONFIG["email"])

    with open(os.path.join(SITE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)

    print("  Built index.html.")


def build_about():
    about_src = os.path.join(SOURCE_DIR, "about.html")
    meta, body = parse_source(about_src)
    if meta is None:
        return
    active_nav = meta.get("active_nav", "about")
    page = render_page("Ray's Notes - About", active_nav, body)
    with open(os.path.join(SITE_DIR, "about.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print("  Built about.html.")


def extract_description(body):
    paras = re.findall(r"<p(?:[^>]*)>(.*?)</p>", body, re.DOTALL)
    text_paras = []
    for p in paras:
        text = re.sub(r"<[^>]+>", "", p).strip()
        if text and not text.startswith("+JMJ"):
            text_paras.append(text)
        if len(text_paras) == 2:
            break
    return " ".join(text_paras)


def build_feed(notes):
    base = CONFIG["base_url"].rstrip("/")
    dated = [(n, parse_date(n["meta"].get("date", ""))) for n in notes]
    dated = [(n, d) for n, d in dated if d is not None]
    dated.sort(key=lambda x: x[1], reverse=True)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        f"    <title>{escape(CONFIG['site_title'])}</title>",
        f"    <link>{base}</link>",
        "    <description>Notes and reflections on theology, typology, and the Catholic faith.</description>",
        "    <language>en</language>",
        f'    <atom:link href="{base}/feed.xml" rel="self" type="application/rss+xml"/>',
    ]
    for note, dt in dated:
        rel = note["rel"]
        url = f"{base}/{rel}"
        title = note["meta"].get("title", "Untitled")
        desc = extract_description(note["body"])
        lines += [
            "    <item>",
            f"      <title>{escape(title)}</title>",
            f"      <link>{escape(url)}</link>",
            f"      <guid>{escape(url)}</guid>",
            f"      <pubDate>{rfc2822(dt)}</pubDate>",
            f"      <description>{escape(desc)}</description>",
            "    </item>",
        ]
    lines += ["  </channel>", "</rss>"]
    feed_xml = "\n".join(lines) + "\n"
    with open(os.path.join(SITE_DIR, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(feed_xml)
    print(f"  Built feed.xml with {len(dated)} items.")


def main():
    print("Building rayg.space...")
    notes = collect_notes()
    print(f"  Found {len(notes)} source notes.")
    build_notes(notes)
    build_archives(notes)
    build_index_pages(notes)
    build_homepage(notes)
    build_about()
    build_feed(notes)
    print("Done.")


if __name__ == "__main__":
    main()
