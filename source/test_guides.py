# -*- coding: utf-8 -*-
"""Affiliate guides: one config file, three languages, no invented prices in the buttons."""
import json
import os
import re
import unittest

import build
import facebook_post
import telegram_digest
import telegram_post

HERE = os.path.dirname(os.path.abspath(__file__))
ARTICLES = os.path.join(HERE, "content", "articles")
SLUGS = ("international-health-insurance", "protect-data-foreign-banks")
LANGS = ("ru", "en", "el")
PARTNERS = ("safetywing", "genki", "airalo", "nordvpn", "surfshark", "proton", "onepassword")


def _words(text):
    return re.findall(r"[0-9A-Za-zΑ-Ωα-ωΆ-ώА-Яа-яЁё’']+", text)


class GuideContentTests(unittest.TestCase):
    def test_affiliate_config_is_the_only_partner_map(self):
        with open(os.path.join(HERE, "affiliates.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(set(data), set(PARTNERS))
        for key, value in data.items():
            self.assertTrue(value.startswith("#AFFILIATE_"), value)
        self.assertEqual(build.AFFILIATES, data)

    def test_guides_are_long_enough_in_every_language(self):
        for slug in SLUGS:
            story = build.BYSLUG[slug]
            self.assertTrue(story["guide"], slug)
            self.assertEqual(story["missing"], set(), slug)
            for lang in LANGS:
                words = _words(build.plain_body(story["body"][lang]))
                self.assertGreaterEqual(len(words), 1200, (slug, lang, len(words)))
                self.assertLessEqual(len(words), 2000, (slug, lang, len(words)))
                self.assertGreaterEqual(len(story["faq"][lang]), 4, (slug, lang))
                desc = story["desc"][lang]
                self.assertTrue(desc, (slug, lang))
                self.assertLessEqual(len(desc), 160, (slug, lang, len(desc)))
                for key in story["offers"][lang]:
                    self.assertIn(key, build.AFFILIATES)

    def test_rendered_page_reads_links_from_the_config(self):
        for slug in SLUGS:
            for lang in LANGS:
                html = build.page_article(lang, build.BYSLUG[slug])
                self.assertIn(f'href="https://cynews24.net/{lang}/{slug}/"', html)
                self.assertIn('hreflang="ru"', html)
                self.assertIn('hreflang="en"', html)
                self.assertIn('hreflang="el"', html)
                self.assertIn('hreflang="x-default"', html)
                self.assertIn('"@type": "Article"', html)
                self.assertNotIn('"@type": "NewsArticle"', html)
                self.assertIn('"@type": "FAQPage"', html)
                self.assertIn('rel="nofollow sponsored noopener"', html)
                self.assertIn('target="_blank"', html)
                self.assertIn("/assets/js/affiliates.js", html)
                self.assertIn(f"/{lang}/affiliate-disclosure/", html)
                for key in build.BYSLUG[slug]["offers"][lang]:
                    self.assertIn(f'data-affiliate="{key}"', html)
                    self.assertIn(f'href="{build.AFFILIATES[key]}"', html)
                for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html):
                    json.loads(block)
                # No euro prices invented next to a partner button.
                self.assertNotRegex(html, r'class="affbtn"[^>]*>[^<]*€')

    def test_widgets_stay_off_ordinary_news(self):
        news = build.page_article("en", build.BYSLUG["nicosia-murder-massage-parlour"])
        self.assertNotIn('class="partner"', news)
        self.assertNotIn("data-affiliate", news)
        for slug in (
            "relocating-to-cyprus",
            "cyprus-resident-handbook",
            "mortgage-cyprus-germany-greece-spain",
            "fintech-jobs-not-registrations",
        ):
            html = build.page_article("en", build.BYSLUG[slug])
            self.assertIn('class="partner"', html)
            self.assertIn("data-affiliate", html)
            self.assertIn("/en/affiliate-disclosure/", html)

    def test_guides_are_not_posted_as_news(self):
        articles = telegram_post.load_articles(ARTICLES)
        facebook = facebook_post.load_articles(ARTICLES)
        digest = telegram_digest.load_items(ARTICLES)
        posted = {item.slug for item in articles}
        posted |= {item.slug for item in facebook}
        posted |= {item.article.slug for item in digest}
        for slug in SLUGS:
            self.assertNotIn(slug, posted)

    def test_sitemap_lists_guides_and_the_disclosure(self):
        xml = build.sitemap()
        for slug in SLUGS:
            for lang in LANGS:
                self.assertIn(f"https://cynews24.net/{lang}/{slug}/", xml)
        for lang in LANGS:
            self.assertIn(f"https://cynews24.net/{lang}/affiliate-disclosure/", xml)
        news = build.news_sitemap()
        for slug in SLUGS:
            self.assertNotIn(slug, news)


if __name__ == "__main__":
    unittest.main()
