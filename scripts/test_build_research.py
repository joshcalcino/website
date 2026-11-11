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
        "research/draft-note/index.html": "Stale draft HTML must not be copied",
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
    shutil.copytree(SITE / "templates", root / "templates")
    (root / "scripts").mkdir()
    shutil.copy2(SCRIPT, root / "scripts/build_research.py")
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


class ProductionBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.source = Path(cls.temporary.name) / "source"
        make_fixture(cls.source)
        cls.output = Path(cls.temporary.name) / "public"
        subprocess.run(
            [sys.executable, str(cls.source / "scripts/build_research.py"), "--output", str(cls.output)],
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
        for relative in ("index.html", "assets/site.css", "assets/site.js", "assets/test.png", ".nojekyll"):
            with self.subTest(path=relative):
                self.assertEqual((self.source / relative).read_bytes(), (self.output / relative).read_bytes())

    def test_editor_and_build_sources_are_not_published(self):
        for relative in (".pages.yml", ".github", ".git", "content", "templates", "scripts", "config", "docs", "README.txt"):
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

    def save_article(self):
        self.article_path.write_text(json.dumps(self.article), encoding="utf-8")

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


if __name__ == "__main__":
    unittest.main()
