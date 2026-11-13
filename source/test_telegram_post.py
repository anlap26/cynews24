# -*- coding: utf-8 -*-
"""Unit tests for the Telegram poster. No network and no messages to the channels."""
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

import telegram_post as tg

HERE = os.path.dirname(os.path.abspath(__file__))
ARTICLES = os.path.join(HERE, "content", "articles")
STATE = os.path.join(HERE, "content", "telegram-posted.json")
ROOT = os.path.normpath(os.path.join(HERE, ".."))

# Articles that already existed when posting was added. New files are not listed,
# so publishing an article does not fail the build for lack of a state entry.
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


def page(title: str, lang: str, slug: str, *, noindex: bool = False) -> bytes:
    robots = "noindex,follow" if noindex else "index,follow,max-image-preview:large,max-snippet:-1"
    escaped = html.escape(title, quote=True)
    return (
        f'<!doctype html><html lang="{lang}"><head><title>{escaped}</title>'
        f'<meta name="robots" content="{robots}">'
        f'<link rel="canonical" href="https://cynews24.net/{lang}/{slug}/">'
        f"</head><body><h1>{escaped}</h1></body></html>"
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
    ru_title="Заголовок",
    ru_lede="Короткий лид",
    en=True,
    image="photo-key",
):
    titles = {"ru": ru_title, "en": "English title" if en else ""}
    ledes = {"ru": ru_lede, "en": "English lede" if en else ""}
    return tg.Article(
        slug=slug,
        cat=cat,
        date=datetime.date.fromisoformat(date),
        titles=titles,
        ledes=ledes,
        translated={"ru": True, "en": en},
        image_key=image,
    )


class CaptionTests(unittest.TestCase):
    def test_live_page_matches_escaped_title_and_rejects_fallback(self):
        title = "Governor's Beach & <law>"
        self.assertTrue(tg.is_page_ready(page(title, "en", "governors-beach"), "en", "governors-beach", title))
        fallback = page("Русский заголовок", "en", "governors-beach", noindex=True)
        self.assertFalse(tg.is_page_ready(fallback, "en", "governors-beach", title))
        self.assertFalse(tg.is_page_ready(b"missing", "en", "governors-beach", title))
        self.assertFalse(tg.is_image_ready(b"<html>no</html>"))
        self.assertTrue(tg.is_image_ready(jpeg()))

    def test_html_escape_and_structure(self):
        caption = tg.render_caption(
            'Том & Джерри <закон>',
            'Лид с "кавычками" и <тегом>',
            "https://cynews24.net/ru/slug/",
            "Читать полностью",
            "#Политика #Кипр",
        )
        self.assertIn("<b>Том &amp; Джерри &lt;закон&gt;</b>", caption)
        self.assertIn("Лид с &quot;кавычками&quot; и &lt;тегом&gt;".replace("&quot;", '"'), caption)
        self.assertIn('Лид с "кавычками" и &lt;тегом&gt;', caption)
        self.assertIn('<a href="https://cynews24.net/ru/slug/">Читать полностью</a>', caption)
        self.assertIn("#Политика #Кипр", caption)
        self.assertNotIn("<закон>", caption)
        self.assertNotIn("<тегом>", caption)
        self.assertLessEqual(tg.visible_length(caption), tg.CAPTION_LIMIT)

    def test_long_lede_and_title_stay_within_limit(self):
        caption = tg.render_caption(
            "Заголовок & <тест> " * 80,
            "слово " * 2000,
            "https://cynews24.net/en/very-long-slug-name/",
            "Read more",
            "#RealEstate #Cyprus",
        )
        self.assertLessEqual(tg.visible_length(caption), 1024)
        self.assertIn("Read more", caption)
        self.assertIn("#RealEstate #Cyprus", caption)
        self.assertIn("&amp;", caption)
        self.assertIn("&lt;тест&gt;", caption)
        self.assertNotIn("<тест>", caption)

    def test_every_category_hashtag(self):
        for cat in tg.CATS:
            for lang, link in (("ru", "Читать полностью"), ("en", "Read more")):
                caption = tg.render_caption("Title", "Lede", "https://cynews24.net/ru/s/", link, tg.hashtags(lang, cat))
                self.assertIn(tg.HASHTAGS[lang][cat], caption)
                self.assertIn(tg.COUNTRY[lang], caption)
                self.assertNotIn("-", tg.HASHTAGS[lang][cat])


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
            self.write(tmp, "with-img.json", {
                "slug": "kept-slug",
                "cat": "sport",
                "date": "2026-11-12",
                "img": "fencing-bronze",
                "ru": {"title": "Русский", "lede": "Лид", "body": ["Абзац"]},
                "en": {"title": "English", "lede": "Lede", "body": "Body"},
            })
            self.write(tmp, "no-photo.json", {
                "slug": "plain",
                "cat": "world",
                "date": "2026-11-11",
                "ru": {"title": "Без фото", "lede": "Лид", "body": "Текст"},
            })
            articles = {item.slug: item for item in tg.load_articles(tmp)}
        self.assertEqual(tg.slugify("Новый закон"), "novyj-zakon")
        self.assertEqual(articles["from-title"].image_key, "from-title")
        self.assertFalse(articles["from-title"].translated["en"])
        self.assertEqual(articles["kept-slug"].image_key, "fencing-bronze")
        self.assertTrue(articles["kept-slug"].translated["en"])
        self.assertIsNone(articles["plain"].image_key)
        self.assertEqual(articles["from-title"].date, datetime.date(2026, 11, 13))

    def test_rejects_bad_article_and_duplicate_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "bad.json", {"cat": "nope", "date": "2026-11-13", "ru": {"title": "A", "lede": "B", "body": "C"}})
            with self.assertRaises(SystemExit):
                tg.load_article(path)
        with tempfile.TemporaryDirectory() as tmp:
            body = {"slug": "same", "cat": "society", "date": "2026-11-13", "ru": {"title": "A", "lede": "B", "body": "C"}}
            self.write(tmp, "a.json", body)
            self.write(tmp, "b.json", body)
            with self.assertRaises(SystemExit):
                tg.load_articles(tmp)


