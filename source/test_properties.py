# -*- coding: utf-8 -*-
"""Property listings stay off the site until published. No network."""
from __future__ import annotations

import unittest
from unittest import mock

import build


class PropertyTests(unittest.TestCase):
    def test_example_listing_is_not_live(self):
        ids = [p["id"] for p in build.property_data()["listings"]]
        self.assertIn("example-limassol-apartment", ids)
        live = [p["id"] for p in build.published_listings()]
        self.assertEqual(live, ["bellissimo", "olivia", "the-city-home-2"])
        sm = build.sitemap()
        self.assertNotIn("example-limassol-apartment", sm)
        for pid in live:
            self.assertIn(f"https://cynews24.net/en/real-estate/{pid}/", sm)
        olivia = next(p for p in build.published_listings() if p["id"] == "olivia")
        self.assertEqual(build._prop_price(olivia, "en"), "Price on request")
        self.assertEqual(build._prop_price(olivia, "ru"), "Цена по запросу")
        self.assertEqual(build._prop_price(olivia, "el"), "Τιμή κατόπιν αιτήματος")
        villa = next(p for p in build.published_listings() if p["id"] == "bellissimo")
        self.assertIn("+ VAT", build._prop_price(villa, "en"))
        self.assertIn("без НДС", build._prop_price(villa, "ru"))
        self.assertIn("πλέον ΦΠΑ", build._prop_price(villa, "el"))

    def test_real_estate_page_lists_published_homes_and_can_be_empty(self):
        with mock.patch.object(build, "mycytax_catalog", return_value=object()), \
             mock.patch.object(build.mycytax, "projects_html", return_value=""):
            html = build.page_cat("en", "real-estate")
        self.assertIn("Bellissimo Villa", html)
        self.assertIn("Olivia Mansion", html)
        self.assertIn("The City Home 2", html)
        self.assertNotIn("example-limassol-apartment", html)
        self.assertNotIn("No property listings are published yet.", html)
        self.assertIn('href="/en/real-estate/"', build.header("en", lambda x: f"/{x}/"))
        self.assertIn("Real Estate", build.header("en", lambda x: f"/{x}/real-estate/", "real-estate"))
        with mock.patch.object(build, "published_listings", return_value=[]):
            self.assertIn("No property listings are published yet.", build.listings_block("en"))
            self.assertIn("Опубликованных объявлений пока нет.", build.listings_block("ru"))
            self.assertIn("Δεν υπάρχουν δημοσιευμένες αγγελίες ακόμη.", build.listings_block("el"))
