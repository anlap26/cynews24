# -*- coding: utf-8 -*-
"""Unit tests for MyCyTax cross-links. No network."""
from __future__ import annotations

import os
import unittest

import mycytax

HERE = os.path.dirname(os.path.abspath(__file__))


class Response:
    def __init__(self, payload, status=200):
        self.status = status
        self._payload = payload if isinstance(payload, bytes) else payload.encode("utf-8")

    def read(self, _limit=-1):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def catalog():
    return mycytax.load_catalog(use_network=False)


def ids(lang, title, body="", tags=None, cat=None):
    pages = mycytax.relevant_pages(lang, title, body, tags or [], cat or catalog())
    return [page.id for page in pages]


class MatchingTests(unittest.TestCase):
    def test_fallback_covers_guides_and_calculators(self):
        cat = catalog()
        self.assertEqual(cat.source, "fallback")
        self.assertGreaterEqual(len(cat.pages), 16)
        kinds = {page.kind for page in cat.pages}
        self.assertEqual(kinds, {"guide", "calculator"})
        for page in cat.pages:
            self.assertTrue(page.path.startswith("/guides/") or page.path.startswith("/calculators/"))
            self.assertNotEqual(page.path.rstrip("/").count("/"), 1)

    def test_language_urls_follow_the_live_site(self):
        cat = catalog()
        vat = cat.by_id["vat"]
        self.assertEqual(cat.home("en"), "https://mycytax.com/")
        self.assertEqual(cat.home("ru"), "https://mycytax.com/ru/")
        self.assertEqual(cat.home("el"), "https://mycytax.com/el/")
        self.assertNotIn("/en/", cat.home("en"))
        self.assertEqual(cat.url("en", vat), "https://mycytax.com/calculators/vat/")
        self.assertEqual(cat.url("ru", vat), "https://mycytax.com/ru/calculators/vat/")
        self.assertEqual(cat.url("el", vat), "https://mycytax.com/el/calculators/vat/")

    def test_unrelated_article_matches_nothing(self):
        self.assertEqual(ids("en", "A fencer takes youth Olympic bronze", "The bout lasted nine minutes.", ["fencing", "sport"]), [])
        self.assertEqual(ids("ru", "Сборная по фехтованию взяла бронзу", "Поединок длился девять минут.", ["фехтование"]), [])
        self.assertEqual(ids("el", "Χάλκινο μετάλλιο στην ξιφασκία", "Ο αγώνας κράτησε εννέα λεπτά.", ["αθλητισμός"]), [])

    def test_incidental_property_words_do_not_open_the_box(self):
        self.assertEqual(
            mycytax.topic_scores("en", "Assets stay frozen", "That does not mean property has been permanently confiscated.", []),
            {},
        )
        game = mycytax.topic_scores(
            "en", "Game studios", "The scheme offers tax breaks and an intellectual property box.", ["video games"],
        )
        self.assertIn("tax", game)
        self.assertNotIn("property", game)
        self.assertEqual(
            mycytax.topic_scores("en", "A meeting", "The town planning and housing department attended.", []),
            {},
        )
        self.assertIn("property", mycytax.topic_scores("en", "Families leave a coastal site", "", ["Cyprus housing"]))

    def test_greek_home_is_property_and_tax_home_is_residency(self):
        self.assertIn("property", mycytax.topic_scores("el", "Έξωση", "Τα τροχόσπιτα είναι μόνιμη κατοικία.", []))
        scores = mycytax.topic_scores("el", "Φορολογική κατοικία", "Ο κανόνας των 60 ημερών.", [])
        self.assertIn("residency", scores)
        self.assertIn("tax", scores)
        self.assertNotIn("property", scores)

    def test_word_boundaries_skip_lookalikes(self):
        self.assertEqual(mycytax.topic_scores("en", "The current parent took a taxi", "A syntax note.", ["staff"]), {})
        self.assertNotIn("rent", mycytax.topic_scores("en", "Different current affairs", "", []))
        self.assertNotIn("tax", mycytax.topic_scores("en", "Taxi drivers wait", "", []))

    def test_title_body_and_tags_each_count(self):
        self.assertIn("vat", mycytax.topic_scores("en", "VAT on new homes", "", []))
        self.assertEqual(mycytax.topic_scores("en", "VAT on new homes", "", [])["vat"], 3)
        self.assertEqual(mycytax.topic_scores("en", "A short note", "The bill introduces VAT.", [])["vat"], 1)
        self.assertEqual(mycytax.topic_scores("en", "A short note", "", ["VAT"])["vat"], 2)
        self.assertEqual(mycytax.topic_scores("ru", "Коротко", "", ["ипотека"])["mortgage"], 2)
        self.assertEqual(mycytax.topic_scores("el", "Σύντομα", "Νέος κανόνας για τη σύνταξη.", [])["pension"], 1)

    def test_languages_do_not_share_keywords(self):
        self.assertEqual(mycytax.topic_scores("en", "Пенсионная реформа", "Досрочная пенсия.", ["пенсии"]), {})
        self.assertEqual(mycytax.topic_scores("ru", "Pension reform starts in January", "", ["pensions"]), {})

    def test_vat_ranks_the_vat_calculator_first(self):
        self.assertEqual(ids("en", "VAT on a new home", "Buyers ask about the rate.", ["VAT"]), ["vat", "off-plan", "taxes-overview"])
        self.assertEqual(ids("ru", "НДС на новостройки", "", ["НДС"])[0], "vat")
        self.assertEqual(ids("el", "ΦΠΑ σε νέα κατοικία", "", ["ΦΠΑ"])[0], "vat")

    def test_pension_salary_and_social_insurance_use_tax_guides(self):
        expected = ["tax-residency", "non-dom", "taxes-overview"]
        self.assertEqual(ids("ru", "Пенсионная реформа", "Досрочная пенсия и фонды провидент.", ["пенсии"]), expected)
        self.assertEqual(ids("en", "Pension reform still aims for January", "Provident funds were discussed.", ["pensions"]), expected)
        self.assertEqual(ids("el", "Συνταξιοδοτική μεταρρύθμιση", "Η σύνταξη στα 63.", ["συντάξεις"]), expected)
        self.assertEqual(ids("en", "New salary scales for civil servants", "", ["salaries"]), expected)
        self.assertEqual(ids("ru", "Зарплаты бюджетников", "Оклад вырастет.", []), expected)
        self.assertEqual(ids("en", "Social insurance contributions rise", "", []), expected)
        self.assertEqual(ids("ru", "Социальное страхование", "Страховые взносы изменятся.", []), expected)
        self.assertEqual(ids("el", "Κοινωνικές ασφαλίσεις", "Ασφαλιστικές εισφορές.", []), expected)

    def test_property_sale_and_mortgage_pick_sale_guides(self):
        found = ids(
            "en",
            "Selling property in Cyprus: fines of up to €100,000",
            "Lenders must release the mortgage. A land registry search is required.",
            ["Cyprus property sale", "mortgage release"],
        )
        self.assertEqual(found, ["selling-and-taxes", "capital-gains", "title-deeds"])
        self.assertEqual(ids("ru", "Продажа недвижимости на Кипре", "Штраф и ипотека.", ["недвижимость"]), ["selling-and-taxes", "title-deeds", "capital-gains"])
        self.assertEqual(ids("el", "Πώληση ακινήτου στην Κύπρο", "Η υποθήκη μένει.", ["ακίνητα"])[0], "selling-and-taxes")

    def test_mortgage_only_still_returns_several_links(self):
        found = ids("en", "Banks rewrite the mortgage rules", "", ["mortgages"])
        self.assertEqual(found[0], "mortgage")
        self.assertGreaterEqual(len(found), 2)
        self.assertLessEqual(len(found), 3)
        self.assertIn("transfer-fees", found)

    def test_rent_prefers_rent_guides(self):
        self.assertEqual(ids("en", "Rents rose again", "", ["rental market"]), ["rental-yield", "renting-out"])
        self.assertEqual(ids("ru", "Аренда жилья дорожает", "", ["аренда"])[0], "rental-yield")
        self.assertEqual(ids("el", "Αυξάνονται τα ενοίκια", "", ["ενοίκιο"])[:2], ["rental-yield", "renting-out"])

    def test_residency_prefers_residency_guides(self):
        found = ids("en", "Tax residency and the 60-day rule", "A residence permit is separate.", ["non-dom"])
        self.assertEqual(found[0], "tax-residency")
        self.assertIn("residence-permit", found)
        self.assertIn("non-dom", found)

    def test_related_box_has_two_or_three_same_language_links(self):
        cat = catalog()
        html = mycytax.article_crosslink("ru", "Пенсионная реформа", "Досрочная пенсия.", ["пенсии"], cat)
        self.assertIn("<aside class=\"sister\"", html)
        self.assertIn("Полезно: гайды и калькуляторы MyCyTax", html)
        self.assertEqual(html.count("<li>"), 3)
        self.assertIn("https://mycytax.com/ru/guides/tax-residency/", html)
        self.assertNotIn("/en/", html)
        self.assertNotIn("class=\"sisterline\"", html)
        english = mycytax.article_crosslink("en", "VAT on a new home", "", ["VAT"], cat)
        self.assertIn("Useful: MyCyTax guides and calculators", english)
        self.assertIn("https://mycytax.com/calculators/vat/", english)
        self.assertNotIn("https://mycytax.com/en/", english)
        greek = mycytax.article_crosslink("el", "Σύνταξη και μεταρρύθμιση", "", [], cat)
        self.assertIn("Χρήσιμο: οδηγοί και υπολογιστές MyCyTax", greek)
        self.assertIn("https://mycytax.com/el/guides/tax-residency/", greek)

    def test_unrelated_article_is_one_generic_line(self):
        for lang, label, url in (
            ("ru", "MyCyTax — налоги и недвижимость на Кипре", "https://mycytax.com/ru/"),
            ("en", "MyCyTax — Cyprus tax &amp; property", "https://mycytax.com/"),
            ("el", "MyCyTax — φόροι και ακίνητα στην Κύπρο", "https://mycytax.com/el/"),
        ):
            html = mycytax.article_crosslink(lang, "Christmas market opens", "Lights go on tonight.", ["tourism"], catalog())
            self.assertIn('class="sisterline"', html)
            self.assertNotIn("<h2>", html)
            self.assertNotIn("<aside", html)
            self.assertEqual(html.count("<a "), 1)
            self.assertIn(label, html)
            self.assertIn(f'href="{url}"', html)

    def test_link_text_is_escaped(self):
        page = mycytax.Page("vat", "calculator", "/calculators/vat/", {"vat": 6}, {
            "en": "VAT & <fees>", "ru": "НДС", "el": "ΦΠΑ",
        })
        html = mycytax.article_crosslink("en", "VAT note", "", [], mycytax.Catalog([page]))
        self.assertIn("VAT &amp; &lt;fees&gt;", html)
        self.assertNotIn("VAT & <fees>", html)

    def test_footer_projects_block(self):
        cat = catalog()
        ru = mycytax.projects_html("ru", cat)
        self.assertIn('aria-label="Наши проекты"', ru)
        self.assertIn(">Наши проекты<", ru)
        self.assertIn('href="https://mycytax.com/ru/"', ru)
        self.assertIn("MyCyTax — налоги и недвижимость на Кипре", ru)
        en = mycytax.projects_html("en", cat)
        self.assertIn(">Our projects<", en)
        self.assertIn('href="https://mycytax.com/"', en)
        self.assertIn("MyCyTax — Cyprus tax &amp; property", en)
        self.assertNotIn("/en/", en)
        el = mycytax.projects_html("el", cat)
        self.assertIn(">Τα έργα μας<", el)
        self.assertIn('href="https://mycytax.com/el/"', el)
        self.assertIn("MyCyTax — φόροι και ακίνητα στην Κύπρο", el)


