# -*- coding: utf-8 -*-
"""Unit tests for the Facebook poster. No network and no posts to the Page."""
from __future__ import annotations

import contextlib
import datetime
import html
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

import facebook_post as fb

HERE = os.path.dirname(os.path.abspath(__file__))
ARTICLES = os.path.join(HERE, "content", "articles")
STATE = os.path.join(HERE, "content", "facebook-posted.json")
ROOT = os.path.normpath(os.path.join(HERE, ".."))

# Articles that already existed when Facebook posting was added. New files are
# not listed, so publishing an article does not fail the build for lack of a
# state entry.
ORIGINAL = [
    "cape-greco-monastery-legalisation",
    "cyprus-video-game-industry",
    "diabetes-undiagnosed-cyprus",
    "driver-hours-campaign",
    "eu-ai-summit-dublin",
    "fintech-jobs-not-registrations",
    "fitto-cyprus-talks",
    "frozen-assets-51-million",
    "governors-beach-caravan-eviction",
    "homes-without-electricity-paphos",
    "kiayias-youth-olympic-fencing-bronze",
    "microsoft-outage-second-day",
    "missing-mushroom-picker-paphos-forest",
    "nicosia-christmas-market-2026",
    "pedestrian-crossing-camera-fine",
    "pension-reform-1-january",
    "planning-enforcement-audit",
    "property-sale-fines-100000",
]


def page(title: str, lang: str, slug: str, *, noindex: bool = False, og: bool = True) -> bytes:
    robots = "noindex,follow" if noindex else "index,follow,max-image-preview:large,max-snippet:-1"
    escaped = html.escape(title, quote=True)
    tags = ""
    if og:
        tags = (
            f'<meta property="og:title" content="{escaped}">'
            f'<meta property="og:description" content="Lead.">'
            f'<meta property="og:image" content="https://cynews24.net/assets/img/{slug}-og.jpg">'
        )
    return (
        f'<!doctype html><html lang="{lang}"><head><title>{escaped}</title>'
        f'<meta name="robots" content="{robots}">'
        f'<link rel="canonical" href="https://cynews24.net/{lang}/{slug}/">'
        f"{tags}</head><body><h1>{escaped}</h1></body></html>"
    ).encode("utf-8")


def jpeg() -> bytes:
    return b"\xff\xd8\xff" + b"x" * 120


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def article(
    slug="fresh-story",
    cat="politics",
    date="2026-11-13",
    en=True,
    ru_title="Заголовок",
    en_title="English title",
    en_lede="English lead. Second sentence. Third sentence.",
    image="photo-key",
):
    return fb.Article(
        slug=slug,
        cat=cat,
        date=datetime.date.fromisoformat(date),
        titles={"ru": ru_title, "en": en_title if en else "", "el": ""},
        ledes={"ru": "Русский лид", "en": en_lede if en else "", "el": ""},
        translated={"ru": True, "en": en, "el": False},
        image_key=image,
    )


