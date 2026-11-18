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
        self.assertEqual(build.published_listings(), [])
        self.assertNotIn("example-limassol-apartment", build.sitemap())

    def test_real_estate_page_explains_the_empty_list(self):
        with mock.patch.object(build, "mycytax_catalog", return_value=object()), \
             mock.patch.object(build.mycytax, "projects_html", return_value=""):
            html = build.page_cat("en", "real-estate")
        self.assertIn("No property listings are published yet.", html)
        self.assertIn('href="/en/real-estate/"', build.header("en", lambda x: f"/{x}/"))
        self.assertIn("Real Estate", build.header("en", lambda x: f"/{x}/real-estate/", "real-estate"))
        ru = build.listings_block("ru")
        el = build.listings_block("el")
        self.assertIn("Опубликованных объявлений пока нет.", ru)
        self.assertIn("Δεν υπάρχουν δημοσιευμένες αγγελίες ακόμη.", el)