class SitemapTests(unittest.TestCase):
    def test_parse_keeps_leaf_guides_in_every_language(self):
        xml = """<?xml version="1.0"?>
        <urlset>
          <url><loc>https://mycytax.com/</loc></url>
          <url><loc>https://mycytax.com/about/</loc></url>
          <url><loc>https://mycytax.com/ru/privacy/</loc></url>
          <url><loc>https://mycytax.com/guides/</loc></url>
          <url><loc>https://mycytax.com/calculators/</loc></url>
          <url><loc>https://mycytax.com/calculators/vat/</loc></url>
          <url><loc>https://mycytax.com/ru/calculators/vat/</loc></url>
          <url><loc>https://mycytax.com/el/guides/tax-residency/</loc></url>
          <url><loc>https://example.com/guides/vat/</loc></url>
        </urlset>"""
        self.assertEqual(mycytax.parse_sitemap(xml), ["/calculators/vat/", "/guides/tax-residency/"])

    def test_timeout_uses_the_committed_fallback(self):
        seen = {}

        def opener(request, timeout):
            seen["timeout"] = timeout
            seen["url"] = request.full_url
            raise TimeoutError("timed out")

        cat = mycytax.load_catalog(opener=opener, timeout=3)
        self.assertEqual(seen["timeout"], 3)
        self.assertEqual(seen["url"], mycytax.SITEMAP_URL)
        self.assertEqual(cat.source, "fallback")
        self.assertEqual(len(cat.pages), len(catalog().pages))

    def test_http_error_uses_the_committed_fallback(self):
        def opener(_request, timeout):
            raise OSError(f"boom after {timeout}")

        cat = mycytax.load_catalog(opener=opener, timeout=2)
        self.assertEqual(cat.source, "fallback")
        self.assertTrue(cat.by_id["mortgage"])

    def test_empty_sitemap_uses_the_committed_fallback(self):
        def opener(_request, timeout):
            return Response("<urlset></urlset>")

        cat = mycytax.load_catalog(opener=opener, timeout=2)
        self.assertEqual(cat.source, "fallback")
        self.assertIn("taxes-overview", cat.by_id)

    def test_sitemap_drops_missing_pages_and_adds_new_ones(self):
        xml = """<urlset>
          <url><loc>https://mycytax.com/calculators/vat/</loc></url>
          <url><loc>https://mycytax.com/ru/calculators/vat/</loc></url>
          <url><loc>https://mycytax.com/el/calculators/vat/</loc></url>
          <url><loc>https://mycytax.com/about/</loc></url>
          <url><loc>https://mycytax.com/guides/social-insurance/</loc></url>
          <url><loc>https://mycytax.com/ru/guides/social-insurance/</loc></url>
          <url><loc>https://mycytax.com/el/guides/social-insurance/</loc></url>
        </urlset>"""

        def opener(_request, timeout):
            return Response(xml)

        cat = mycytax.load_catalog(opener=opener, timeout=2)
        self.assertEqual(cat.source, "sitemap")
        self.assertEqual(set(cat.by_id), {"vat", "social-insurance"})
        self.assertEqual(cat.by_id["vat"].label("ru"), "НДС на новое жильё")
        added = cat.by_id["social-insurance"]
        self.assertEqual(added.label("en"), "Social insurance")
        self.assertGreaterEqual(added.topics.get("social", 0), 5)
        self.assertEqual(cat.url("el", added), "https://mycytax.com/el/guides/social-insurance/")
        found = ids("en", "Social insurance contributions rise", "", [], cat)
        self.assertEqual(found[0], "social-insurance")


if __name__ == "__main__":
    unittest.main()