class MessageTests(unittest.TestCase):
    def test_english_message_has_title_lead_and_hashtags(self):
        post = fb.build_post(article(), "en", "https://cynews24.net")
        self.assertEqual(post["link"], "https://cynews24.net/en/fresh-story/")
        self.assertNotIn("http", post["message"])
        self.assertIn("English title", post["message"])
        self.assertIn("English lead. Second sentence.", post["message"])
        self.assertNotIn("Third sentence.", post["message"])
        self.assertIn("#Politics #Cyprus #CyprusNews", post["message"])
        self.assertNotIn("#Кипр", post["message"])

    def test_language_switch_uses_that_url_and_hashtags(self):
        story = article()
        russian = fb.build_post(story, "ru", "https://cynews24.net")
        self.assertEqual(russian["link"], "https://cynews24.net/ru/fresh-story/")
        self.assertIn("Заголовок", russian["message"])
        self.assertIn("#Политика #Кипр #новостиКипра", russian["message"])
        greek = fb.Article(
            story.slug, "sport", story.date,
            {"ru": "Заголовок", "en": "English title", "el": "Ελληνικός τίτλος"},
            {"ru": "Лид", "en": "Lead.", "el": "Ελληνική εισαγωγή."},
            {"ru": True, "en": True, "el": True},
            story.image_key,
        )
        post = fb.build_post(greek, "el", "https://cynews24.net")
        self.assertEqual(post["link"], "https://cynews24.net/el/fresh-story/")
        self.assertIn("#Αθλητισμός #Κύπρος #ΕιδήσειςΚύπρου", post["message"])

    def test_every_category_hashtag(self):
        for cat in fb.CATS:
            for lang in fb.LANGS:
                tags = fb.hashtags(lang, cat)
                self.assertIn(fb.CAT_TAGS[lang][cat], tags)
                self.assertIn(fb.COUNTRY[lang], tags)
                self.assertIn(fb.NEWS[lang], tags)
                self.assertNotIn("-", fb.CAT_TAGS[lang][cat])

    def test_lead_keeps_two_sentences_and_a_single_one(self):
        self.assertEqual(fb.lead_summary("Only one."), "Only one.")
        self.assertEqual(fb.lead_summary("Really? Yes. No more."), "Really? Yes.")
        long = "word " * 400
        self.assertLessEqual(len(fb.lead_summary(long)), fb.LEAD_LIMIT)
        self.assertTrue(fb.lead_summary(long).endswith("…"))

    def test_open_graph_ready_requires_absolute_image(self):
        title = "Governor's Beach & <law>"
        self.assertTrue(fb.is_page_ready(page(title, "en", "governors-beach"), "en", "governors-beach", title))
        self.assertFalse(fb.is_page_ready(page(title, "en", "governors-beach", og=False), "en", "governors-beach", title))
        fallback = page("Русский заголовок", "en", "governors-beach", noindex=True)
        self.assertFalse(fb.is_page_ready(fallback, "en", "governors-beach", title))
        self.assertFalse(fb.is_image_ready(b"<html>no</html>"))
        self.assertTrue(fb.is_image_ready(jpeg()))
        image = fb.og_image_url(page(title, "en", "governors-beach"))
        self.assertEqual(image, "https://cynews24.net/assets/img/governors-beach-og.jpg")


class LoadTests(unittest.TestCase):
    def write(self, directory, name, payload):
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return path

    def test_slug_image_and_translation_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "from-title.json", {
                "cat": "society",
                "date": "2026-11-13T00:00:00.000Z",
                "image": "source/src/photo.jpg",
                "img": "ignored",
                "ru": {"title": "Новый закон", "lede": "Лид", "body": "Текст"},
                "en": {"title": "  ", "lede": "Lede", "body": "Body"},
            })
            self.write(tmp, "kept.json", {
                "slug": "kept-slug",
                "cat": "sport",
                "date": "2026-11-12",
                "img": "fencing-bronze",
                "ru": {"title": "Русский", "lede": "Лид", "body": "Текст"},
                "en": {"title": "English", "lede": "Lede", "body": "Body"},
                "el": {"title": "Ελληνικά", "lede": "Εισαγωγή", "body": "Κείμενο"},
            })
            articles = {item.slug: item for item in fb.load_articles(tmp)}
        self.assertEqual(articles["from-title"].image_key, "from-title")
        self.assertFalse(articles["from-title"].translated["en"])
        self.assertEqual(articles["kept-slug"].image_key, "fencing-bronze")
        self.assertTrue(articles["kept-slug"].translated["en"])
        self.assertTrue(articles["kept-slug"].translated["el"])

    def test_rejects_bad_article_and_duplicate_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "bad.json", {"cat": "nope", "date": "2026-11-13", "ru": {"title": "A", "lede": "B", "body": "C"}})
            with self.assertRaises(SystemExit):
                fb.load_article(path)
        with tempfile.TemporaryDirectory() as tmp:
            body = {"slug": "same", "cat": "society", "date": "2026-11-13", "ru": {"title": "A", "lede": "B", "body": "C"}}
            self.write(tmp, "a.json", body)
            self.write(tmp, "b.json", body)
            with self.assertRaises(SystemExit):
                fb.load_articles(tmp)

    def test_lang_must_be_known(self):
        with self.assertRaises(SystemExit):
            fb.require_lang("de")
        self.assertEqual(fb.require_lang(""), "en")
        self.assertEqual(fb.require_lang("EN"), "en")


