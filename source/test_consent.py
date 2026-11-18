# -*- coding: utf-8 -*-
"""Consent, Bing, analytics placeholder, feeds and the Instagram footer. No network."""
from __future__ import annotations

import unittest
from unittest import mock

import build

KEY = "c9b38f2f2d7a4e59bfc566f01e259c2e"
NOT_GA = {
    "en": "does not use Google Analytics",
    "ru": "не использует Google Analytics",
    "el": "δεν χρησιμοποιεί Google Analytics",
}


class ConsentTests(unittest.TestCase):
    def tearDown(self):
        build.GA4_ID = ""
        build.BING_VERIFICATION = ""
        build._GA_WARNED = False

    def test_consent_default_is_before_adsense(self):
        html = build.google_tags()
        self.assertLess(html.find("gtag('consent','default'"), html.find("adsbygoogle.js"))
        self.assertNotIn("googletagmanager.com", html)
        for signal in ("ad_storage", "ad_user_data", "ad_personalization", "analytics_storage"):
            self.assertIn(f"'{signal}':'denied'", html)

    def test_ga4_tag_respects_consent_order(self):
        build.GA4_ID = "G-TEST12345"
        html = build.google_tags()
        default = html.find("gtag('consent','default'")
        tag = html.find("googletagmanager.com/gtag/js?id=G-TEST12345")
        ads = html.find("adsbygoogle.js")
        self.assertTrue(0 <= default < tag < ads)
        self.assertIn('gtag("config","G-TEST12345")', html)

    def test_invalid_measurement_id_is_not_loaded(self):
        build.GA4_ID = "UA-123"
        self.assertEqual(build.ga4_snippet(), "")
        self.assertNotIn("googletagmanager.com", build.google_tags())

    def test_bing_meta_is_omitted_until_configured(self):
        self.assertEqual(build.bing_meta(), "")
        html = build.head("en", "T", "D", ["k"], "/en/", lambda x: f"/{x}/", "/assets/og-default.jpg")
        self.assertNotIn("msvalidate.01", html)
        self.assertLess(html.find("adsbygoogle.js"), html.find("</head>"))
        self.assertLess(html.find("gtag('consent','default'"), html.find("adsbygoogle.js"))

    def test_bing_meta_uses_the_configured_value(self):
        build.BING_VERIFICATION = 'AB"CD'
        self.assertEqual(build.bing_meta(), '<meta name="msvalidate.01" content="AB&quot;CD" />')

    def test_root_and_404_load_consent_before_ads(self):
        for html in (build.page_root(), build.page_404()):
            self.assertLess(html.find("gtag('consent','default'"), html.find("adsbygoogle.js"))
            self.assertIn('id="cookie-banner"', html)
            self.assertIn("Accept", html)
            self.assertIn("Reject", html)
        self.assertIn('href="/feed.xml"', build.page_root())

    def test_banner_languages_and_consent_update(self):
        self.assertIn("Принять", build.cookie_banner("ru"))
        self.assertIn("Отклонить", build.cookie_banner("ru"))
        self.assertIn("Αποδοχή", build.cookie_banner("el"))
        self.assertIn("Απόρριψη", build.cookie_banner("el"))
        js = build.COOKIE_BANNER_JS
        self.assertIn('gtag("consent","update"', js)
        self.assertIn('"granted"', js)
        self.assertIn('"denied"', js)
        self.assertIn("cynews24-consent", js)
        self.assertIn("data-cookie-settings", js)

    def test_privacy_mentions_analytics_only_when_enabled(self):
        for lang, phrase in NOT_GA.items():
            privacy = _flat(build.privacy_for(lang))
            cookies = _flat(build.cookies_for(lang))
            self.assertIn(phrase, privacy)
            self.assertIn(phrase, cookies)
            self.assertIn("cynews24-consent", privacy)
            self.assertIn("cynews24-consent", cookies)
        build.GA4_ID = "G-LIVE123"
        for lang, phrase in NOT_GA.items():
            privacy = _flat(build.privacy_for(lang))
            cookies = _flat(build.cookies_for(lang))
            self.assertNotIn(phrase, privacy)
            self.assertNotIn(phrase, cookies)
            self.assertIn("G-LIVE123", privacy)
            self.assertIn("G-LIVE123", cookies)
            self.assertIn("cynews24-consent", privacy)

    def test_footer_has_instagram_beside_telegram_and_cookie_settings(self):
        with mock.patch.object(build, "mycytax_catalog", return_value=object()), \
             mock.patch.object(build.mycytax, "projects_html", return_value=""):
            html = build.footer("ru")
        self.assertLess(html.find("https://t.me/cynews24"), html.find("https://www.instagram.com/cynews24/"))
        self.assertIn("data-cookie-settings", html)
        self.assertIn("Настройки cookie", html)
        self.assertIn('href="/ru/cookies/"', html)
        self.assertNotIn("facebook.com", html)
        self.assertIn("https://www.instagram.com/cynews24/", build.footer_social("en"))
        self.assertIn("https://www.instagram.com/cynews24/", build.footer_social("el"))
        self.assertNotIn("youtube.com", html)
        self.assertNotIn("youtube.com", build.header("en", lambda x: f"/{x}/"))
        self.assertNotIn("youtube.com", " ".join(build.same_as()))

    def test_homepage_recommends_the_peachick_club(self):
        with mock.patch.object(build, "mycytax_catalog", return_value=object()), \
             mock.patch.object(build.mycytax, "projects_html", return_value=""):
            en = build.page_home("en")
            ru = build.page_home("ru")
            el = build.page_home("el")
        link='href="https://www.youtube.com/@thepeachickclub" target="_blank" rel="noopener"'
        self.assertIn("Editor&#x27;s pick: cartoons for kids, made in Cyprus", en)
        self.assertIn("Real peachicks from Cyprus", en)
        self.assertIn(link, en)
        self.assertIn("От редакции: мультики для детей, снятые на Кипре", ru)
        self.assertIn("Смотреть на YouTube", ru)
        self.assertIn(link, ru)
        self.assertIn("Επιλογή σύνταξης: κινούμενα για παιδιά, γυρισμένα στην Κύπρο", el)
        self.assertIn("Δείτε στο YouTube", el)
        self.assertIn(link, el)
        self.assertFalse(any("youtube.com" in url for url in build.same_as()))

    def test_sitemap_lists_cookie_policy_and_the_key_is_32_hex(self):
        sm = build.sitemap()
        for lang in ("ru", "en", "el"):
            self.assertIn(f"https://cynews24.net/{lang}/cookies/", sm)
        self.assertEqual(build.indexnow_key(), KEY)
        self.assertEqual(len(KEY), 32)


def _flat(page):
    return " ".join(p for _title, paras in page["sections"] for p in paras)
