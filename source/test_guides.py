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
PARTNERS = ("genki", "airalo", "nordvpn", "surfshark", "proton", "onepassword")


def _words(text):
    return re.findall(r"[0-9A-Za-zΑ-Ωα-ωΆ-ώА-Яа-яЁё’']+", text)


class GuideContentTests(unittest.TestCase):
    def test_affiliate_config_is_the_only_partner_map(self):
        with open(os.path.join(HERE, "affiliates.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(set(data) - {"amazon", "trezor"}, set(PARTNERS))
        self.assertEqual(data["trezor"], "https://affil.trezor.io/aff_c?offer_id=352&aff_id=847056")
        economy = build.page_cat("en", "economy")
        self.assertIn('rel="sponsored nofollow noopener"', economy)
        self.assertIn('href="https://affil.trezor.io/aff_c?offer_id=352&amp;aff_id=847056"', economy)
        self.assertIn("Trezor Safe 7", economy)
        self.assertIn("/en/affiliate-disclosure/", economy)
        crypto = [s for s in build.STORIES if build.crypto_story(s)]
        self.assertIn("cysec-forex-crypto", [s["slug"] for s in crypto])
        self.assertIn("paphos-crypto-phone-scam", [s["slug"] for s in crypto])
        self.assertNotIn("jobs-and-pay-cyprus", [s["slug"] for s in crypto])
        page = build.page_article("en", build.BYSLUG["cysec-forex-crypto"])
        self.assertIn('target="_blank"', page)
        self.assertIn("https://affil.trezor.io/aff_c?offer_id=352&amp;aff_id=847056", page)
        for key in PARTNERS:
            self.assertTrue(data[key].startswith("#AFFILIATE_"), data[key])
            self.assertEqual(build.AFFILIATES[key], data[key])
        amazon = data["amazon"]
        self.assertEqual(amazon["url"], "https://www.amazon.de/?tag=cynews24-21")
        self.assertEqual(amazon["search"], "https://www.amazon.de/s?k={query}&tag=cynews24-21")
        self.assertEqual(build.AFFILIATES["amazon"], amazon["url"])
        self.assertEqual(build.AFFILIATE_SEARCH["amazon"], amazon["search"])
        href = build.affiliate_href("amazon", "UK plug adapter Type G")
        self.assertEqual(href, "https://www.amazon.de/s?k=UK+plug+adapter+Type+G&tag=cynews24-21")
        self.assertNotIn("/dp/", href)
        self.assertNotIn("/gp/product/", href)

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
                self.assertIn(f'rel="canonical" href="https://cynews24.net/{lang}/{slug}/"', html)
                self.assertIn('hreflang="ru"', html)
                self.assertIn('hreflang="en"', html)
                self.assertIn('hreflang="el"', html)
                self.assertIn(f'hreflang="x-default" href="https://cynews24.net/en/{slug}/"', html)
                self.assertNotIn('hreflang="x-default" href="https://cynews24.net/"', html)
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

    def test_amazon_blocks_are_search_links_on_a_few_pages(self):
        expected = {
            "relocating-to-cyprus": ("UK plug adapter Type G", "power bank", "luggage scale"),
            "international-health-insurance": ("travel first aid kit", "digital thermometer", "UK plug adapter Type G"),
            "protect-data-foreign-banks": ("YubiKey", "USB data blocker", "hardware wallet"),
            "cyprus-resident-handbook": ("smart lock", "home security camera", "video doorbell"),
            "flights-to-cyprus": ("UK plug adapter Type G", "power bank", "luggage scale"),
        }
        notes = {
            "en": "As an Amazon Associate I earn from qualifying purchases.",
            "ru": "Как участник партнёрской программы Amazon я зарабатываю на соответствующих покупках.",
            "el": "Ως συνεργάτης της Amazon, κερδίζω από αγορές που πληρούν τις προϋποθέσεις.",
        }
        self.assertLessEqual(len(expected), 6)
        for slug, queries in expected.items():
            self.assertGreaterEqual(len(queries), 2)
            self.assertLessEqual(len(queries), 4)
            for lang in LANGS:
                html = build.page_article(lang, build.BYSLUG[slug])
                self.assertEqual(html.count('data-affiliate="amazon"'), len(queries), (slug, lang))
                self.assertIn('rel="sponsored nofollow noopener"', html)
                self.assertIn('target="_blank"', html)
                self.assertIn(notes[lang], html)
                self.assertIn(f"/{lang}/affiliate-disclosure/", html)
                for query in queries:
                    self.assertIn(f'data-affiliate-query="{query}"', html)
                    self.assertIn(build.affiliate_href("amazon", query).replace("&", "&amp;"), html)
                    self.assertIn("tag=cynews24-21", build.affiliate_href("amazon", query))
                    self.assertNotIn("/dp/", build.affiliate_href("amazon", query))
        news = build.page_article("en", build.BYSLUG["nicosia-murder-massage-parlour"])
        self.assertNotIn("cynews24-21", news)
        self.assertNotIn("amazon.de", news)
        for lang, sentence in notes.items():
            page = build.page_info(lang, "affiliate-disclosure", build.DISCLOSURE[lang], "WebPage")
            self.assertIn(sentence, page)
            self.assertIn("cynews24-21", page)

    def test_travel_links_live_in_one_config(self):
        self.assertEqual(build.TRAVEL_LINKS["BOOKING_URL"], "https://www.booking.com/")
        self.assertEqual(build.TRAVEL_LINKS["GETYOURGUIDE_URL"], "https://www.getyourguide.com/")
        self.assertEqual(build.TRAVEL_LINKS["DISCOVERCARS_URL"], "https://www.discovercars.com/")
        self.assertEqual(build.TRAVEL_LINKS["SAFETYWING_URL"], "https://safetywing.com/")
        self.assertEqual(build.TRAVEL_LINKS["AIRALO_URL"], "https://airalo.tpx.lt/nILAEUYZ")
        self.assertEqual(build.TRAVEL_LINKS["YESIM_URL"], "https://yesim.tpx.lt/L3JvkZOj")
        self.assertEqual(build.TRAVEL_LINKS["KLOOK_URL"], "https://klook.tpx.lt/xtutlwca")
        html = build.page_article("en", build.BYSLUG["renting-a-car-in-cyprus"])
        self.assertIn('rel="sponsored nofollow noopener"', html)
        self.assertIn("https://www.discovercars.com/", html)
        self.assertIn("https://kiwitaxi.tpx.lt/pmM77dyU", html)
        self.assertIn("https://tpx.lt/sJrz0dYS", html)
        esim = build.page_article("en", build.BYSLUG["esim-mobile-data-cyprus"])
        self.assertLess(esim.find("https://airalo.tpx.lt/nILAEUYZ"), esim.find("https://yesim.tpx.lt/L3JvkZOj"))
        self.assertIn('href="/en/travel/"', build.header("en", lambda x: f"/{x}/"))
        self.assertTrue(build.BYSLUG["esim-mobile-data-cyprus"]["guide"])

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
        self.assertIn(
            'hreflang="x-default" href="https://cynews24.net/en/international-health-insurance/"',
            xml)
        self.assertIn("<loc>https://cynews24.net/</loc>", xml)
        self.assertIn('hreflang="x-default" href="https://cynews24.net/"', xml)
        self.assertNotIn("https://cynews24.net/feed.xml", xml)
        self.assertNotIn("index.html", xml)
        for loc in re.findall(r"<loc>(.*?)</loc>", xml):
            self.assertTrue(loc.startswith("https://cynews24.net/"), loc)
            self.assertTrue(loc.endswith("/"), loc)
        news = build.news_sitemap()
        for slug in SLUGS:
            self.assertNotIn(slug, news)


if __name__ == "__main__":
    unittest.main()
