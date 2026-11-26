# -*- coding: utf-8 -*-
"""World-news regions, relocation hub, and the section pages that already existed."""
import unittest

import build

NEW = (
    "eu-summit-budget-ukraine-2026",
    "ibiza-diesel-tanker-sinks",
    "hernandez-de-cos-ecb-presidency",
    "poundland-enters-administration",
    "greece-borrows-below-france",
    "kuwait-intercepts-iranian-drones",
    "netanyahu-trial-judges-review",
    "iraq-sentences-french-is-suspects",
    "russia-barrage-ukraine-stavropol",
    "indonesia-bogor-mine-rescue",
    "kim-nuclear-arsenal-expansion",
    "bangkok-bangchak-depot-blast",
    "fcc-clears-spacex-orbital-datacentres",
    "musk-spacex-shares-for-children",
    "argentina-technical-recession",
    "ebola-congo-passes-12000",
    "zambia-generic-hiv-prevention-shot",
    "uk-refugee-transfer-eswatini",
)


class WorldSectionTests(unittest.TestCase):
    def test_new_stories_are_sourced_world_news_in_three_languages(self):
        self.assertGreaterEqual(len(NEW), 15)
        self.assertLessEqual(len(NEW), 20)
        seen = set()
        for slug in NEW:
            story = build.BYSLUG[slug]
            self.assertEqual(story["cat"], "world", slug)
            self.assertIn(story["region"], build.REGIONS, slug)
            seen.add(story["region"])
            self.assertFalse(story.get("guide"), slug)
            self.assertEqual(story["missing"], set(), slug)
            self.assertTrue(story["sources"], slug)
            self.assertTrue(story["sources"][0][1].startswith("https://"), slug)
            self.assertEqual(story["date"], "2026-11-26", slug)
            for lang in build.LANGS:
                self.assertGreaterEqual(len(story["body"][lang]), 3, (slug, lang))
                self.assertLessEqual(len(story["desc"][lang]), 165, (slug, lang))
                self.assertNotIn("firma", story["body"][lang])
        self.assertEqual(seen, set(build.REGIONS))

    def test_region_pages_keep_the_world_url_and_add_hreflang(self):
        sm = build.sitemap()
        for region in build.REGIONS:
            for lang in build.LANGS:
                self.assertIn(f"https://cynews24.net/{lang}/world/{region}/", sm)
        for lang in build.LANGS:
            self.assertIn(f"https://cynews24.net/{lang}/world/", sm)
            self.assertIn(f"https://cynews24.net/{lang}/relocation/", sm)
            self.assertIn(f"https://cynews24.net/{lang}/tourism/", sm)
            self.assertIn(f"https://cynews24.net/{lang}/economy/", sm)
            self.assertIn(f"https://cynews24.net/{lang}/real-estate/", sm)
            self.assertIn(f"https://cynews24.net/{lang}/events/", sm)
        html = build.page_region("en", "europe")
        self.assertIn('rel="canonical" href="https://cynews24.net/en/world/europe/"', html)
        self.assertIn('rel="alternate" hreflang="ru" href="https://cynews24.net/ru/world/europe/"', html)
        self.assertIn('rel="alternate" hreflang="el"', html)
        self.assertIn('"@type": "BreadcrumbList"', html)
        self.assertIn('"@type": "CollectionPage"', html)
        self.assertIn("/en/eu-summit-budget-ukraine-2026/", html)
        self.assertIn(">World news<", build.header("en", lambda x: f"/{x}/"))
        self.assertIn(">Мировые новости<", build.header("ru", lambda x: f"/{x}/"))

    def test_article_stays_at_the_old_address_and_is_a_newsarticle(self):
        story = build.BYSLUG["ibiza-diesel-tanker-sinks"]
        html = build.page_article("en", story)
        self.assertIn('rel="canonical" href="https://cynews24.net/en/ibiza-diesel-tanker-sinks/"', html)
        self.assertNotIn("/en/world/europe/ibiza", html)
        self.assertIn('"@type": "NewsArticle"', html)
        self.assertIn('"@type": "BreadcrumbList"', html)
        self.assertIn('href="/en/world/europe/"', html)
        self.assertIn("https://www.euronews.com/2026/11/26/ship-transporting-7000-tonnes-of-diesel-sinks-off-ibiza-one-crewman-dead", html)
        self.assertIn("<h1>", html)
        old = build.page_article("ru", build.BYSLUG["eu-ai-summit-dublin"])
        self.assertIn('rel="canonical" href="https://cynews24.net/ru/eu-ai-summit-dublin/"', old)

    def test_topic_hubs_link_existing_articles(self):
        for lang, h1 in (("en", "Relocation and expat life in Cyprus"), ("ru", "Переезд на Кипр и жизнь экспатов")):
            html = build.page_relocation(lang)
            self.assertIn(f"<h1>{h1}</h1>", html)
            self.assertIn(f"/{lang}/relocating-to-cyprus/", html)
            self.assertIn(f"/{lang}/economy/", html)
            self.assertIn('rel="canonical"', html)
        tourism = build.page_cat("en", "tourism")
        self.assertIn("Cyprus tourism news | CyNews 24", tourism)
        self.assertIn('href="/en/events/"', tourism)
        self.assertIn('href="/en/relocation/"', tourism)
        economy = build.page_cat("ru", "economy")
        self.assertIn('href="/ru/real-estate/"', economy)
        estate = build.page_cat("el", "real-estate")
        self.assertIn('href="/el/relocation/"', estate)
        events = build.page_events("en")
        self.assertIn('href="/en/tourism/"', events)
        self.assertIn("/en/nicosia-christmas-market-2026/", events)
        nav = build.header("en", lambda x: f"/{x}/")
        for href in ("/en/tourism/", "/en/economy/", "/en/real-estate/", "/en/events/", "/en/relocation/", "/en/world/"):
            self.assertIn(f'href="{href}"', nav)