class PlanTests(unittest.TestCase):
    def test_posts_fresh_russian_and_waits_for_english(self):
        state = tg.empty_state()
        actions = tg.plan([article(en=False)], state, datetime.date(2026, 11, 13))
        self.assertEqual([(item.kind, item.lang) for item in actions], [("send", "ru"), ("untranslated", "en")])

    def test_edit_does_not_repost(self):
        story = article()
        state = tg.empty_state()
        tg.mark(state, story.slug, "ru", "sent", tg.utcnow())
        tg.mark(state, story.slug, "en", "sent", tg.utcnow())
        changed = tg.Article(
            story.slug, story.cat, story.date,
            {"ru": "Другой заголовок", "en": "Other title"},
            story.ledes, story.translated, story.image_key,
        )
        self.assertEqual(tg.plan([changed], state, story.date), [])

    def test_age_boundary_and_late_english(self):
        today = datetime.date(2026, 11, 13)
        fresh = article(slug="three-days", date="2026-11-10", en=False)
        old = article(slug="four-days", date="2026-11-09", en=True, image=None)
        actions = {(item.article.slug, item.lang): item.kind for item in tg.plan([fresh, old], tg.empty_state(), today)}
        self.assertEqual(actions[("three-days", "ru")], "send")
        self.assertEqual(actions[("three-days", "en")], "untranslated")
        self.assertEqual(actions[("four-days", "ru")], "stale")
        self.assertEqual(actions[("four-days", "en")], "stale")

    def test_english_added_later_uses_the_same_age_rule(self):
        story = article(slug="later", date="2026-11-01", en=False)
        state = tg.empty_state()
        tg.mark(state, story.slug, "ru", "sent", tg.utcnow())
        waiting = tg.plan([story], state, datetime.date(2026, 11, 2))
        self.assertEqual([(item.kind, item.lang) for item in waiting], [("untranslated", "en")])
        translated = tg.Article(
            story.slug, story.cat, story.date,
            {"ru": story.titles["ru"], "en": "Now in English"},
            {"ru": story.ledes["ru"], "en": "Lede"},
            {"ru": True, "en": True}, story.image_key,
        )
        late = tg.plan([translated], state, datetime.date(2026, 11, 6))
        self.assertEqual([(item.kind, item.lang) for item in late], [("stale", "en")])
        soon = tg.plan([translated], state, datetime.date(2026, 11, 3))
        self.assertEqual([(item.kind, item.lang) for item in soon], [("send", "en")])


