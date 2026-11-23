# -*- coding: utf-8 -*-
"""Travel in Cyprus row: marker 808586 short links, only on travel-related stories."""
import re
import unittest

import build

LANGS = ("ru", "en", "el")
SHOW = {
    "best-things-to-do-cyprus-2026",
    "esim-mobile-data-cyprus",
    "nicosia-christmas-market-2026",
    "renting-a-car-in-cyprus",
    "tourist-arrivals-october",
    "where-to-stay-in-cyprus",
    "weekend-events-14-15-november",
    "short-term-rental-bed-cap",
}
HIDE = (
    "nicosia-murder-massage-parlour",
    "dubai-arrest-xiourouppas-plot",
    "governors-beach-caravan-eviction",
    "cape-greco-monastery-legalisation",
    "cyprus-inflation-october-2026",
    "christodoulides-erhurman-meeting",
    "international-health-insurance",
    "homes-without-electricity-paphos",
    "missing-mushroom-picker-paphos-forest",
    "kykkos-monastery-stabbing",
    "dream-tower-limassol-review",
    "eden-coast-paphos-review",
    "greek-investment-cyprus-9-billion",
    "november-17-blackout-rumour",
    "kyrenia-3-satellite",
    "microsoft-outage-second-day",
    "kakopetria-student-death",
)
DISCLOSURE = {
    "en": "Affiliate links: we may earn a commission at no extra cost to you.",
    "ru": "Партнёрские ссылки: мы можем получить комиссию без доплаты для вас.",
    "el": "Σύνδεσμοι συνεργατών: ενδέχεται να λάβουμε προμήθεια χωρίς επιπλέον χρέωση για εσάς.",
}
HEADINGS = {
    "en": "Travel in Cyprus",
    "ru": "Путешествие по Кипру",
    "el": "Ταξίδι στην Κύπρο",
}


def _box(html):
    found = re.findall(r'<aside class="travelbox".*?</aside>', html)
    return found


def _fake(cat, **langs):
    story = {"cat": cat, "title": {}, "kw": {}}
    for lang in LANGS:
        title, keywords = langs.get(lang, ("", []))
        story["title"][lang] = title
        story["kw"][lang] = keywords
    return story


