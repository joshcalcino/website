#!/usr/bin/env python3
"""Build the website from Pages CMS content, or package its public pages."""

import argparse
from functools import lru_cache
from html import escape
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import shutil
from string import Template
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
BASE = "/website"
ORIGIN = "https://joshcalcino.github.io"
BACKGROUND = BASE + "/assets/images/7145bb_4c72a5519133421f8156bef918339169~mv2.webp"
DEFAULT_IMAGE = BASE + "/assets/images/7145bb_4aac35370ef84cd1a2758e4939702e2d~mv2.webp"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
ANCHOR = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
SOURCE_DIRS = {"content", "templates", "scripts", "docs", "config", "node_modules", "__pycache__"}
EXCLUDED = SOURCE_DIRS | {"_site"}
STATIC_SUFFIXES = {".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".pdf", ".mp4", ".webm", ".webmanifest"}


def require_text(data, key, source, allow_empty=False):
    value = data.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{source}: {key} must be {'a string' if allow_empty else 'a nonempty string'}")
    return value


def asset_path(src, source, extensions=None):
    if not isinstance(src, str) or not src.startswith(BASE + "/assets/"):
        raise ValueError(f"{source}: asset paths must start with {BASE}/assets/")
    parsed = urlsplit(src)
    decoded = unquote(parsed.path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or decoded != src or "\\" in src:
        raise ValueError(f"{source}: unsafe asset path {src!r}")
    parts = src[len(BASE) + 1:].split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{source}: unsafe asset path {src!r}")
    path = ROOT.joinpath(*parts)
    if not path.is_file() or not path.resolve().is_relative_to((ROOT / "assets").resolve()):
        raise ValueError(f"{source}: local asset does not exist: {src}")
    if extensions and path.suffix.lower() not in extensions:
        raise ValueError(f"{source}: choose a file ending in {', '.join(sorted(extensions))}")
    return src


def image_path(src, source):
    return asset_path(src, source)


def link_url(value, source):
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise ValueError(f"{source}: enter a valid link")
    parsed = urlsplit(value)
    if parsed.scheme in {"https", "http"} and parsed.netloc:
        return value
    if parsed.scheme in {"mailto", "tel"} and parsed.path:
        return value
    if value.startswith("#") and len(value) > 1:
        return value
    if not parsed.scheme and not parsed.netloc and parsed.path.startswith(BASE + "/"):
        if "\\" not in value and not any(part == ".." for part in unquote(parsed.path).split("/")):
            return value
    raise ValueError(f"{source}: use a website path beginning {BASE}/ or a web/contact link")


class RichImages(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.source = source

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img":
            image_path(dict(attrs).get("src"), self.source)

    handle_startendtag = handle_starttag


def rich_text(data, key, source, allow_empty=False, optional=False):
    if optional and data.get(key) is None:
        data[key] = ""
    value = require_text(data, key, source, allow_empty)
    RichImages(source + ": " + key).feed(value)
    return value


def read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(ROOT)}: expected a JSON object")
    return data


def external_url(data, key, source):
    value = data.get(key, "")
    if value is None or value == "":
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{source}: {key} must be an HTTPS URL")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or any(char.isspace() for char in value):
        raise ValueError(f"{source}: {key} must be an HTTPS URL")
    return value


def load_content():
    overview_path = ROOT / "content/research-overview.json"
    overview = read_json(overview_path)
    source = "content/research-overview.json"
    require_text(overview, "title", source)
    require_text(overview, "description", source)
    rich_text(overview, "introduction", source)
    articles = []
    slugs = set()
    for path in sorted((ROOT / "content/research").glob("*.json")):
        article = read_json(path)
        source = str(path.relative_to(ROOT))
        slug = require_text(article, "slug", source)
        if not SLUG.fullmatch(slug) or slug in slugs:
            raise ValueError(f"{source}: slug must be a unique lowercase route such as infall or irs-48")
        slugs.add(slug)
        for key in ("title", "description"):
            require_text(article, key, source)
        if article.get("published") is None:
            article["published"] = False
        if not isinstance(article["published"], bool):
            raise ValueError(f"{source}: published must be true or false")
        if article.get("intro_layout") is None:
            article["intro_layout"] = "stack"
        if article["intro_layout"] not in ("stack", "split"):
            raise ValueError(f"{source}: intro_layout must be stack or split")
        rich_text(article, "subtitle", source, allow_empty=True, optional=True)
        rich_text(article, "summary", source)
        if article.get("order") is None:
            article["order"] = 10
        order = article.get("order")
        if isinstance(order, bool) or not isinstance(order, (int, float)) or not math.isfinite(order):
            raise ValueError(f"{source}: order must be a finite number")
        thumbnail = article.get("thumbnail")
        if not isinstance(thumbnail, dict):
            raise ValueError(f"{source}: thumbnail must be an object")
        image_path(thumbnail.get("src"), source + ": thumbnail")
        require_text(thumbnail, "alt", source + ": thumbnail")
        rich_text(thumbnail, "caption", source + ": thumbnail", allow_empty=True, optional=True)
        article["paper_url"] = external_url(article, "paper_url", source)
        sections = article.get("sections")
        if not isinstance(sections, list) or not sections:
            raise ValueError(f"{source}: sections must be a nonempty array")
        for index, section in enumerate(sections):
            label = f"{source}: section {index + 1}"
            if not isinstance(section, dict):
                raise ValueError(f"{label}: expected an object")
            kind = section.get("type")
            if kind == "text":
                rich_text(section, "body", label)
            elif kind == "figure":
                image_path(section.get("src"), label)
                require_text(section, "alt", label)
                rich_text(section, "caption", label, allow_empty=True, optional=True)
                if section.get("anchor") is None:
                    section["anchor"] = ""
                if not isinstance(section["anchor"], str) or (section["anchor"] and not ANCHOR.fullmatch(section["anchor"])):
                    raise ValueError(f"{label}: anchor must be a safe HTML ID such as streamer-simulation")
            elif kind == "video":
                video_id = require_text(section, "youtube_id", label)
                if not YOUTUBE_ID.fullmatch(video_id):
                    raise ValueError(f"{label}: youtube_id must be an 11-character YouTube ID")
                require_text(section, "title", label)
                rich_text(section, "caption", label, allow_empty=True, optional=True)
            else:
                raise ValueError(f"{label}: unknown section type {kind!r}")
        if article["intro_layout"] == "split" and (len(sections) < 2 or sections[0]["type"] != "text" or sections[1]["type"] != "figure"):
            raise ValueError(f"{source}: split intro_layout requires a text section followed by a figure")
        articles.append(article)
    if not articles:
        raise ValueError("content/research: at least one article JSON file is required")
    return overview, sorted(articles, key=lambda article: (article["order"], article["slug"]))


@lru_cache(maxsize=128)
def image_dimensions(path):
    """Read PNG, WebP, JPEG, or GIF dimensions without image-library dependencies."""
    data = path.read_bytes()
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24 and data[12:16] == b"IHDR":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        offset = 12
        while offset + 8 <= len(data):
            kind = data[offset:offset + 4]
            size = int.from_bytes(data[offset + 4:offset + 8], "little")
            body = data[offset + 8:offset + 8 + size]
            if kind == b"VP8X" and len(body) >= 10:
                return 1 + int.from_bytes(body[4:7], "little"), 1 + int.from_bytes(body[7:10], "little")
            if kind == b"VP8L" and len(body) >= 5 and body[0] == 0x2F:
                bits = int.from_bytes(body[1:5], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
            if kind == b"VP8 " and len(body) >= 10 and body[3:6] == b"\x9d\x01\x2a":
                return int.from_bytes(body[6:8], "little") & 0x3FFF, int.from_bytes(body[8:10], "little") & 0x3FFF
            offset += 8 + size + (size % 2)
    if data.startswith(b"\xff\xd8"):
        offset = 2
        frame_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while offset < len(data):
            if data[offset] != 0xFF:
                break
            while offset < len(data) and data[offset] == 0xFF:
                offset += 1
            if offset >= len(data):
                break
            marker = data[offset]
            offset += 1
            if marker in {0xD9, 0xDA}:
                break
            if marker in {0x01, 0xD8} or 0xD0 <= marker <= 0xD7:
                continue
            if offset + 2 > len(data):
                break
            size = int.from_bytes(data[offset:offset + 2], "big")
            if size < 2 or offset + size > len(data):
                break
            if marker in frame_markers and size >= 7:
                return int.from_bytes(data[offset + 5:offset + 7], "big"), int.from_bytes(data[offset + 3:offset + 5], "big")
            offset += size
    return None


def dimension_attributes(src):
    dimensions = image_dimensions(ROOT / src[len(BASE) + 1:])
    if dimensions and all(value > 0 for value in dimensions):
        return f' width="{dimensions[0]}" height="{dimensions[1]}"'
    return ""


def render_figure(section):
    src = escape(section["src"], quote=True)
    alt = escape(section["alt"], quote=True)
    anchor = ' id="' + section["anchor"] + '"' if section.get("anchor") else ""
    dimensions = dimension_attributes(section["src"])
    return f'<figure class="science-figure"{anchor}><a href="{src}" aria-label="Open figure at full size"><img src="{src}"{dimensions} alt="{alt}" loading="lazy" decoding="async"></a><figcaption>{section["caption"]}</figcaption></figure>'


def render_sections(sections, intro_layout="stack"):
    rendered = []
    start = 0
    if intro_layout == "split":
        rendered.append('<div class="research-card article-intro"><div>' + sections[0]["body"] + '</div>' + render_figure(sections[1]) + '</div>')
        start = 2
    for index, section in enumerate(sections):
        if index < start:
            continue
        if section["type"] == "text":
            body = section["body"]
            classes = "prose"
            if re.search(r'<ol\b[^>]*\bclass\s*=\s*[\'\"][^\'\"]*\bpaper-list\b', body, re.IGNORECASE) or re.search(r'<h2\b[^>]*>\s*Read the papers\s*</h2\s*>', body, re.IGNORECASE):
                classes += " infall-papers"
            elif index == 0 and not re.search(r'<h[1-6]\b', body, re.IGNORECASE):
                classes += " infall-introduction"
            rendered.append(f'<section class="{classes}">' + body + '</section>')
        elif section["type"] == "figure":
            rendered.append(render_figure(section))
        else:
            video_id = section["youtube_id"]
            title = escape(section["title"], quote=True)
            rendered.append(f'<figure class="video-figure"><iframe src="https://www.youtube-nocookie.com/embed/{video_id}" title="{title}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe><figcaption>{section["caption"]}</figcaption></figure>')
    return "\n".join(rendered)


def load_site_settings():
    source = "content/site.json"
    data = read_json(ROOT / source)
    for key in ("name", "mobile_name", "footer"):
        require_text(data, key, source)
    for key in ("default_image", "research_background"):
        image_path(data.get(key), source + ": " + key)
    navigation = data.get("navigation")
    if not isinstance(navigation, list) or not navigation:
        raise ValueError(f"{source}: navigation must contain at least one link")
    for index, item in enumerate(navigation):
        label = f"{source}: navigation link {index + 1}"
        if not isinstance(item, dict):
            raise ValueError(f"{label}: expected an object")
        require_text(item, "label", label)
        link_url(item.get("href"), label)
    if data.get("not_found") is None:
        data["not_found"] = {}
    if not isinstance(data["not_found"], dict):
        raise ValueError(f"{source}: not_found must be an object")
    for key, default in (("title", "Page not found"), ("message", "The page you requested is not here."), ("button_label", "Back to Home")):
        if data["not_found"].get(key) is None:
            data["not_found"][key] = default
        require_text(data["not_found"], key, source + ": not_found")
    return data


def render_document(title, description, route, body, *, settings, body_class="", background=None, image=None, article=False):
    navigation = []
    for item in settings["navigation"]:
        parsed = urlsplit(item["href"])
        target = BASE + route
        matches = parsed.path == target or (parsed.path != BASE + "/" and parsed.path.endswith("/") and target.startswith(parsed.path))
        active = matches and not parsed.fragment and (not parsed.netloc or parsed.netloc == urlsplit(ORIGIN).netloc)
        current = ' aria-current="page"' if active else ""
        navigation.append('<a href="' + escape(item["href"], quote=True) + '"' + current + '>' + escape(item["label"]) + '</a>')
    image = image or settings["default_image"]
    background_style = ' style="--page-image:url(\'' + escape(background, quote=True) + '\')"' if background else ""
    template = Template((ROOT / "templates/base.html").read_text(encoding="utf-8"))
    return template.substitute(
        title=escape(title), description=escape(description, quote=True), canonical=ORIGIN + BASE + route,
        image=escape(ORIGIN + image, quote=True), kind="article" if article else "website",
        body_class=escape(body_class, quote=True), background_style=background_style,
        extra_styles='<link rel="stylesheet" href="/website/assets/research/infall/infall.css">' if article else "",
        navigation="".join(navigation), mobile_name=escape(settings["mobile_name"]),
        footer=escape(settings["footer"]), body=body,
    )


def render_pages(overview, articles, settings=None):
    settings = settings if settings is not None else load_site_settings()
    templates = {name: Template((ROOT / "templates" / (name + ".html")).read_text(encoding="utf-8")) for name in ("research-overview", "research-card", "research-article")}

    def page(title, description, route, body, article=False, image=None):
        return render_document(title + " | " + settings["name"], description, route, body, settings=settings,
            body_class="photo-background research" + (" infall-article" if article else ""),
            background=settings["research_background"], image=image, article=article)

    pages = {}
    cards = []
    for article in articles:
        route = "/research/" + article["slug"] + "/"
        paper_link = '<a class="button secondary" href="' + escape(article["paper_url"], quote=True) + '">See the paper</a>' if article["paper_url"] else ""
        cards.append(templates["research-card"].substitute(slug=article["slug"], title=escape(article["title"]), summary=article["summary"], route=BASE + route, image=escape(article["thumbnail"]["src"], quote=True), dimensions=dimension_attributes(article["thumbnail"]["src"]), alt=escape(article["thumbnail"]["alt"], quote=True), caption=article["thumbnail"]["caption"], paper_link=paper_link))
        subtitle = '<div class="infall-subtitle">' + article["subtitle"] + '</div>' if article["subtitle"] else ""
        body = templates["research-article"].substitute(title=escape(article["title"]), subtitle=subtitle, sections=render_sections(article["sections"], article["intro_layout"]), paper_link=paper_link)
        pages[Path("research") / article["slug"] / "index.html"] = page(article["title"], article["description"], route, body, article=True, image=article["thumbnail"]["src"])
    body = templates["research-overview"].substitute(title=escape(overview["title"]), introduction=overview["introduction"], cards="\n".join(cards))
    pages[Path("research/index.html")] = page(overview["title"], overview["description"], "/research/", body)
    return pages


def render_not_found(settings):
    data = settings["not_found"]
    body = '<section class="content-width missing-page"><h1 class="section-heading">' + escape(data["title"]) + '</h1><p>' + escape(data["message"]) + '</p><a class="button" href="' + BASE + '/">' + escape(data["button_label"]) + '</a></section>'
    return render_document(data["title"] + " | " + settings["name"], data["message"], "/404.html", body,
        settings=settings, body_class="photography")


def public_files(output):
    files = []
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part.startswith(".") or part in EXCLUDED for part in relative.parts):
            continue
        if output != ROOT and path.is_relative_to(output):
            continue
        # Research pages in a deployment come only from published content below.
        if output != ROOT and relative.parts[0] == "research":
            continue
        if path.is_symlink():
            raise ValueError(f"Refusing to package a symbolic link: {relative}")
        if relative.parts[0] == "assets" or path.suffix == ".html" or (len(relative.parts) == 1 and (path.name in {"robots.txt", "sitemap.xml", "CNAME"} or path.suffix in STATIC_SUFFIXES)):
            files.append(relative)
    if (ROOT / ".nojekyll").is_file():
        files.append(Path(".nojekyll"))
    return files


def sitemap(files, pages):
    routes = set()
    for relative in set(files) | set(pages):
        if relative.suffix != ".html" or relative.name == "404.html":
            continue
        text = pages.get(relative)
        if text is None:
            text = (ROOT / relative).read_text(encoding="utf-8")
        if re.search(r'<meta\b[^>]*http-equiv\s*=\s*[\'\"]?refresh\b', text, re.IGNORECASE):
            continue
        route = relative.as_posix()
        route = route[:-len("index.html")] if route.endswith("index.html") else route
        routes.add(ORIGIN + BASE + "/" + route)
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ElementTree.register_namespace("", namespace)
    root = ElementTree.Element("{" + namespace + "}urlset")
    for route in sorted(routes):
        node = ElementTree.SubElement(root, "{" + namespace + "}url")
        ElementTree.SubElement(node, "{" + namespace + "}loc").text = route
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ElementTree.tostring(root, encoding="unicode") + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Build a complete public site into this directory instead of updating research pages in place.")
    args = parser.parse_args()
    output = args.output.expanduser().resolve() if args.output else ROOT
    try:
        if args.output is not None and output == ROOT:
            raise ValueError("--output must be a separate artifact directory; omit it for a local build including drafts")
        if output != ROOT and (ROOT.is_relative_to(output) or (output.is_relative_to(ROOT) and output.relative_to(ROOT).parts[0] in SOURCE_DIRS | {"assets", "research"})):
            raise ValueError("--output must be a separate artifact directory, not a source directory or its parent")
        if output != ROOT and output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError("--output must be an empty or new directory so stale or unpublished files cannot enter the deployment")
        import home_page
        import other_pages

        settings = load_site_settings()
        helpers = dict(read_json=read_json, require_text=require_text, rich_text=rich_text,
            image_path=image_path, asset_path=asset_path, link_url=link_url)
        home = home_page.load_content(ROOT, **helpers)
        other = other_pages.load_content(ROOT, **helpers)
        overview, articles = load_content()
        included = articles if output == ROOT else [article for article in articles if article["published"]]
        pages = render_pages(overview, included, settings)

        def document(*values, **options):
            return render_document(*values, settings=settings, **options)

        rendering = dict(root=ROOT, document=document, dimension_attributes=dimension_attributes)
        pages.update(home_page.render(home, **rendering))
        pages.update(other_pages.render(other, **rendering))
        pages[Path("404.html")] = render_not_found(settings)
        files = public_files(output)
        pages[Path("sitemap.xml")] = sitemap(files, pages)
        # Every content and template check above completes before the first write.
        if output != ROOT:
            for relative in files:
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
        for relative, text in pages.items():
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    mode = "Local build includes drafts" if output == ROOT else "Production artifact excludes drafts"
    print(f"{mode}: home, outreach, photography, research overview, {len(included)} articles, shared settings, and sitemap in {output}")


if __name__ == "__main__":
    main()
