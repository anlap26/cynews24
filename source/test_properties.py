# -*- coding: utf-8 -*-
"""Property listings stay off the site until published. No network."""
from __future__ import annotations

import os
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

    def test_listing_pages_have_a_lead_form_and_no_invented_whatsapp(self):
        villa = next(p for p in build.published_listings() if p["id"] == "bellissimo")
        labels = {
            "en": ("Request info", "I&#x27;m interested in Bellissimo Villa", "Bellissimo Villa"),
            "ru": ("Оставить заявку", "Меня интересует Вилла Bellissimo", "Вилла Bellissimo"),
            "el": ("Ζητήστε πληροφορίες", "Ενδιαφέρομαι για Bellissimo Villa", "Bellissimo Villa"),
        }
        for lang, (label, interest, title) in labels.items():
            page = build.page_listing(lang, villa)
            card = build.listing_card(villa, lang)
            grid = build.listings_block(lang)
            self.assertIn('href="#lead"', page)
            self.assertIn(label, page)
            self.assertIn(f'action="{build.LEAD_FORM_ACTION}"', page)
            self.assertIn('method="POST"', page)
            self.assertIn(f'name="_subject" value="CyNews24 lead: {title}"', page)
            self.assertIn(f'name="listing" value="{title}"', page)
            self.assertIn(f'name="page" value="https://cynews24.net/{lang}/real-estate/bellissimo/"', page)
            self.assertIn('name="_template" value="table"', page)
            self.assertIn('name="_captcha" value="false"', page)
            self.assertIn('name="_honey"', page)
            self.assertIn(f'name="_next" value="https://cynews24.net/{lang}/thanks/"', page)
            self.assertIn('name="name" required', page)
            self.assertIn('name="phone" required', page)
            self.assertIn('type="email" name="email"', page)
            self.assertNotIn('name="email" required', page)
            self.assertIn(f'<textarea name="message">{interest}</textarea>', page)
            self.assertNotIn('name="message" required', page)
            self.assertIn('name="consent" value="yes" required', page)
            self.assertNotIn("wa.me", page)
            self.assertNotIn('class="wa"', page)
            self.assertIn(f'href="/{lang}/real-estate/bellissimo/#lead"', card)
            self.assertIn(label, card)
            self.assertIn(f'href="/{lang}/real-estate/bellissimo/#lead"', grid)
            thanks = build.page_lead_thanks(lang)
            self.assertIn('content="noindex,follow"', thanks)
            self.assertIn(f'href="/{lang}/real-estate/"', thanks)

    def test_consultation_and_advertise_use_the_leads_inbox(self):
        self.assertEqual(build.LEADS_EMAIL, "2877novosti@gmail.com")
        self.assertEqual(build.LEADS_FORM_ACTION, "https://formsubmit.co/2877novosti@gmail.com")
        self.assertEqual(build.LEAD_FORM_ACTION, "https://formsubmit.co/2877novosti@gmail.com")
        with open(os.path.join(os.path.dirname(__file__), "build.py"), encoding="utf8") as handle:
            source = handle.read()
        self.assertNotIn("cs1.atex", source)
        self.assertNotIn("cynews42.com", source)
        story = build.STORIES[0]
        action = 'action="https://formsubmit.co/2877novosti@gmail.com"'
        for lang in ("en", "ru", "el"):
            article = build.page_article(lang, story)
            consult = build.page_property_consultation(lang)
            advertise = build.page_advertise(lang)
            advertising = build.page_advertising(lang)
            for html in (article, consult, advertise, advertising, build.footer(lang), build.header(lang, lambda x: f"/{x}/")):
                self.assertNotIn("cs1.atex", html)
                self.assertNotIn("cynews42.com", html)
            self.assertIn(action, article)
            self.assertIn(action, consult)
            self.assertIn(action, advertise)
            self.assertIn(action, advertising)
            self.assertIn('name="_subject" value="cynews24 property lead"', article)
            self.assertIn('name="_captcha" value="true"', article)
            self.assertIn(f'href="/{lang}/privacy/"', article)
            self.assertIn('name="consent" value="yes" required', article)
            self.assertIn('name="_subject" value="cynews24 advertising enquiry"', advertise)
            self.assertIn(f'href="/{lang}/advertise/"', build.footer(lang))
            self.assertIn('content="noindex,follow"', build.page_advertise_thanks(lang))
            self.assertIn('content="noindex,follow"', build.page_property_consult_thanks(lang))

    def test_russian_listing_copy(self):
        listings = {p["id"]: p for p in build.published_listings()}
        bellissimo = listings["bellissimo"]
        olivia = listings["olivia"]
        city = listings["the-city-home-2"]
        bell_card = build.listing_card(bellissimo, "ru")
        olivia_card = build.listing_card(olivia, "ru")
        city_card = build.listing_card(city, "ru")
        self.assertIn("<h3>Вилла Bellissimo</h3>", bell_card)
        self.assertNotIn('<span class="cat">Вилла</span>', bell_card)
        self.assertIn("3 спальни", bell_card)
        self.assertNotIn("3 спален", bell_card)
        self.assertIn("<h3>Особняк Olivia</h3>", olivia_card)
        self.assertIn('<span class="cat">Вилла</span>', olivia_card)
        self.assertIn("6 спален", olivia_card)
        self.assertIn("<h3>The City Home 2</h3>", city_card)
        self.assertIn('<span class="cat">Проект</span>', city_card)
        self.assertIn("3 спальни", city_card)
        self.assertNotIn("3 спален", city_card)
        bell_page = build.page_listing("ru", bellissimo)
        olivia_page = build.page_listing("ru", olivia)
        self.assertNotIn('<p class="cat">Вилла</p>', bell_page)
        self.assertIn("<h1>Вилла Bellissimo</h1>", bell_page)
        self.assertIn("3 спальни", bell_page)
        self.assertIn('<p class="cat">Вилла</p>', olivia_page)
        self.assertIn("Крытая жилая площадь", olivia_page)
        self.assertNotIn("Крылая", olivia_page)
        self.assertEqual(
            [build._bedroom_phrase(n, "ru") for n in (1, 2, 3, 4, 5, 11, 12, 14, 21, 22)],
            ["1 спальня", "2 спальни", "3 спальни", "4 спальни", "5 спален",
             "11 спален", "12 спален", "14 спален", "21 спальня", "22 спальни"],
        )
        self.assertIn("3 bedrooms", build.listing_card(bellissimo, "en"))
        self.assertIn('<span class="cat">Villa</span>', build.listing_card(bellissimo, "en"))

    def test_whatsapp_button_appears_only_with_a_stored_number(self):
        villa = dict(next(p for p in build.published_listings() if p["id"] == "olivia"))
        villa["contact"] = {"whatsapp": "35799111222"}
        page = build.page_listing("en", villa)
        card = build.listing_card(villa, "en")
        self.assertIn('class="wa" href="https://wa.me/35799111222"', page)
        self.assertIn('class="wa" href="https://wa.me/35799111222"', card)
        self.assertEqual(page.count('class="wa"'), 1)
        self.assertEqual(card.count('class="wa"'), 1)
