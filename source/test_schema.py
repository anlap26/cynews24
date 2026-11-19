# -*- coding: utf-8 -*-
"""JSON-LD matches the fields Google documents for Article, Breadcrumb, FAQ and WebSite."""
import json
import re
import unittest
from datetime import datetime

import build

ISO_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")
LANGS = ("ru", "en", "el")
TRAVEL = (
    "best-things-to-do-cyprus-2026",
    "renting-a-car-in-cyprus",
    "where-to-stay-in-cyprus",
    "esim-mobile-data-cyprus",
)


def blocks(html):
    raw = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    out = []
    for chunk in raw:
        out.append(json.loads(chunk))
    return out


def types_of(node):
    found = []
    if isinstance(node, dict):
        kind = node.get("@type")
        if isinstance(kind, list):
            found.extend(kind)
        elif kind:
            found.append(kind)
        for value in node.values():
            found.extend(types_of(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(types_of(value))
    return found


def by_type(nodes, name):
    return [node for node in nodes if name in (node.get("@type") if isinstance(node.get("@type"), list) else [node.get("@type")])]


class SchemaTests(unittest.TestCase):
    def test_every_article_is_a_newsarticle_with_google_fields(self):
        for story in build.STORIES:
            for lang in LANGS:
                html = build.page_article(lang, story)
                nodes = blocks(html)
                articles = by_type(nodes, "NewsArticle")
                self.assertEqual(len(articles), 1, story["slug"])
                article = articles[0]
                self.assertEqual(article["headline"], story["title"][lang])
                self.assertTrue(article["headline"].strip())
                published = article["datePublished"]
                modified = article["dateModified"]
                self.assertRegex(published, ISO_OFFSET)
                self.assertRegex(modified, ISO_OFFSET)
                self.assertGreaterEqual(datetime.fromisoformat(modified), datetime.fromisoformat(published))
                author = article["author"]
                self.assertEqual(author["@type"], "Organization")
                self.assertEqual(author["name"], "CyNews 24")
                self.assertTrue(author["url"].startswith("https://cynews24.net/"))
                publisher = article["publisher"]
                self.assertEqual(publisher["@type"], "Organization")
                self.assertEqual(publisher["name"], "CyNews 24")
                logo = publisher["logo"]
                self.assertEqual(logo["@type"], "ImageObject")
                self.assertTrue(logo["url"].startswith("https://cynews24.net/"))
                self.assertGreaterEqual(logo["width"], 112)
                self.assertGreaterEqual(logo["height"], 112)
                images = article["image"]
                self.assertIsInstance(images, list)
                self.assertGreaterEqual(len(images), 1)
                image = images[0]
                self.assertEqual(image["@type"], "ImageObject")
                self.assertTrue(image["url"].startswith("https://"))
                self.assertGreaterEqual(image["width"] * image["height"], 50000)
                self.assertEqual(article["mainEntityOfPage"]["@id"], f"https://cynews24.net/{lang}/{story['slug']}/")
                self.assertEqual(article["inLanguage"], lang)
                crumbs = by_type(nodes, "BreadcrumbList")
                self.assertEqual(len(crumbs), 1, story["slug"])
                self._crumbs_ok(crumbs[0])
                if story["faq"][lang]:
                    faq = by_type(nodes, "FAQPage")
                    self.assertEqual(len(faq), 1, story["slug"])
                    for question in faq[0]["mainEntity"]:
                        self.assertEqual(question["@type"], "Question")
                        self.assertTrue(question["name"].strip())
                        self.assertTrue(question["acceptedAnswer"]["text"].strip())
                        self.assertIn(question["name"], html)
                else:
                    self.assertFalse(by_type(nodes, "FAQPage"), story["slug"])
                if len(story["steps"][lang]) >= 2:
                    howto = by_type(nodes, "HowTo")
                    self.assertEqual(len(howto), 1, story["slug"])
                    steps = howto[0]["step"]
                    self.assertGreaterEqual(len(steps), 2)
                    for step in steps:
                        self.assertEqual(step["@type"], "HowToStep")
                        self.assertTrue(step["name"].strip())
                        self.assertTrue(step["text"].strip())
                        self.assertIn(step["name"], html)
                        self.assertIn(step["text"][:40], html)
                else:
                    self.assertFalse(by_type(nodes, "HowTo"), story["slug"])

    def test_travel_guides_have_faq_and_only_the_esim_guide_is_a_howto(self):
        for slug in TRAVEL:
            for lang in LANGS:
                nodes = blocks(build.page_article(lang, build.BYSLUG[slug]))
                self.assertTrue(by_type(nodes, "FAQPage"), slug)
                self.assertEqual(bool(by_type(nodes, "HowTo")), slug == "esim-mobile-data-cyprus", slug)

    def test_home_pages_have_organization_and_website_and_no_fake_search(self):
        root = blocks(build.page_root())
        self.assertTrue(by_type(root, "WebSite"))
        self.assertTrue(by_type(root, "Organization"))
        self.assertNotIn("SearchAction", types_of(root))
        for lang in LANGS:
            nodes = blocks(build.page_home(lang))
            sites = by_type(nodes, "WebSite")
            orgs = by_type(nodes, "Organization")
            self.assertEqual(len(sites), 1)
            self.assertTrue(orgs)
            self.assertEqual(sites[0]["url"], f"https://cynews24.net/{lang}/")
            self.assertEqual(sites[0]["publisher"]["@id"], "https://cynews24.net/#org")
            self.assertEqual(orgs[0]["name"], "CyNews 24")
            self.assertTrue(orgs[0]["logo"]["url"].startswith("https://"))
            self.assertNotIn("SearchAction", types_of(nodes))

    def test_section_pages_have_breadcrumbs(self):
        pages = [
            build.page_cat("en", "tourism"),
            build.page_travel("ru"),
            build.page_events("el"),
            build.page_about("en"),
            build.page_advertise("ru"),
            build.page_advertising("el"),
            build.page_property_consultation("en"),
        ]
        listings = build.published_listings()
        if listings:
            pages.append(build.page_listing("en", listings[0]))
        for html in pages:
            crumbs = by_type(blocks(html), "BreadcrumbList")
            self.assertEqual(len(crumbs), 1)
            self._crumbs_ok(crumbs[0])

    def _crumbs_ok(self, crumb):
        items = crumb["itemListElement"]
        self.assertGreaterEqual(len(items), 2)
        for index, item in enumerate(items, start=1):
            self.assertEqual(item["@type"], "ListItem")
            self.assertEqual(item["position"], index)
            self.assertTrue(item["name"].strip())
            self.assertTrue(item["item"].startswith("https://cynews24.net/"))