class ExecuteTests(unittest.TestCase):
    def run_execute(self, articles, state, *, today="2026-11-13", token="token", dry_run=False,
                    http_get=None, send=None, max_wait=360, clock=None):
        logs = []
        saves = []
        clock = clock or Clock()
        if http_get is None:
            def http_get(url):
                if "/assets/img/" in url:
                    return 200, jpeg()
                parts = url.rstrip("/").split("/")
                slug, lang = parts[-1], parts[-2]
                match = next(item for item in articles if item.slug == slug)
                return 200, page(match.titles[lang], lang, slug)
        if send is None:
            def send(payload):
                return True, "10"
        tg.execute(
            articles, state,
            today=datetime.date.fromisoformat(today),
            now=datetime.datetime(2026, 11, 13, 12, 0, tzinfo=datetime.timezone.utc),
            token=token, dry_run=dry_run, base="https://cynews24.net", max_wait=max_wait,
            http_get=http_get, sleep=clock.sleep, monotonic=clock.monotonic,
            send=send, log=logs.append, save=lambda: saves.append(json.loads(tg.serialize(state))),
        )
        return logs, saves

    def test_posts_photo_and_text_once_with_the_right_channels(self):
        sent = []
        story = article(image="cape-greco")
        plain = article(slug="plain", cat="society", en=True, image=None, ru_title="Без фото")
        state = tg.empty_state()
        logs, saves = self.run_execute([story, plain], state, send=lambda payload: sent.append(payload) or (True, "7"))
        methods = [(item["chat_id"], item["method"]) for item in sent]
        self.assertEqual(methods, [
            ("@cynews24", "sendPhoto"),
            ("@cynews24en", "sendPhoto"),
            ("@cynews24", "sendMessage"),
            ("@cynews24en", "sendMessage"),
        ])
        photo = sent[0]
        self.assertEqual(photo["photo"], "https://cynews24.net/assets/img/cape-greco-og.jpg")
        self.assertEqual(photo["parse_mode"], "HTML")
        self.assertIn("<b>Заголовок</b>", photo["caption"])
        self.assertIn(">Читать полностью</a>", photo["caption"])
        self.assertIn("#Политика #Кипр", photo["caption"])
        text = sent[2]
        self.assertEqual(text["link_preview_options"], {"is_disabled": False, "url": "https://cynews24.net/ru/plain/"})
        self.assertIn(">Читать полностью</a>", text["text"])
        self.assertEqual(sent[1]["caption"].count("Read more"), 1)
        self.assertEqual(state["posted"]["fresh-story"]["ru"]["status"], "sent")
        self.assertEqual(state["posted"]["fresh-story"]["en"]["status"], "sent")
        self.assertEqual(state["posted"]["plain"]["en"]["status"], "sent")
        self.assertGreaterEqual(len(saves), 4)
        # A second run, including after an edit, sends nothing.
        again = []
        edited = article(image="cape-greco", ru_title="Изменённый заголовок", ru_lede="Новый лид")
        self.run_execute([edited, plain], state, send=lambda payload: again.append(payload) or (True, "8"))
        self.assertEqual(again, [])

    def test_missing_english_is_not_marked_and_posts_later(self):
        sent = []
        story = article(en=False, image=None)
        state = tg.empty_state()
        self.run_execute([story], state, send=lambda payload: sent.append(payload) or (True, "1"))
        self.assertEqual([item["chat_id"] for item in sent], ["@cynews24"])
        self.assertIn("ru", state["posted"][story.slug])
        self.assertNotIn("en", state["posted"][story.slug])
        translated = tg.Article(
            story.slug, story.cat, story.date,
            {"ru": story.titles["ru"], "en": "English title"},
            {"ru": story.ledes["ru"], "en": "English lede"},
            {"ru": True, "en": True}, None,
        )
        self.run_execute([translated], state, send=lambda payload: sent.append(payload) or (True, "2"))
        self.assertEqual(sent[-1]["chat_id"], "@cynews24en")
        self.assertIn("Read more", sent[-1]["text"])
        self.assertEqual(state["posted"][story.slug]["en"]["status"], "sent")

    def test_old_articles_are_marked_without_posting(self):
        sent = []
        old = article(slug="old", date="2026-11-01", en=True)
        no_en = article(slug="old-ru", date="2026-11-01", en=False)
        state = tg.empty_state()
        logs, _saves = self.run_execute([old, no_en], state, send=lambda payload: sent.append(payload) or (True, "1"))
        self.assertEqual(sent, [])
        self.assertEqual(state["posted"]["old"]["ru"]["status"], "skipped-old")
        self.assertEqual(state["posted"]["old"]["en"]["status"], "skipped-old")
        self.assertEqual(state["posted"]["old-ru"]["ru"]["status"], "skipped-old")
        self.assertNotIn("en", state["posted"]["old-ru"])
        self.assertTrue(any("without sending" in line for line in logs))

    def test_missing_token_does_not_advance_state_or_send(self):
        sent = []
        story = article(date="2026-11-01", en=True)
        state = tg.empty_state()
        before = tg.serialize(state)
        logs, saves = self.run_execute([story], state, token="", send=lambda payload: sent.append(payload) or (True, "1"))
        self.assertEqual(sent, [])
        self.assertEqual(saves, [])
        self.assertEqual(tg.serialize(state), before)
        self.assertTrue(any("TELEGRAM_BOT_TOKEN" in line and "not set" in line for line in logs))
        self.assertTrue(any(line.startswith("::notice") for line in logs))

    def test_dry_run_logs_messages_and_does_not_send_or_write(self):
        sent = []
        story = article(image="cape-greco")
        pending = article(slug="later", en=False, image=None)
        old = article(slug="old", date="2026-11-01")
        state = tg.empty_state()
        before = tg.serialize(state)
        logs, saves = self.run_execute(
            [story, pending, old], state, token="secret", dry_run=True,
            send=lambda payload: sent.append(payload) or (True, "1"),
        )
        self.assertEqual(sent, [])
        self.assertEqual(saves, [])
        self.assertEqual(tg.serialize(state), before)
        text = "\n".join(logs)
        self.assertIn("DRY RUN @cynews24 sendPhoto slug=fresh-story", text)
        self.assertIn("photo: https://cynews24.net/assets/img/cape-greco-og.jpg", text)
        self.assertIn("<b>Заголовок</b>", text)
        self.assertIn("Читать полностью", text)
        self.assertIn("DRY RUN @cynews24en sendPhoto slug=fresh-story", text)
        self.assertIn("Read more", text)
        self.assertIn("no English translation yet", text)
        self.assertIn("would mark posted without sending", text)
        self.assertIn("Nothing was sent", text)
        self.assertIn("TELEGRAM_BOT_TOKEN is configured (value not printed).", text)
        self.assertNotIn("secret", text)

    def test_retries_until_the_page_and_image_are_live(self):
        story = article(image="pic")
        clock = Clock()
        calls = {"n": 0}

        def http_get(url):
            calls["n"] += 1
            if clock.now < 20:
                return 404, b"missing"
            if url.endswith(".jpg"):
                return 200, jpeg()
            return 200, page(story.titles["ru"] if "/ru/" in url else story.titles["en"], "ru" if "/ru/" in url else "en", story.slug)

        sent = []
        state = tg.empty_state()
        self.run_execute([story], state, clock=clock, http_get=http_get, send=lambda payload: sent.append(payload) or (True, "3"))
        self.assertGreater(clock.now, 0)
        self.assertEqual(len(sent), 2)
        self.assertEqual(state["posted"][story.slug]["ru"]["status"], "sent")

    def test_english_waits_until_the_translation_is_actually_served(self):
        story = article(image=None)
        clock = Clock()

        def http_get(url):
            if "/ru/" in url:
                return 200, page(story.titles["ru"], "ru", story.slug)
            # The old English page is already 200, but it is still the Russian fallback.
            if clock.now < 15:
                return 200, page(story.titles["ru"], "en", story.slug, noindex=True)
            return 200, page(story.titles["en"], "en", story.slug)

        sent = []
        state = tg.empty_state()
        self.run_execute([story], state, clock=clock, http_get=http_get, send=lambda payload: sent.append(url_of(payload)) or (True, "4"))
        self.assertEqual(sent, [
            "https://cynews24.net/ru/fresh-story/",
            "https://cynews24.net/en/fresh-story/",
        ])
        self.assertGreaterEqual(clock.now, 15)

    def test_live_failure_does_not_mark_and_keeps_earlier_success(self):
        first = article(slug="first", image=None)
        second = article(slug="second", image=None)
        state = tg.empty_state()

        def http_get(url):
            if "/second/" in url:
                return 404, b"no"
            slug = "first"
            lang = "en" if "/en/" in url else "ru"
            title = first.titles[lang]
            return 200, page(title, lang, slug)

        logs, _saves = self.run_execute(
            [first, second], state, max_wait=0,
            http_get=http_get, send=lambda payload: (True, "5"),
        )
        self.assertEqual(state["posted"]["first"]["ru"]["status"], "sent")
        self.assertNotIn("second", state["posted"])
        self.assertTrue(any("second ru" in line for line in logs))

    def test_telegram_failure_does_not_mark(self):
        story = article(image=None, en=False)
        state = tg.empty_state()
        self.run_execute([story], state, send=lambda payload: (False, "Bad Request: caption"))
        self.assertNotIn(story.slug, state["posted"])

    def test_api_retries_429_and_redacts_the_token(self):
        calls = []

        def post(url, data):
            calls.append((url, data))
            if len(calls) == 1:
                return 429, json.dumps({"ok": False, "description": "Too Many Requests token-secret", "parameters": {"retry_after": 1}}).encode()
            return 200, json.dumps({"ok": True, "result": {"message_id": 42}}).encode()

        slept = []
        ok, info = tg.send_telegram(
            "token-secret",
            {"method": "sendMessage", "chat_id": "@cynews24", "text": "Hi", "parse_mode": "HTML", "url": "https://cynews24.net/ru/x/"},
            post=post, sleep=slept.append,
        )
        self.assertTrue(ok)
        self.assertEqual(info, "42")
        self.assertEqual(slept, [1])
        body = json.loads(calls[0][1].decode())
        self.assertNotIn("url", body)
        self.assertEqual(body["parse_mode"], "HTML")
        self.assertEqual(body["text"], "Hi")
        self.assertIn("/bottoken-secret/sendMessage", calls[0][0])

        def bad_request(url, data):
            calls.append(url)
            return 400, json.dumps({"ok": False, "description": "boom token-secret"}).encode()

        calls.clear()
        ok, info = tg.send_telegram("token-secret", {"method": "sendPhoto", "chat_id": "@cynews24en"}, post=bad_request, sleep=slept.append)
        self.assertFalse(ok)
        self.assertNotIn("token-secret", info)
        self.assertIn("boom", info)
        self.assertEqual(len(calls), 1)

    def test_cli_missing_token_keeps_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            articles_dir = os.path.join(tmp, "articles")
            os.makedirs(articles_dir)
            with open(os.path.join(articles_dir, "story.json"), "w", encoding="utf-8") as handle:
                json.dump({
                    "slug": "cli-story", "cat": "economy", "date": "2026-11-13",
                    "ru": {"title": "Новость", "lede": "Лид", "body": "Текст"},
                }, handle)
            state_path = os.path.join(tmp, "telegram-posted.json")
            with open(state_path, "w", encoding="utf-8") as handle:
                handle.write(tg.serialize(tg.empty_state()))
            with open(state_path, encoding="utf-8") as handle:
                before = handle.read()
            env = os.environ.copy()
            env.pop("TELEGRAM_BOT_TOKEN", None)
            env.pop("DRY_RUN", None)
            env.pop("PUSH_STATE", None)
            with mock.patch.dict(os.environ, env, clear=True):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = tg.main(["--articles", articles_dir, "--state", state_path, "--today", "2026-11-13"])
            self.assertEqual(code, 0)
            self.assertIn("TELEGRAM_BOT_TOKEN", output.getvalue())
            with open(state_path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), before)