class TravelBlockTests(unittest.TestCase):
    def test_short_links_are_exactly_the_marker_808586_set(self):
        urls = {item[0]: item[1] for item in build.TRAVEL_OFFERS}
        self.assertEqual(urls, {
            "localrent": "https://localrent.tpx.lt/XVEtrVFd",
            "welcome": "https://tpx.lt/HeqeBOtK",
            "kiwitaxi": "https://kiwitaxi.tpx.lt/TTuXoyTH",
            "klook": "https://klook.tpx.lt/xtutlwca",
            "tiqets": "https://tiqets.tpx.lt/PUqK4uu8",
            "airalo": "https://airalo.tpx.lt/Z3nl2F1z",
            "aviasales": "https://aviasales.tpx.lt/45iBpc4b",
        })
        for context, keys in build.TRAVEL_ORDER.items():
            self.assertGreaterEqual(len(keys), 4, context)
            self.assertLessEqual(len(keys), 6, context)
            self.assertEqual(len(keys), len(set(keys)), context)

    def test_current_stories_split_into_travel_and_everything_else(self):
        shown = {story["slug"] for story in build.STORIES if build.travel_relevant(story)}
        self.assertEqual(shown, SHOW)
        for slug in HIDE:
            self.assertNotIn(slug, shown)

    def test_keyword_lists_fire_in_each_language(self):
        airport = _fake(
            "society",
            ru=("Рейс в аэропорт Ларнаки задержали из-за тумана", []),
            en=("", []),
            el=("", []))
        # "задержали" is a crime word and must not hide a flight delay.
        self.assertTrue(build.travel_relevant(airport))
        self.assertEqual(build.travel_context(airport), "airport")
        beach = _fake("society", el=("Ο καιρός στις παραλίες της Αγίας Νάπας", ["παραλίες"]))
        self.assertTrue(build.travel_relevant(beach))
        self.assertEqual(build.travel_context(beach), "beach")
        festival = _fake("society", ru=("Фестиваль в Лимассоле", ["что делать на Кипре"]))
        self.assertTrue(build.travel_relevant(festival))
        self.assertEqual(build.travel_context(festival), "event")
        dubai = _fake(
            "society",
            en=("Wanted suspect arrested at Dubai airport", ["murder plot"]),
            ru=("В аэропорту Дубая задержали подозреваемого", []))
        self.assertFalse(build.travel_relevant(dubai))
        eviction = _fake(
            "real-estate",
            en=("Families told to leave the caravan site at Governor's Beach", ["eviction"]))
        self.assertFalse(build.travel_relevant(eviction))
        insurance = _fake(
            "society",
            en=("Health cover", ["travel medical insurance"]),
            ru=("Страховка", ["туристическая страховка"]),
            el=("Υγεία", ["ταξιδιωτική ασφάλιση"]))
        self.assertFalse(build.travel_relevant(insurance))
        revenue = _fake("economy", en=("Greek investment rose", ["Nicosia tourism revenue"]))
        self.assertFalse(build.travel_relevant(revenue))
        spending = _fake("economy", en=("Tourist spending in Cyprus fell", []))
        self.assertTrue(build.travel_relevant(spending))
        self.assertEqual(build.travel_context(spending), "default")

    def test_block_is_localised_and_ordered(self):
        orders = {
            "renting-a-car-in-cyprus": ("car", "https://localrent.tpx.lt/XVEtrVFd"),
            "esim-mobile-data-cyprus": ("esim", "https://airalo.tpx.lt/Z3nl2F1z"),
            "best-things-to-do-cyprus-2026": ("beach", "https://klook.tpx.lt/xtutlwca"),
            "where-to-stay-in-cyprus": ("stay", "https://localrent.tpx.lt/XVEtrVFd"),
            "nicosia-christmas-market-2026": ("event", "https://tiqets.tpx.lt/PUqK4uu8"),
            "weekend-events-14-15-november": ("event", "https://tiqets.tpx.lt/PUqK4uu8"),
            "tourist-arrivals-october": ("default", "https://klook.tpx.lt/xtutlwca"),
        }
        for slug, (context, first) in orders.items():
            self.assertEqual(build.travel_context(build.BYSLUG[slug]), context, slug)
            for lang in LANGS:
                html = build.page_article(lang, build.BYSLUG[slug])
                boxes = _box(html)
                self.assertEqual(len(boxes), 1, (slug, lang))
                box = boxes[0]
                self.assertIn(f'data-travel="{context}"', box)
                self.assertIn(f"<h2>{HEADINGS[lang]}</h2>", box)
                self.assertIn(DISCLOSURE[lang].split(":", 1)[1], box)
                self.assertIn(f'href="/{lang}/affiliate-disclosure/"', box)
                self.assertEqual(box.count('rel="sponsored nofollow noopener"'), 6, (slug, lang))
                self.assertEqual(box.count('target="_blank"'), 6, (slug, lang))
                self.assertNotIn("<script", box)
                self.assertNotIn("data-affiliate", box)
                self.assertLess(box.find(first), box.find("travelcards") + len(box))
                hrefs = re.findall(r'href="(https?://[^"]+)"', box)
                self.assertEqual(hrefs[0], first, (slug, lang))
                self.assertEqual(len(hrefs), 6, (slug, lang))

    def test_airport_story_leads_with_transfer_flights_and_esim(self):
        story = _fake("economy", en=("Flights to Paphos airport resume", ["Paphos airport"]))
        self.assertEqual(build.travel_context(story), "airport")
        html = build.travel_box_html("en", "airport")
        hrefs = re.findall(r'href="(https?://[^"]+)"', html)
        self.assertEqual(hrefs[:3], [
            "https://tpx.lt/HeqeBOtK",
            "https://aviasales.tpx.lt/45iBpc4b",
            "https://airalo.tpx.lt/Z3nl2F1z",
        ])

    def test_beach_story_leads_with_tours_and_car_rental(self):
        hrefs = re.findall(r'href="(https?://[^"]+)"', build.travel_box_html("ru", "beach"))
        self.assertEqual(hrefs[:2], [
            "https://klook.tpx.lt/xtutlwca",
            "https://localrent.tpx.lt/XVEtrVFd",
        ])

    def test_irrelevant_pages_stay_clear_of_the_new_links(self):
        marker = "https://localrent.tpx.lt/XVEtrVFd"
        for slug in HIDE:
            for lang in LANGS:
                html = build.page_article(lang, build.BYSLUG[slug])
                self.assertNotIn('class="travelbox"', html, (slug, lang))
                self.assertNotIn(marker, html, (slug, lang))
        self.assertNotIn(marker, build.page_home("en"))
        self.assertNotIn(marker, build.page_cat("ru", "politics"))
        self.assertNotIn(marker, build.page_cat("en", "economy"))
        self.assertNotIn(marker, build.page_events("el"))
        travel = build.page_travel("en")
        self.assertIn('class="travelbox"', travel)
        self.assertIn(marker, travel)
        self.assertIn(DISCLOSURE["en"], travel.replace("</a>", ""))

    def test_existing_ads_social_and_guide_links_stay(self):
        html = build.page_article("en", build.BYSLUG["weekend-events-14-15-november"])
        self.assertIn("ca-pub-1547877294743851", html)
        self.assertIn("https://emrldtp.com/NjAzNzQw.js?t=603740", html)
        self.assertIn("https://t.me/cynews24en", html)
        self.assertIn("https://www.threads.com/@cynews24", html)
        self.assertNotIn("/assets/js/affiliates.js", html)
        car = build.page_article("en", build.BYSLUG["renting-a-car-in-cyprus"])
        self.assertIn("https://www.discovercars.com/", car)
        self.assertIn("https://kiwitaxi.tpx.lt/pmM77dyU", car)
        self.assertIn("https://tpx.lt/sJrz0dYS", car)
        esim = build.page_article("en", build.BYSLUG["esim-mobile-data-cyprus"])
        self.assertLess(esim.find("https://airalo.tpx.lt/nILAEUYZ"), esim.find("https://yesim.tpx.lt/L3JvkZOj"))
        self.assertIn("https://airalo.tpx.lt/Z3nl2F1z", esim)


if __name__ == "__main__":
    unittest.main()
