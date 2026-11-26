# -*- coding: utf-8 -*-
"""Google Discover: large image preview, honest lead sizes, NewsArticle fields."""
import json
import os
import re
import tempfile
import unittest

from PIL import Image

import build

LANGS = ("ru", "en", "el")
ROBOTS = re.compile(r'<meta name="robots" content="([^"]*)">')
OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]*)">')
OG_W = re.compile(r'<meta property="og:image:width" content="(\d+)">')
OG_H = re.compile(r'<meta property="og:image:height" content="(\d+)">')
TW_CARD = re.compile(r'<meta name="twitter:card" content="([^"]*)">')
TW_IMAGE = re.compile(r'<meta name="twitter:image" content="([^"]*)">')
FIGURE = re.compile(r'<figure><img src="([^"]+)" srcset="([^"]+)" sizes="[^"]*" width="(\d+)" height="(\d+)"')


def tokens(value):
    return [part.strip() for part in value.split(",") if part.strip()]


def blocks(html):
    return [json.loads(chunk) for chunk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


def by_type(nodes, name):
    return [node for node in nodes if name in (node.get("@type") if isinstance(node.get("@type"), list) else [node.get("@type")])]


class DiscoverTests(unittest.TestCase):
    def test_robots_merges_the_large_preview_and_keeps_index_rules(self):
        self.assertEqual(
            build.robots_content("index,follow"),
            "index,follow,max-image-preview:large")
        self.assertEqual(
            build.robots_content("index,follow,max-image-preview:large,max-snippet:-1"),
            "index,follow,max-image-preview:large,max-snippet:-1")
        self.assertEqual(build.robots_content("noindex,follow"), "noindex,follow")
        merged = tokens(build.robots_content("follow"))
        self.assertEqual(merged[0], "index")
        self.assertIn("follow", merged)
        self.assertIn("max-image-preview:large", merged)
        self.assertNotIn("noindex", merged)

    def test_known_small_leads_are_exactly_the_published_exceptions(self):
        small = {story["slug"] for story in build.small_lead_stories()}
        self.assertEqual(small, set(build.KNOWN_SMALL_LEADS))
        self.assertEqual(build.enforce_lead_images() and True, True)
        self.assertTrue(build.lead_size_error("a-new-article", 800))
        self.assertTrue(build.lead_size_error("a-new-article", 0, placeholder=True))
        self.assertEqual(build.lead_size_error("a-new-article", 1600), "")
        self.assertEqual(build.lead_size_error("presidential-election-spending-cap", 850), "")

    def test_article_and_section_pages_expose_discover_meta(self):
        pages = []
        for lang in LANGS:
            pages.append(build.page_home(lang))
            pages.append(build.page_guides(lang))
            pages.append(build.page_travel(lang))
            pages.append(build.page_events(lang))
            for cat in build.CATS:
                pages.append(build.page_cat(lang, cat))
        for html in pages:
            found = ROBOTS.findall(html)
            self.assertEqual(len(found), 1)
            parts = tokens(found[0])
            self.assertIn("index", parts)
            self.assertIn("follow", parts)
            self.assertIn("max-image-preview:large", parts)
            self.assertNotIn("noindex", parts)
            self.assertEqual(TW_CARD.search(html).group(1), "summary_large_image")
            self.assertEqual(TW_IMAGE.search(html).group(1), OG_IMAGE.search(html).group(1))
            self.assertGreaterEqual(int(OG_W.search(html).group(1)), 1)
            self.assertGreaterEqual(int(OG_H.search(html).group(1)), 1)
        for lang in LANGS:
            for cat in build.CATS:
                html = build.page_cat(lang, cat)
                items = [s for s in build.sorted_all() if s["cat"] == cat]
                news = [s for s in items if not s.get("guide")]
                story = news[0] if news else items[0]
                ow, oh = build.lead_geometry(story)["og"]
                self.assertEqual(int(OG_W.search(html).group(1)), ow, cat)
                self.assertEqual(int(OG_H.search(html).group(1)), oh, cat)
                self.assertTrue(OG_IMAGE.search(html).group(1).endswith(f"/assets/img/{story['img']}-og.jpg"))

    def test_every_article_uses_its_real_lead_size(self):
        for story in build.STORIES:
            geo = build.lead_geometry(story)
            lw, lh = geo["lead"]
            ow, oh = geo["og"]
            for lang in LANGS:
                html = build.page_article(lang, story)
                found = ROBOTS.findall(html)
                self.assertEqual(len(found), 1, story["slug"])
                parts = tokens(found[0])
                if lang in story.get("missing", ()):
                    self.assertEqual(parts, ["noindex", "follow"])
                else:
                    self.assertIn("index", parts)
                    self.assertIn("follow", parts)
                    self.assertIn("max-image-preview:large", parts)
                    self.assertNotIn("noindex", parts)
                self.assertEqual(TW_CARD.search(html).group(1), "summary_large_image")
                image = OG_IMAGE.search(html).group(1)
                self.assertEqual(TW_IMAGE.search(html).group(1), image)
                self.assertTrue(image.endswith(f"/assets/img/{story['img']}-og.jpg"))
                self.assertEqual(int(OG_W.search(html).group(1)), ow)
                self.assertEqual(int(OG_H.search(html).group(1)), oh)
                figure = FIGURE.search(html)
                self.assertIsNotNone(figure, story["slug"])
                self.assertTrue(figure.group(1).endswith(f"/assets/img/{story['img']}-1200.webp"))
                self.assertEqual(int(figure.group(3)), lw)
                self.assertEqual(int(figure.group(4)), lh)
                self.assertIn(f"{lw}w", figure.group(2))
                kind = "Article" if story.get("guide") else "NewsArticle"
                article = by_type(blocks(html), kind)[0]
                images = article["image"]
                self.assertIsInstance(images, list)
                self.assertGreaterEqual(len(images), 1)
                self.assertEqual(images[0]["width"], lw)
                self.assertEqual(images[0]["height"], lh)
                self.assertTrue(images[0]["url"].endswith(f"/assets/img/{story['img']}-1200.webp"))
                self.assertEqual(article["headline"], story["title"][lang])
                self.assertIn("datePublished", article)
                self.assertIn("dateModified", article)
                self.assertEqual(article["author"]["@type"], "Organization")
                self.assertEqual(article["publisher"]["logo"]["width"], 512)
            if story["slug"] in build.KNOWN_SMALL_LEADS and not geo["placeholder"]:
                self.assertLess(lw, 1200, story["slug"])
            elif not geo["placeholder"]:
                self.assertGreaterEqual(lw, 1200, story["slug"])

    def test_written_files_match_the_published_size(self):
        small = build.BYSLUG["limassol-funeral-schoolgirl-kakopetria"]
        large = build.BYSLUG["filo-jet-tenth-arrest"]
        with tempfile.TemporaryDirectory() as tmp:
            for story in (small, large):
                geo = build.lead_geometry(story)
                lw, lh = geo["lead"]
                ow, oh = geo["og"]
                sw, sh = geo["small"]
                path = build.story_photo_path(story)
                credit = None if "upload" in story else build.CREDITS.get(story["img"])
                focus = tuple(credit.get("focus", [0.5, 0.5])) if credit else (0.5, 0.5)
                with Image.open(path) as src:
                    plain = build.cover_crop(src, lw, lh, focus)
                build.save_lead_files(story, plain, tmp)
                with Image.open(os.path.join(tmp, f"{story['img']}-1200.webp")) as im:
                    self.assertEqual(im.size, (lw, lh))
                with Image.open(os.path.join(tmp, f"{story['img']}-og.jpg")) as im:
                    self.assertEqual(im.size, (ow, oh))
                with Image.open(os.path.join(tmp, f"{story['img']}-600.webp")) as im:
                    self.assertEqual(im.size, (sw, sh))
            self.assertLess(build.lead_geometry(small)["lead"][0], 1200)
            self.assertEqual(build.lead_geometry(large)["lead"], (1200, 675))
            self.assertEqual(build.lead_geometry(large)["og"], (1200, 630))

    def test_writer_note_is_in_the_readme(self):
        with open(os.path.join(build.HERE, "..", "README.md"), encoding="utf8") as fh:
            readme = fh.read()
        self.assertIn("not clickbait", readme)
        self.assertIn("1200", readme)