def url_of(payload):
    if payload["method"] == "sendPhoto":
        return payload["caption"].split('href="', 1)[1].split('"', 1)[0]
    return payload["link_preview_options"]["url"]


class SeedAndWorkflowTests(unittest.TestCase):
    def test_original_articles_are_seeded_and_match_the_loader(self):
        self.assertTrue(os.path.exists(STATE))
        with open(STATE, encoding="utf-8") as handle:
            raw = handle.read()
        state = tg.load_state(STATE)
        self.assertEqual(raw, tg.serialize(state))
        found = []
        for name in ORIGINAL:
            path = os.path.join(ARTICLES, name + ".json")
            if not os.path.exists(path):
                continue
            found.append(tg.load_article(path))
        self.assertGreater(len(found), 0)
        expected = tg.initial_seed(found)
        for slug, entry in expected["posted"].items():
            self.assertEqual(state["posted"].get(slug), entry)
        for entry in state["posted"].values():
            self.assertTrue(set(entry) <= {"ru", "en"})

    def test_workflows_keep_pages_and_avoid_a_posting_loop(self):
        with open(os.path.join(ROOT, ".github", "workflows", "build.yml"), encoding="utf-8") as handle:
            build = handle.read()
        with open(os.path.join(ROOT, ".github", "workflows", "telegram.yml"), encoding="utf-8") as handle:
            poster = handle.read()
        self.assertEqual(build.count("!source/content/telegram-posted.json"), 2)
        self.assertIn("/repos/${GITHUB_REPOSITORY}/pages/builds", build)
        self.assertIn("steps.commit.outputs.pushed == 'true'", build)
        self.assertIn("github.event_name == 'schedule'", build)
        self.assertIn("github.event_name == 'workflow_dispatch'", build)
        self.assertIn("cancel-in-progress: false", build)
        self.assertIn("Test Telegram poster", build)
        self.assertIn('name: Build site', build)
        self.assertIn('workflows: ["Build site"]', poster)
        self.assertIn("TELEGRAM_BOT_TOKEN", poster)
        self.assertIn("value not printed", poster)
        self.assertNotIn('echo "$TELEGRAM_BOT_TOKEN"', poster)
        self.assertNotIn("echo $TELEGRAM_BOT_TOKEN", poster)
        self.assertIn("dry_run", poster)
        self.assertIn("cancel-in-progress: false", poster)
        self.assertIn("branches: [main]", poster)
        self.assertIn("PUSH_STATE", poster)
        self.assertNotIn("sendMessage", poster)
        self.assertNotIn("api.telegram.org", poster)

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
            state = os.path.join(work, "source", "content", "telegram-posted.json")
            os.makedirs(os.path.dirname(state))
            with open(state, "w", encoding="utf-8") as handle:
                handle.write(tg.serialize(tg.empty_state()))
            with open(os.path.join(work, "README"), "a", encoding="utf-8") as handle:
                handle.write("dirty but must not be committed\n")
            with contextlib.redirect_stdout(io.StringIO()):
                tg.commit_and_push(work, state)
            shown = subprocess.check_output(["git", "-C", work, "show", "--name-only", "--pretty=format:%s", "HEAD"], text=True)
            self.assertIn(tg.COMMIT_MESSAGE, shown)
            self.assertIn("source/content/telegram-posted.json", shown)
            self.assertNotIn("README", shown.splitlines()[-1])
            clone = os.path.join(tmp, "clone")
            subprocess.check_call(["git", "clone", "-q", bare, clone])
            self.assertTrue(os.path.exists(os.path.join(clone, "source", "content", "telegram-posted.json")))
            with open(os.path.join(clone, "README"), encoding="utf-8") as handle:
                readme = handle.read()
            self.assertNotIn("dirty", readme)


if __name__ == "__main__":
    unittest.main()
