# -*- coding: utf-8 -*-
"""The guides hub: explainers in the sitemap, off the news channels, with FAQ and hreflang."""
import os
import re
import unittest

import build
import facebook_post
import telegram_digest
import telegram_post

HERE = os.path.dirname(os.path.abspath(__file__))
ARTICLES = os.path.join(HERE, "content", "articles")
NEW = (
    "cyprus-schengen-2026",
    "ees-etias-cyprus-2026",
    "cyprus-digital-nomad-visa-2026",
    "cost-of-living-cyprus-2026",
    "cyprus-non-dom-tax-2026",
    "buying-property-cyprus-foreigner",
    "cyprus-weather-by-month",
    "beaches-in-cyprus",
    "flights-to-cyprus",
    "cyprus-malta-portugal-relocation",
    "renting-in-cyprus",
    "gesy-for-foreigners",
    "driving-in-cyprus",
    "bank-account-cyprus",
    "open-a-company-in-cyprus",
    "cysec-forex-crypto",
    "jobs-and-pay-cyprus",
    "cyprus-and-the-region",
    "cyprus-tax-residency-2026",
    "eu-residence-cyprus",
)


class GuideHubTests(unittest.TestCase):
    def test_new_guides_are_bilingual_explainers(self):
        self.assertGreaterEqual(len(NEW), 20)
        for slug in NEW:
            story = build.BYSLUG[slug]
            self.assertTrue(story["guide"], slug)
            self.assertEqual(story["missing"], {"el"}, slug)
            self.assertTrue(story.get("updated"), slug)
            for lang in ("en", "ru"):
                self.assertGreaterEqual(len(story["faq"][lang]), 4, (slug, lang))
                self.assertLessEqual(len(story["desc"][lang]), 160, (slug, lang))
                self.assertIn("<h1>", build.page_article(lang, story))

    def test_hub_lists_them_and_the_nav_points_at_it(self):
        for lang in ("en", "ru"):
            html = build.page_guides(lang)
            self.assertIn(f"<h1>{'Guides to Cyprus' if lang == 'en' else 'Гиды по Кипру'}</h1>", html)
            self.assertIn(f'hreflang="en" href="https://cynews24.net/en/guides/"', html)
            self.assertIn(f'hreflang="ru" href="https://cynews24.net/ru/guides/"', html)
            self.assertIn('hreflang="el"', html)
            for slug in NEW:
                self.assertIn(f"/{lang}/{slug}/", html)
        greek = build.page_guides("el")
        self.assertIn("/en/guides/", greek)
        for slug in NEW:
            self.assertNotIn(f"/el/{slug}/", greek)
        self.assertIn('href="/en/guides/"', build.header("en", lambda x: f"/{x}/"))

    def test_pages_have_faq_schema_hreflang_and_a_visible_update(self):
        story = build.BYSLUG["cyprus-schengen-2026"]
        html = build.page_article("en", story)
        self.assertIn('"@type": "FAQPage"', html)
        self.assertIn('"@type": "Article"', html)
        self.assertNotIn('"@type": "NewsArticle"', html)
        self.assertIn('rel="alternate" hreflang="ru"', html)
        self.assertIn('rel="alternate" hreflang="en"', html)
        self.assertNotIn('rel="alternate" hreflang="el"', html)
        self.assertIn("Updated:", html)
        self.assertIn('rel="sponsored nofollow noopener"', html)
        self.assertIn("https://aviasales.tpx.lt/1sQ7N99K", html)

    def test_guides_stay_out_of_news_surfaces(self):
        posted = {item.slug for item in telegram_post.load_articles(ARTICLES)}
        posted |= {item.slug for item in facebook_post.load_articles(ARTICLES)}
        posted |= {item.article.slug for item in telegram_digest.load_items(ARTICLES)}
        news = build.news_sitemap()
        sm = build.sitemap()
        feed = build.rss("en")
        home = build.page_home("en")
        for slug in NEW:
            self.assertNotIn(slug, posted)
            self.assertNotIn(slug, news)
            self.assertNotIn(slug, feed)
            self.assertNotIn(f"/en/{slug}/", home)
            self.assertIn(f"https://cynews24.net/en/{slug}/", sm)
            self.assertIn(f"https://cynews24.net/ru/{slug}/", sm)
            self.assertNotIn(f"https://cynews24.net/el/{slug}/", sm)
        self.assertIn("https://cynews24.net/en/guides/", sm)


if __name__ == "__main__":
    unittest.main()