class PlanTests(unittest.TestCase):
    def test_posts_fresh_english_and_waits_without_a_translation(self):
        actions = fb.plan([article(en=False)], fb.empty_state(), datetime.date(2026, 11, 13), "en")
        self.assertEqual([(item.kind, item.lang) for item in actions], [("untranslated", "en")])
        ready = fb.plan([article()], fb.empty_state(), datetime.date(2026, 11, 13), "en")
        self.assertEqual([(item.kind, item.lang) for item in ready], [("send", "en")])

    def test_edit_does_not_repost(self):
        story = article()
        state = fb.empty_state()
        fb.mark(state, story.slug, "sent", fb.utcnow(), "en")
        changed = fb.Article(
            story.slug, story.cat, story.date,
            {"ru": story.titles["ru"], "en": "Other title", "el": ""},
            story.ledes, story.translated, story.image_key,
        )
        self.assertEqual(fb.plan([changed], state, story.date, "en"), [])
        self.assertEqual(fb.plan([changed], state, story.date, "ru"), [])

    def test_age_boundary(self):
        today = datetime.date(2026, 11, 13)
        fresh = article(slug="three-days", date="2026-11-10")
        old = article(slug="four-days", date="2026-11-09")
        actions = {(item.article.slug, item.lang): item.kind for item in fb.plan([fresh, old], fb.empty_state(), today, "en")}
        self.assertEqual(actions[("three-days", "en")], "send")
        self.assertEqual(actions[("four-days", "en")], "stale")

    def test_cap_defers_without_dropping_other_actions(self):
        stories = [article(slug=f"s{i:02d}") for i in range(12)]
        stories.append(article(slug="old", date="2026-11-01"))
        stories.append(article(slug="pending", en=False))
        actions = fb.apply_cap(fb.plan(stories, fb.empty_state(), datetime.date(2026, 11, 13), "en"), 10)
        kinds = [item.kind for item in actions]
        self.assertEqual(kinds.count("send"), 10)
        self.assertEqual(kinds.count("deferred"), 2)
        self.assertIn("stale", kinds)
        self.assertIn("untranslated", kinds)
        self.assertEqual([item.article.slug for item in actions if item.kind == "deferred"], ["s10", "s11"])


