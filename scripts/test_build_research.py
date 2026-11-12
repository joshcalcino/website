"""Regression checks for CMS edits and the production publishing boundary."""

from contextlib import redirect_stderr, redirect_stdout
import base64
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree


SCRIPT = Path(__file__).with_name("build_research.py")
SITE = SCRIPT.parents[1]
SPEC = importlib.util.spec_from_file_location("build_research", SCRIPT)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def make_fixture(root):
    """Create editable content and public files owned entirely by the tests."""
    files = {
        "index.html": "<!doctype html><title>Existing home</title><p>Keep me.</p>",
        "assets/site.css": "body { color: black; }",
        "assets/site.js": "document.documentElement.dataset.ready = 'yes';",
        ".nojekyll": "",
        ".pages.yml": "content: []",
        ".github/workflows/pages.yml": "name: Test fixture",
        ".git/config": "[core]\nrepositoryformatversion = 0",
        "config/private.html": "Private configuration",
        "docs/private.html": "Private documentation",
        "README.txt": "Editor instructions",
        "_site/stale.html": "An earlier artifact must not become a nested public site",
        "research/draft-note/index.html": "Stale draft HTML must not be copied",
        "content/site.json": json.dumps({
            "name": "Fixture Person", "mobile_name": "Fixture mobile name",
            "footer": "Fixture copyright notice", "default_image": "/website/assets/test.png",
            "research_background": "/website/assets/test.png",
            "navigation": [
                {"label": "Fixture Home", "href": "/website/"},
                {"label": "Fixture Research", "href": "/website/research/"},
                {"label": "Fixture Outreach", "href": "/website/public-outreach/"},
                {"label": "Fixture Photos", "href": "/website/astrophotography/"},
            ],
            "not_found": {"title": "Fixture missing page", "message": "No fixture at this address.", "button_label": "Fixture home button"},
        }),
        "content/home.json": json.dumps({
            "title": "Fixture homepage | Fixture Person", "description": "Fixture home description",
            "background": "/website/assets/test.png", "name": "Fixture Person",
            "tagline": "Fixture scientist\nFixture teacher",
            "portrait": {"src": "/website/assets/test.png", "alt": "Fixture portrait"},
            "about_heading": "Fixture biography", "biography": "<p>Original fixture biography.</p>",
            "interests": "<p>Original fixture interests.</p>",
            "downloads": [{"label": "Fixture CV", "file": "/website/assets/resume.pdf"}],
            "social_links": [{"label": "Fixture profile", "url": "https://example.org/profile", "icon": "github"}],
        }),
        "content/outreach.json": json.dumps({
            "title": "Fixture outreach | Fixture Person", "description": "Fixture outreach description",
            "heading": "Fixture outreach", "background": "/website/assets/test.png",
            "introduction": "<p>Original fixture outreach introduction.</p>",
            "testimonials_intro": "<p>Fixture audience feedback.</p>",
            "testimonials": [{"quote": "<p>Fixture testimonial.</p>"}],
            "event_sections": [{"heading": "Fixture talks", "events": [{"date": "2026", "description": "<p>Original fixture event.</p>"}]}],
        }),
        "content/photography.json": json.dumps({
            "title": "Fixture photography | Fixture Person", "description": "Fixture photography description",
            "heading": "Fixture photography", "introduction": "<p>Fixture gallery introduction.</p>",
            "intro_image": {"src": "/website/assets/test.png", "alt": "Fixture introductory photograph"},
            "gallery": [
                {"image": "/website/assets/test.png", "original": "/website/assets/test.png", "alt": "First fixture photograph", "caption": "First fixture caption"},
                {"image": "/website/assets/test.png", "original": "", "alt": "Second fixture photograph", "caption": "Second fixture caption"},
            ],
        }),
        "content/research-overview.json": json.dumps({
            "title": "Fixture research", "description": "Test overview",
            "introduction": "<p>Test introduction.</p>",
        }),
    }
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    (root / "assets/test.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    ))
    (root / "assets/resume.pdf").write_bytes(b"%PDF-1.4\n% Synthetic test download\n%%EOF\n")
    shutil.copytree(SITE / "templates", root / "templates")
    (root / "scripts").mkdir()
    for name in ("build_research.py", "build_site.py", "home_page.py", "other_pages.py"):
        shutil.copy2(SCRIPT.with_name(name), root / "scripts" / name)
    articles = {}
    for slug, published in (("draft-note", False), ("published-note", True)):
        article = {
            "slug": slug, "title": "Fixture " + slug, "description": "Test article",
            "published": published, "subtitle": "Test subtitle", "intro_layout": "split",
            "summary": "<p>Test summary.</p>", "order": 1,
            "paper_url": "https://example.org/paper",
            "thumbnail": {"src": "/website/assets/test.png", "alt": "Test image", "caption": "Test caption"},
            "sections": [
                {"type": "text", "body": "<p>Test article body.</p>"},
                {"type": "figure", "src": "/website/assets/test.png", "alt": "Test figure", "caption": "Figure caption", "anchor": "test-figure"},
                {"type": "video", "youtube_id": "abcdefghijk", "title": "Test video", "caption": "Video caption"},
            ],
        }
        (root / f"content/research/{slug}.json").parent.mkdir(exist_ok=True)
        (root / f"content/research/{slug}.json").write_text(json.dumps(article), encoding="utf-8")
        articles[slug] = article
    return articles


class ImageDimensionTests(unittest.TestCase):
    def test_gif_logical_screen_dimensions_for_both_versions(self):
        with tempfile.TemporaryDirectory() as temporary:
            for header in (b"GIF87a", b"GIF89a"):
                with self.subTest(version=header.decode("ascii")):
                    path = Path(temporary) / (header.decode("ascii") + ".gif")
                    # A 640-by-480 logical screen; values span bytes to check endianness.
                    path.write_bytes(header + b"\x80\x02\xe0\x01\x00\x00\x00\x3b")
                    self.assertEqual(builder.image_dimensions(path), (640, 480))


class ProductionBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.source = Path(cls.temporary.name) / "source"
        make_fixture(cls.source)
        cls.output = Path(cls.temporary.name) / "public"
        subprocess.run(
            [sys.executable, str(cls.source / "scripts/build_site.py"), "--output", str(cls.output)],
            check=True, capture_output=True, text=True,
        )

    def test_unpublished_article_is_absent_everywhere(self):
        self.assertFalse((self.output / "research/draft-note").exists())
        overview = (self.output / "research/index.html").read_text()
        self.assertNotIn('href="/website/research/draft-note/"', overview)
        self.assertNotIn("Fixture draft-note", overview)
        sitemap = ElementTree.parse(self.output / "sitemap.xml")
        locations = {node.text for node in sitemap.iter() if node.tag.endswith("}loc")}
        self.assertNotIn(builder.ORIGIN + builder.BASE + "/research/draft-note/", locations)
        self.assertIn(builder.ORIGIN + builder.BASE + "/research/published-note/", locations)

    def test_published_article_and_existing_site_survive(self):
        article = (self.output / "research/published-note/index.html").read_text()
        self.assertIn("Fixture published-note", article)
        self.assertIn("https://www.youtube-nocookie.com/embed/abcdefghijk", article)
        homepage = (self.output / "index.html").read_text()
        self.assertIn('<h1 id="name">Fixture Person</h1>', homepage)
        self.assertIn("Original fixture biography.", homepage)
        self.assertIn('href="/website/assets/resume.pdf"', homepage)
        self.assertIn("Fixture scientist<br>Fixture teacher", homepage)
        for relative in ("assets/site.css", "assets/site.js", "assets/test.png", "assets/resume.pdf", ".nojekyll"):
            with self.subTest(path=relative):
                self.assertEqual((self.source / relative).read_bytes(), (self.output / relative).read_bytes())

    def test_editor_and_build_sources_are_not_published(self):
        for relative in (".pages.yml", ".github", ".git", "content", "templates", "scripts", "config", "docs", "README.txt", "_site"):
            with self.subTest(path=relative):
                self.assertFalse((self.output / relative).exists())
        self.assertFalse(list(self.output.rglob("*.py")))
        self.assertFalse(list(self.output.rglob("*.json")))


class ContentValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "source"
        self.article = make_fixture(self.root)["published-note"]
        self.article_path = self.root / "content/research/published-note.json"
        root_patch = patch.object(builder, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        path_patch = patch.object(sys, "path", [str(self.root / "scripts"), *sys.path])
        path_patch.start()
        self.addCleanup(path_patch.stop)

    def save_article(self):
        self.article_path.write_text(json.dumps(self.article), encoding="utf-8")

    def read_page(self, name):
        return json.loads((self.root / "content" / (name + ".json")).read_text(encoding="utf-8"))

    def save_page(self, name, data):
        (self.root / "content" / (name + ".json")).write_text(json.dumps(data), encoding="utf-8")

    def build(self, output):
        with patch.object(sys, "argv", [str(SCRIPT), "--output", str(output)]):
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                builder.main()

    def test_missing_or_null_optional_cms_fields_render_safely(self):
        original = json.loads(json.dumps(self.article))
        for missing in (True, False):
            with self.subTest(missing=missing):
                self.article = json.loads(json.dumps(original))
                optional = [(self.article, key) for key in ("subtitle", "paper_url", "order", "published", "intro_layout")]
                optional.append((self.article["thumbnail"], "caption"))
                optional.extend((section, "caption") for section in self.article["sections"] if section["type"] in {"figure", "video"})
                optional.extend((section, "anchor") for section in self.article["sections"] if section["type"] == "figure")
                for data, key in optional:
                    if missing:
                        data.pop(key, None)
                    else:
                        data[key] = None
                self.save_article()
                overview, articles = builder.load_content()
                article = next(article for article in articles if article["slug"] == "published-note")
                self.assertFalse(article["published"])
                self.assertEqual(article["order"], 10)
                self.assertEqual(article["intro_layout"], "stack")
                self.assertEqual((article["subtitle"], article["paper_url"], article["thumbnail"]["caption"]), ("", "", ""))
                pages = builder.render_pages(overview, articles)
                self.assertIn(Path("research/published-note/index.html"), pages)
                self.assertNotIn("None", pages[Path("research/published-note/index.html")])

    def test_invalid_required_content_fails_before_any_output_write(self):
        self.article["title"] = ""
        self.save_article()
        output = self.root.parent / "public"
        with patch.object(sys, "argv", [str(SCRIPT), "--output", str(output)]):
            with redirect_stderr(io.StringIO()) as error, redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    builder.main()
        self.assertEqual(result.exception.code, 2)
        self.assertIn("title must be a nonempty string", error.getvalue())
        self.assertFalse(output.exists())

    def test_homepage_biography_and_cv_edits_reach_the_public_page(self):
        home = self.read_page("home")
        home["biography"] = '<p>Edited biography with <strong>new work</strong>.</p>'
        home["downloads"] = [{"label": "Updated fixture CV", "file": "/website/assets/updated-cv.pdf"}]
        (self.root / "assets/updated-cv.pdf").write_bytes(b"%PDF-1.4\n% Updated synthetic CV\n%%EOF\n")
        self.save_page("home", home)
        output = self.root.parent / "edited-home"
        self.build(output)
        page = (output / "index.html").read_text()
        self.assertIn(home["biography"], page)
        self.assertNotIn("Original fixture biography.", page)
        self.assertIn('href="/website/assets/updated-cv.pdf">Updated fixture CV', page)
        self.assertNotIn('href="/website/assets/resume.pdf"', page)
        self.assertEqual((self.root / "assets/updated-cv.pdf").read_bytes(), (output / "assets/updated-cv.pdf").read_bytes())

    def test_outreach_events_and_gallery_caption_order_follow_saved_json(self):
        outreach = self.read_page("outreach")
        outreach["event_sections"][0]["events"] = [{"date": "Nov 2026", "description": "<p>A newly saved fixture talk.</p>"}]
        self.save_page("outreach", outreach)
        photography = self.read_page("photography")
        photography["gallery"].reverse()
        photography["gallery"][0]["caption"] = 'Edited caption with "quoted" stars & planets'
        self.save_page("photography", photography)
        output = self.root.parent / "edited-other-pages"
        self.build(output)
        outreach_page = (output / "public-outreach/index.html").read_text()
        self.assertIn("Nov 2026", outreach_page)
        self.assertIn("<p>A newly saved fixture talk.</p>", outreach_page)
        self.assertNotIn("Original fixture event.", outreach_page)
        gallery = (output / "astrophotography/index.html").read_text()
        self.assertIn('data-caption="Edited caption with &quot;quoted&quot; stars &amp; planets"', gallery)
        self.assertIn('aria-label="View photograph 1: Second fixture photograph"', gallery)
        self.assertLess(gallery.index('data-alt="Second fixture photograph"'), gallery.index('data-alt="First fixture photograph"'))

    def test_global_navigation_footer_and_404_settings_reach_every_page(self):
        site = self.read_page("site")
        site["navigation"][0]["label"] = "Edited Home Navigation"
        site["footer"] = "Edited fixture footer & attribution"
        site["not_found"] = {"title": "Edited missing title", "message": "Edited missing message", "button_label": "Edited home button"}
        self.save_page("site", site)
        output = self.root.parent / "edited-settings"
        self.build(output)
        for relative in ("index.html", "public-outreach/index.html", "astrophotography/index.html", "research/index.html", "research/published-note/index.html", "404.html"):
            with self.subTest(page=relative):
                page = (output / relative).read_text()
                self.assertIn("Edited Home Navigation</a>", page)
                self.assertIn("Edited fixture footer &amp; attribution", page)
                self.assertNotIn("Fixture copyright notice", page)
        missing = (output / "404.html").read_text()
        for value in site["not_found"].values():
            self.assertIn(value, missing)
        self.assertNotIn("/404.html", (output / "sitemap.xml").read_text())

    def test_invalid_new_page_data_fails_before_any_output_write(self):
        cases = [
            ("home", lambda data: data.update(biography="")),
            ("home", lambda data: data["downloads"][0].update(file="/website/assets/test.png")),
            ("outreach", lambda data: data["event_sections"][0]["events"][0].update(description="")),
            ("photography", lambda data: data["gallery"][0].update(image="/website/assets/missing.png")),
            ("site", lambda data: data.update(navigation=[])),
        ]
        for index, (name, mutate) in enumerate(cases):
            with self.subTest(page=name, case=index):
                original = self.read_page(name)
                invalid = json.loads(json.dumps(original))
                mutate(invalid)
                self.save_page(name, invalid)
                output = self.root.parent / ("invalid-new-page-" + str(index))
                with self.assertRaises(SystemExit) as result:
                    self.build(output)
                self.assertEqual(result.exception.code, 2)
                self.assertFalse(output.exists())
                self.save_page(name, original)

    def test_optional_new_page_lists_and_null_fields_render_safely(self):
        originals = {name: self.read_page(name) for name in ("home", "outreach", "photography", "site")}
        for missing in (True, False):
            with self.subTest(missing=missing):
                pages = json.loads(json.dumps(originals))
                for name, fields in (("home", ("tagline", "interests", "downloads", "social_links")), ("outreach", ("testimonials_intro", "testimonials", "event_sections")), ("photography", ("gallery",)), ("site", ("not_found",))):
                    for field in fields:
                        if missing:
                            pages[name].pop(field, None)
                        else:
                            pages[name][field] = None
                    self.save_page(name, pages[name])
                output = self.root.parent / ("optional-new-pages-" + str(missing))
                self.build(output)
                home = (output / "index.html").read_text()
                outreach = (output / "public-outreach/index.html").read_text()
                gallery = (output / "astrophotography/index.html").read_text()
                self.assertNotIn('<p id="cv"', home)
                self.assertNotIn("<blockquote>", outreach)
                self.assertNotIn('class="event-section"', outreach)
                self.assertNotIn("data-gallery-item", gallery)
                self.assertNotIn("None", home + outreach + gallery)
                self.assertIn("Page not found", (output / "404.html").read_text())
        # Nested cleared fields keep valid parent entries and use sensible fallbacks.
        for name, data in originals.items():
            self.save_page(name, data)
        home = self.read_page("home")
        home["social_links"][0]["icon"] = None
        self.save_page("home", home)
        outreach = self.read_page("outreach")
        outreach["event_sections"][0]["events"] = None
        self.save_page("outreach", outreach)
        photography = self.read_page("photography")
        photography["gallery"][0].update(caption=None, original=None)
        self.save_page("photography", photography)
        output = self.root.parent / "optional-nested-fields"
        self.build(output)
        self.assertIn('href="https://example.org/profile">Fixture profile</a>', (output / "index.html").read_text())
        self.assertNotIn("Original fixture event.", (output / "public-outreach/index.html").read_text())
        self.assertIn('href="/website/assets/test.png" data-gallery-item data-caption=""', (output / "astrophotography/index.html").read_text())


if __name__ == "__main__":
    unittest.main()