class ExecuteTests(unittest.TestCase):
    def run_execute(self, articles, state, *, today="2026-11-13", lang="en", token="token",
                    page_id="8690", dry_run=False, http_get=None, send=None, probe=None,
                    max_wait=360, max_posts=10, delay=0, clock=None):
        logs = []
        saves = []
        clock = clock or Clock()
        if http_get is None:
            def http_get(url):
                if "/assets/img/" in url:
                    return 200, jpeg()
                parts = url.rstrip("/").split("/")
                slug, language = parts[-1], parts[-2]
                match = next(item for item in articles if item.slug == slug)
                return 200, page(match.titles[language], language, slug)
        if send is None:
            def send(payload):
                return True, "10"
        if probe is None:
            def probe():
                return True, "CyNews24"
        code = fb.execute(
            articles, state,
            today=datetime.date.fromisoformat(today),
            now=datetime.datetime(2026, 11, 13, 12, 0, tzinfo=datetime.timezone.utc),
            lang=lang, token=token, page_id=page_id, dry_run=dry_run,
            base="https://cynews24.net", max_posts=max_posts, delay=delay, max_wait=max_wait,
            http_get=http_get, sleep=clock.sleep, monotonic=clock.monotonic,
            send=send, probe=probe, log=logs.append,
            save=lambda: saves.append(json.loads(fb.serialize(state))),
        )
        return logs, saves, code

    def test_posts_english_link_once(self):
        sent = []
        story = article()
        state = fb.empty_state()
        logs, saves, code = self.run_execute([story], state, send=lambda payload: sent.append(payload) or (True, "7"))
        self.assertEqual(code, 0)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["link"], "https://cynews24.net/en/fresh-story/")
        self.assertIn("English title", sent[0]["message"])
        self.assertIn("#Cyprus #CyprusNews", sent[0]["message"])
        self.assertNotIn("/ru/", sent[0]["link"])
        self.assertEqual(state["posted"]["fresh-story"]["status"], "sent")
        self.assertEqual(state["posted"]["fresh-story"]["lang"], "en")
        self.assertGreaterEqual(len(saves), 1)
        self.assertTrue(any("Facebook page name: CyNews24" in line for line in logs))
        again = []
        edited = article(en_title="Changed title", en_lede="New lead.")
        self.run_execute([edited], state, send=lambda payload: again.append(payload) or (True, "8"))
        self.assertEqual(again, [])

    def test_missing_english_is_not_marked_and_posts_later(self):
        sent = []
        story = article(en=False)
        state = fb.empty_state()
        self.run_execute([story], state, send=lambda payload: sent.append(payload) or (True, "1"))
        self.assertEqual(sent, [])
        self.assertNotIn(story.slug, state["posted"])
        translated = article(en_title="Now in English", en_lede="The English lead.")
        self.run_execute([translated], state, send=lambda payload: sent.append(payload) or (True, "2"))
        self.assertEqual(sent[-1]["link"], "https://cynews24.net/en/fresh-story/")
        self.assertIn("Now in English", sent[-1]["message"])
        self.assertEqual(state["posted"][story.slug]["status"], "sent")

    def test_old_articles_are_marked_without_posting(self):
        sent = []
        old = article(slug="old", date="2026-11-01")
        state = fb.empty_state()
        logs, _saves, code = self.run_execute([old], state, send=lambda payload: sent.append(payload) or (True, "1"))
        self.assertEqual(code, 0)
        self.assertEqual(sent, [])
        self.assertEqual(state["posted"]["old"]["status"], "skipped-old")
        self.assertEqual(state["posted"]["old"]["lang"], "en")
        self.assertTrue(any("without sending" in line for line in logs))

    def test_missing_token_does_not_advance_state_or_send(self):
        sent = []
        story = article(date="2026-11-01")
        state = fb.empty_state()
        before = fb.serialize(state)
        logs, saves, code = self.run_execute(
            [story], state, token="", send=lambda payload: sent.append(payload) or (True, "1"),
        )
        self.assertEqual(code, 0)
        self.assertEqual(sent, [])
        self.assertEqual(saves, [])
        self.assertEqual(fb.serialize(state), before)
        self.assertTrue(any("FB_PAGE_TOKEN" in line and "not set" in line for line in logs))
        self.assertTrue(any(line.startswith("::notice") for line in logs))

    def test_missing_page_id_does_not_advance_state(self):
        story = article()
        state = fb.empty_state()
        before = fb.serialize(state)
        logs, saves, code = self.run_execute([story], state, page_id="")
        self.assertEqual(code, 0)
        self.assertEqual(saves, [])
        self.assertEqual(fb.serialize(state), before)
        self.assertTrue(any("FB_PAGE_ID" in line and "not set" in line for line in logs))

    def test_dry_run_checks_the_page_and_does_not_send_or_write(self):
        sent = []
        story = article()
        pending = article(slug="later", en=False)
        old = article(slug="old", date="2026-11-01")
        state = fb.empty_state()
        before = fb.serialize(state)
        logs, saves, code = self.run_execute(
            [story, pending, old], state, token="secret-token", page_id="111", dry_run=True,
            send=lambda payload: sent.append(payload) or (True, "1"),
            probe=lambda: (True, "CyNews24"),
        )
        self.assertEqual(code, 0)
        self.assertEqual(sent, [])
        self.assertEqual(saves, [])
        self.assertEqual(fb.serialize(state), before)
        text = "\n".join(logs)
        self.assertIn("DRY RUN slug=fresh-story link=https://cynews24.net/en/fresh-story/", text)
        self.assertIn("English title", text)
        self.assertIn("#Cyprus #CyprusNews", text)
        self.assertIn("no en translation yet", text)
        self.assertIn("would mark posted without sending", text)
        self.assertIn("Nothing was published", text)
        self.assertIn("FB_PAGE_TOKEN is configured (value not printed).", text)
        self.assertIn("Facebook page name: CyNews24", text)
        self.assertNotIn("secret-token", text)
        self.assertNotIn("111", text)

    def test_dry_run_fails_when_the_page_cannot_be_read(self):
        story = article()
        state = fb.empty_state()
        logs, saves, code = self.run_execute(
            [story], state, token="secret-token", page_id="111", dry_run=True,
            probe=lambda: (False, "Invalid OAuth access token secret-token"),
        )
        self.assertEqual(code, 1)
        self.assertEqual(saves, [])
        text = "\n".join(logs)
        self.assertIn("Invalid OAuth", text)
        self.assertNotIn("secret-token", text)
        self.assertIn("Nothing was published", text)

    def test_cap_leaves_the_rest_unmarked(self):
        sent = []
        stories = [article(slug=f"s{i}") for i in range(3)]
        state = fb.empty_state()
        logs, _saves, code = self.run_execute(
            stories, state, max_posts=2, delay=5,
            send=lambda payload: sent.append(payload) or (True, "1"),
        )
        self.assertEqual(code, 0)
        self.assertEqual([item["link"].rstrip("/").rsplit("/", 1)[-1] for item in sent], ["s0", "s1"])
        self.assertNotIn("s2", state["posted"])
        self.assertEqual(state["posted"]["s0"]["status"], "sent")
        self.assertTrue(any("post cap of 2" in line for line in logs))
        self.assertTrue(any(line == "pause 5s" for line in logs))

    def test_graph_error_does_not_mark_that_item_and_keeps_the_others(self):
        stories = [article(slug="ok"), article(slug="bad"), article(slug="later")]
        state = fb.empty_state()

        def send(payload):
            if payload["link"].endswith("/bad/"):
                return False, "Invalid parameter secret-token"
            return True, "9"

        logs, saves, code = self.run_execute(stories, state, token="secret-token", send=send)
        self.assertEqual(code, 1)
        self.assertEqual(state["posted"]["ok"]["status"], "sent")
        self.assertNotIn("bad", state["posted"])
        self.assertEqual(state["posted"]["later"]["status"], "sent")
        self.assertGreaterEqual(len(saves), 2)
        text = "\n".join(logs)
        self.assertIn("Invalid parameter", text)
        self.assertNotIn("secret-token", text)
        self.assertIn("bad", text)

    def test_live_failure_does_not_mark(self):
        story = article()
        state = fb.empty_state()
        logs, _saves, code = self.run_execute(
            [story], state, max_wait=0, http_get=lambda url: (404, b"no"),
        )
        self.assertEqual(code, 1)
        self.assertNotIn(story.slug, state["posted"])
        self.assertTrue(any("not live" in line for line in logs))

    def test_unreachable_page_does_not_post(self):
        sent = []
        story = article()
        state = fb.empty_state()
        logs, saves, code = self.run_execute(
            [story], state, token="secret-token", page_id="111",
            probe=lambda: (False, "Error validating access token secret-token"),
            send=lambda payload: sent.append(payload) or (True, "1"),
        )
        self.assertEqual(code, 1)
        self.assertEqual(sent, [])
        self.assertEqual(saves, [])
        self.assertNotIn("secret-token", "\n".join(logs))

    def test_retries_until_the_page_and_image_are_live(self):
        story = article()
        clock = Clock()

        def http_get(url):
            if clock.now < 20:
                return 404, b"missing"
            if url.endswith(".jpg"):
                return 200, jpeg()
            return 200, page(story.titles["en"], "en", story.slug)

        sent = []
        state = fb.empty_state()
        _logs, _saves, code = self.run_execute(
            [story], state, clock=clock, http_get=http_get,
            send=lambda payload: sent.append(payload) or (True, "3"),
        )
        self.assertEqual(code, 0)
        self.assertGreater(clock.now, 0)
        self.assertEqual(len(sent), 1)
        self.assertEqual(state["posted"][story.slug]["status"], "sent")

    def test_api_retries_rate_limit_and_redacts_the_token_and_page(self):
        calls = []

        def post(url, data):
            calls.append((url, data))
            self.assertNotIn("token-secret", url)
            body = urllib_parse(data)
            self.assertEqual(body["link"], "https://cynews24.net/en/x/")
            self.assertEqual(body["message"], "Hello")
            self.assertEqual(body["access_token"], "token-secret")
            if len(calls) == 1:
                return 429, json.dumps({
                    "error": {
                        "message": "Application request limit reached token-secret",
                        "type": "OAuthException",
                        "code": 4,
                        "fbtrace_id": "trace",
                        "is_transient": True,
                    },
                }).encode()
            return 200, json.dumps({"id": "page-999_42"}).encode()

        slept = []
        ok, info = fb.send_facebook(
            "token-secret", "page-999",
            {"message": "Hello", "link": "https://cynews24.net/en/x/"},
            post=post, sleep=slept.append,
        )
        self.assertTrue(ok)
        self.assertEqual(info, "42")
        self.assertEqual(slept, [2])
        self.assertNotIn("page-999", info)

        def bad_request(url, data):
            return 400, json.dumps({
                "error": {"message": "(#200) permission token-secret page-999", "code": 200},
            }).encode()

        ok, info = fb.send_facebook(
            "token-secret", "page-999",
            {"message": "Hello", "link": "https://cynews24.net/en/x/"},
            post=bad_request, sleep=slept.append,
        )
        self.assertFalse(ok)
        self.assertNotIn("token-secret", info)
        self.assertNotIn("page-999", info)
        self.assertIn("permission", info)
        self.assertIn("code=200", info)

    def test_page_probe_reads_the_name_and_hides_secrets(self):
        token = "token-secret"
        page_id = "869006633124235"

        def get(url):
            self.assertNotIn(token, url.split("access_token=", 1)[0])
            self.assertIn("fields=name", url)
            return 200, json.dumps({"name": "CyNews24", "id": page_id}).encode()

        ok, name = fb.probe_page(page_id, token, get)
        self.assertTrue(ok)
        self.assertEqual(name, "CyNews24")
        self.assertTrue(fb.page_name_ok("CyNews 24"))
        self.assertFalse(fb.page_name_ok("Other Page"))

        def fail(url):
            return 400, json.dumps({
                "error": {"message": f"bad {token}", "code": 190, "type": "OAuthException"},
            }).encode()

        ok, info = fb.probe_page(page_id, token, fail)
        self.assertFalse(ok)
        self.assertNotIn(token, info)
        self.assertNotIn(page_id, info)
        self.assertIn("code=190", info)

    def test_cli_missing_token_keeps_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            articles_dir = os.path.join(tmp, "articles")
            os.makedirs(articles_dir)
            with open(os.path.join(articles_dir, "story.json"), "w", encoding="utf-8") as handle:
                json.dump({
                    "slug": "cli-story", "cat": "economy", "date": "2026-11-13",
                    "ru": {"title": "Новость", "lede": "Лид", "body": "Текст"},
                    "en": {"title": "News", "lede": "Lead.", "body": "Body"},
                }, handle)
            state_path = os.path.join(tmp, "facebook-posted.json")
            with open(state_path, "w", encoding="utf-8") as handle:
                handle.write(fb.serialize(fb.empty_state()))
            with open(state_path, encoding="utf-8") as handle:
                before = handle.read()
            env = os.environ.copy()
            env.pop("FB_PAGE_TOKEN", None)
            env.pop("FB_PAGE_ID", None)
            env.pop("DRY_RUN", None)
            env.pop("PUSH_STATE", None)
            env.pop("FB_POST_LANG", None)
            with mock.patch.dict(os.environ, env, clear=True):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = fb.main([
                        "--articles", articles_dir, "--state", state_path,
                        "--today", "2026-11-13", "--lang", "en",
                    ])
            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn("FB_PAGE_TOKEN", text)
            self.assertIn("FB_POST_LANG=en", text)
            with open(state_path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), before)


def urllib_parse(data: bytes) -> dict:
    import urllib.parse
    return dict(urllib.parse.parse_qsl(data.decode("utf-8")))


class SeedAndWorkflowTests(unittest.TestCase):
    def test_original_articles_are_seeded_and_match_the_loader(self):
        self.assertTrue(os.path.exists(STATE))
        with open(STATE, encoding="utf-8") as handle:
            raw = handle.read()
        state = fb.load_state(STATE)
        self.assertEqual(raw, fb.serialize(state))
        found = []
        for name in ORIGINAL:
            path = os.path.join(ARTICLES, name + ".json")
            self.assertTrue(os.path.exists(path), name)
            found.append(fb.load_article(path))
        self.assertEqual(len(found), len(ORIGINAL))
        expected = fb.initial_seed(found, "en")
        for slug, entry in expected["posted"].items():
            self.assertEqual(state["posted"].get(slug), entry)
            self.assertEqual(entry["status"], "seeded")
            self.assertEqual(entry["lang"], "en")
        articles = fb.load_articles(ARTICLES)
        # The seed covers the original catalogue. Stories added afterwards do
        # not need a state entry: while they are fresh the plan sends them, and
        # once they are older than three days it marks them stale.
        fresh = fb.plan(articles, state, datetime.date(2026, 11, 13), "en")
        for action in fresh:
            self.assertNotIn(action.article.slug, ORIGINAL)
            self.assertEqual(action.kind, "send")
        later = fb.plan(articles, state, datetime.date(2030, 1, 1), "en")
        for action in later:
            self.assertNotIn(action.article.slug, ORIGINAL)
            self.assertEqual(action.kind, "stale")

    def test_built_english_articles_have_open_graph_tags(self):
        build_py = os.path.join(HERE, "build.py")
        with open(build_py, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn('property="og:title"', source)
        self.assertIn('property="og:description"', source)
        self.assertIn('property="og:image"', source)
        self.assertIn('content="1200"', source)
        self.assertIn('content="630"', source)
        for slug in ORIGINAL:
            path = os.path.join(ROOT, "en", slug, "index.html")
            self.assertTrue(os.path.exists(path), slug)
            with open(path, "rb") as handle:
                body = handle.read()
            self.assertIn(b'property="og:title"', body)
            self.assertIn(b'property="og:description"', body)
            self.assertIn(b'property="og:image" content="https://cynews24.net/assets/img/', body)
            self.assertIn(b"-og.jpg", body)
            article = fb.load_article(os.path.join(ARTICLES, slug + ".json"))
            self.assertTrue(article.translated["en"], slug)
            self.assertTrue(fb.is_page_ready(body, "en", slug, article.titles["en"]), slug)
            image = fb.og_image_url(body)
            self.assertTrue(image.startswith("https://cynews24.net/assets/img/"), image)
            self.assertTrue(image.endswith("-og.jpg"), image)

    def test_workflows_keep_pages_and_avoid_a_posting_loop(self):
        with open(os.path.join(ROOT, ".github", "workflows", "build.yml"), encoding="utf-8") as handle:
            build = handle.read()
        with open(os.path.join(ROOT, ".github", "workflows", "facebook.yml"), encoding="utf-8") as handle:
            poster = handle.read()
        self.assertEqual(build.count("!source/content/facebook-posted.json"), 2)
        self.assertEqual(build.count("!source/content/telegram-posted.json"), 2)
        self.assertIn('name: Post to Facebook', poster)
        self.assertIn('workflows: ["Build site"]', poster)
        self.assertIn("branches: [main]", poster)
        self.assertIn("FB_PAGE_TOKEN", poster)
        self.assertIn("FB_PAGE_ID", poster)
        self.assertIn("FB_POST_LANG: en", poster)
        self.assertIn("value not printed", poster)
        self.assertNotIn('echo "$FB_PAGE_TOKEN"', poster)
        self.assertNotIn("echo $FB_PAGE_TOKEN", poster)
        self.assertNotIn('echo "$FB_PAGE_ID"', poster)
        self.assertNotIn("echo $FB_PAGE_ID", poster)
        self.assertNotIn("869006633124235", poster)
        self.assertIn("dry_run", poster)
        self.assertIn("cancel-in-progress: false", poster)
        self.assertIn("PUSH_STATE", poster)
        self.assertNotIn("graph.facebook.com", poster)
        self.assertNotIn("/feed", poster)
        with open(os.path.join(HERE, "facebook_post.py"), encoding="utf-8") as handle:
            script = handle.read()
        self.assertIn("https://graph.facebook.com/v21.0", script)
        self.assertIn("/feed", script)
        self.assertNotIn("869006633124235", script)

    def test_commit_and_push_only_the_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bare = os.path.join(tmp, "bare.git")
            work = os.path.join(tmp, "work")
            subprocess.check_call(["git", "init", "--bare", "-b", "main", bare], stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "init", "-b", "main", work], stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "-C", work, "config", "user.email", "test@example.com"])
            subprocess.check_call(["git", "-C", work, "config", "user.name", "Test"])
            subprocess.check_call(["git", "-C", work, "config", "commit.gpgsign", "false"])
            with open(os.path.join(work, "README"), "w", encoding="utf-8") as handle:
                handle.write("site\n")
            subprocess.check_call(["git", "-C", work, "add", "README"])
            subprocess.check_call(["git", "-C", work, "commit", "-q", "-m", "init"])
            subprocess.check_call(["git", "-C", work, "remote", "add", "origin", bare])
            subprocess.check_call(["git", "-C", work, "push", "-q", "origin", "HEAD:main"])
            state = os.path.join(work, "source", "content", "facebook-posted.json")
            os.makedirs(os.path.dirname(state))
            with open(state, "w", encoding="utf-8") as handle:
                handle.write(fb.serialize(fb.empty_state()))
            with open(os.path.join(work, "README"), "a", encoding="utf-8") as handle:
                handle.write("dirty but must not be committed\n")
            with contextlib.redirect_stdout(io.StringIO()):
                fb.commit_and_push(work, state)
            shown = subprocess.check_output(
                ["git", "-C", work, "show", "--name-only", "--pretty=format:%s", "HEAD"], text=True,
            )
            self.assertIn(fb.COMMIT_MESSAGE, shown)
            self.assertIn("source/content/facebook-posted.json", shown)
            self.assertNotIn("README", shown.splitlines()[-1])
            clone = os.path.join(tmp, "clone")
            subprocess.check_call(["git", "clone", "-q", bare, clone])
            self.assertTrue(os.path.exists(os.path.join(clone, "source", "content", "facebook-posted.json")))
            with open(os.path.join(clone, "README"), encoding="utf-8") as handle:
                readme = handle.read()
            self.assertNotIn("dirty", readme)


if __name__ == "__main__":
    unittest.main()
