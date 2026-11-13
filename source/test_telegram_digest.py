# -*- coding: utf-8 -*-
"""Unit tests for the evening Telegram digest. No network and no messages sent."""
from __future__ import annotations

import contextlib
import datetime
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

import telegram_digest as digest
import telegram_post as tg

HERE = os.path.dirname(os.path.abspath(__file__))
ARTICLES = os.path.join(HERE, "content", "articles")
STATE = os.path.join(HERE, "content", "telegram-digest.json")
ROOT = os.path.normpath(os.path.join(HERE, ".."))

NOV13 = [
    "eu-ai-summit-dublin",
    "microsoft-outage-second-day",
    "pension-reform-1-january",
    "cape-greco-monastery-legalisation",
    "frozen-assets-51-million",
    "pedestrian-crossing-camera-fine",
    "diabetes-undiagnosed-cyprus",
    "missing-mushroom-picker-paphos-forest",
    "planning-enforcement-audit",
    "driver-hours-campaign",
    "fintech-jobs-not-registrations",
]


def item(slug, date, seq, ru, en="", cat="society"):
    translated = {"ru": True, "en": bool(en)}
    return digest.Item(
        tg.Article(
            slug=slug,
            cat=cat,
            date=datetime.date.fromisoformat(date),
            titles={"ru": ru, "en": en},
            ledes={"ru": "Лид", "en": "Lede" if en else ""},
            translated=translated,
            image_key=None,
        ),
        seq,
    )


def run(items, state, day, *, token="token", dry_run=False, send=None, base="https://cynews24.net"):
    logs = []
    saved = []
    sent = []

    def default_send(payload):
        sent.append(payload)
        return True, str(len(sent))

    def save():
        saved.append(json.loads(digest.serialize(state)))

    code = digest.execute(
        items,
        state,
        today=day,
        now=datetime.datetime(2026, 11, 13, 18, 0, tzinfo=datetime.timezone.utc),
        token=token,
        dry_run=dry_run,
        base=base,
        send=send or default_send,
        sleep=lambda seconds: None,
        log=logs.append,
        save=save,
    )
    return code, logs, saved, sent


class FormatTests(unittest.TestCase):
    def test_headers_use_the_day_and_month_without_a_year(self):
        self.assertEqual(digest.header(datetime.date(2026, 11, 14), "ru"), "🗞 Главное за день — 14 ноября")
        self.assertEqual(digest.header(datetime.date(2026, 11, 14), "en"), "🗞 Today in Cyprus — 14 November")
        self.assertEqual(digest.header(datetime.date(2026, 11, 13), "ru"), "🗞 Главное за день — 13 ноября")
        self.assertEqual(digest.header(datetime.date(2026, 11, 13), "en"), "🗞 Today in Cyprus — 13 November")
        ru = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        en = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        for month in range(1, 13):
            day = datetime.date(2026, month, 1)
            self.assertEqual(digest.format_when(day, "ru"), f"1 {ru[month - 1]}")
            self.assertEqual(digest.format_when(day, "en"), f"1 {en[month - 1]}")

    def test_message_is_html_with_numbered_links_and_no_preview(self):
        day = datetime.date(2026, 11, 14)
        items = [
            item("alpha", "2026-11-14", 1, "Альфа & <бета>", "Alpha & <beta>"),
            item("second", "2026-11-14", 2, "Вторая", "Second"),
        ]
        russian = digest.render_digest(day, "ru", items, "https://cynews24.net")
        english = digest.render_digest(day, "en", items, "https://cynews24.net/")
        self.assertEqual(
            russian,
            "\n".join([
                "<b>🗞 Главное за день — 14 ноября</b>",
                "",
                '1. <a href="https://cynews24.net/ru/alpha/">Альфа &amp; &lt;бета&gt;</a>',
                '2. <a href="https://cynews24.net/ru/second/">Вторая</a>',
                "",
                'Все новости: <a href="https://cynews24.net/ru/">cynews24.net</a>',
            ]),
        )
        self.assertEqual(
            english,
            "\n".join([
                "<b>🗞 Today in Cyprus — 14 November</b>",
                "",
                '1. <a href="https://cynews24.net/en/alpha/">Alpha &amp; &lt;beta&gt;</a>',
                '2. <a href="https://cynews24.net/en/second/">Second</a>',
                "",
                'All news: <a href="https://cynews24.net/en/">cynews24.net</a>',
            ]),
        )
        self.assertNotIn("<бета>", russian)
        self.assertNotIn("<beta>", english)
        payload = digest.build_payload("ru", russian)
        self.assertEqual(payload["method"], "sendMessage")
        self.assertEqual(payload["chat_id"], "@cynews24")
        self.assertEqual(payload["parse_mode"], "HTML")
        self.assertEqual(payload["text"], russian)
        self.assertEqual(payload["link_preview_options"], {"is_disabled": True})
        self.assertEqual(digest.build_payload("en", english)["chat_id"], "@cynews24en")

    def test_message_over_the_telegram_limit_is_not_sent(self):
        huge = item("huge", "2026-11-13", 1, "слово " * 800, "word " * 800)
        state = digest.empty_state()
        code, logs, saved, sent = run([huge], state, datetime.date(2026, 11, 13))
        self.assertEqual(code, 1)
        self.assertEqual(sent, [])
        self.assertEqual(saved, [])
        self.assertEqual(state["sent"], {})
        self.assertTrue(any("characters" in line for line in logs))
        dry, dry_logs, dry_saved, dry_sent = run([huge], digest.empty_state(), datetime.date(2026, 11, 13), dry_run=True)
        self.assertEqual(dry, 0)
        self.assertEqual(dry_sent, [])
        self.assertEqual(dry_saved, [])
        self.assertTrue(any("over the 4096 limit" in line for line in dry_logs))
        self.assertTrue(any("too long 2" in line for line in dry_logs))


class SelectTests(unittest.TestCase):
    def test_only_that_day_in_site_order_and_english_needs_a_translation(self):
        items = [
            item("later", "2026-11-13", None, "Позже", "Later"),
            item("zeta", "2026-11-13", 5, "Зета", "Zeta"),
            item("alpha", "2026-11-13", 5, "Альфа", "Alpha"),
            item("early", "2026-11-13", 1, "Ранняя", ""),
            item("yesterday", "2026-11-12", 0, "Вчера", "Yesterday"),
            item("blank-en", "2026-11-13", 2, "Только русский", "   "),
        ]
        day = datetime.date(2026, 11, 13)
        russian = [entry.article.slug for entry in digest.select(items, day, "ru")]
        english = [entry.article.slug for entry in digest.select(items, day, "en")]
        self.assertEqual(russian, ["early", "blank-en", "alpha", "zeta", "later"])
        self.assertEqual(english, ["alpha", "zeta", "later"])
        self.assertNotIn("yesterday", russian)

    def test_november_13_articles_and_no_other_day(self):
        items = digest.load_items(ARTICLES)
        day = datetime.date(2026, 11, 13)
        for lang in ("ru", "en"):
            chosen = digest.select(items, day, lang)
            self.assertEqual([entry.article.slug for entry in chosen], NOV13)
            text = digest.render_digest(day, lang, chosen, "https://cynews24.net")
            self.assertLessEqual(len(text), digest.MESSAGE_LIMIT)
            self.assertIn(digest.header(day, lang), text)
            self.assertNotIn("fitto-cyprus-talks", text)
            self.assertNotIn("cyprus-video-game-industry", text)
            self.assertNotIn("governors-beach-caravan-eviction", text)
            home = f"https://cynews24.net/{lang}/"
            self.assertIn(f'<a href="{home}">cynews24.net</a>', text)
            for index, entry in enumerate(chosen, start=1):
                title = tg.escape_text(" ".join(entry.article.titles[lang].split()))
                url = f"https://cynews24.net/{lang}/{entry.article.slug}/"
                self.assertIn(f'{index}. <a href="{url}">{title}</a>', text)
            payload = digest.build_payload(lang, text)
            self.assertEqual(payload["parse_mode"], "HTML")
            self.assertTrue(payload["link_preview_options"]["is_disabled"])
            self.assertNotIn("el", payload["chat_id"])

    def test_rejects_bad_seq_and_duplicate_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({
                    "slug": "bad", "cat": "society", "date": "2026-11-13", "seq": "1",
                    "ru": {"title": "A", "lede": "B", "body": "C"},
                }, handle)
            with self.assertRaises(SystemExit):
                digest.load_items(tmp)
        with tempfile.TemporaryDirectory() as tmp:
            body = {"slug": "same", "cat": "society", "date": "2026-11-13", "ru": {"title": "A", "lede": "B", "body": "C"}}
            for name in ("a.json", "b.json"):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as handle:
                    json.dump(body, handle)
            with self.assertRaises(SystemExit):
                digest.load_items(tmp)


class StateTests(unittest.TestCase):
    def test_shipped_state_is_empty_and_roundtrips(self):
        self.assertTrue(os.path.exists(STATE))
        with open(STATE, encoding="utf-8") as handle:
            raw = handle.read()
        state = digest.load_state(STATE)
        self.assertEqual(raw, digest.serialize(state))
        self.assertEqual(state["sent"], {})
        self.assertIn("@cynews24", state["note"])
        self.assertIn("@cynews24en", state["note"])

    def test_rejects_a_corrupt_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"sent": {"nope": {"ru": {"status": "sent", "at": "2026-11-13T18:00:00Z"}}}}')
            with self.assertRaises(SystemExit):
                digest.load_state(path)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"sent": {"2026-11-13": {"el": {"status": "sent", "at": "2026-11-13T18:00:00Z"}}}}')
            with self.assertRaises(SystemExit):
                digest.load_state(path)

    def test_mark_is_once_per_language(self):
        state = digest.empty_state()
        day = datetime.date(2026, 11, 13)
        moment = datetime.datetime(2026, 11, 13, 18, 5, tzinfo=datetime.timezone.utc)
        digest.mark(state, day, "ru", "sent", moment, 11)
        digest.mark(state, day, "ru", "sent", moment, 99)
        self.assertTrue(digest.is_marked(state, day, "ru"))
        self.assertFalse(digest.is_marked(state, day, "en"))
        self.assertEqual(state["sent"]["2026-11-13"]["ru"]["count"], 11)
        self.assertEqual(state["sent"]["2026-11-13"]["ru"]["status"], "sent")


class ExecuteTests(unittest.TestCase):
    def stories(self):
        return [
            item("one", "2026-11-13", 1, "Первая & новость", "First & story"),
            item("two", "2026-11-13", 2, "Вторая", "Second"),
            item("other", "2026-11-12", 3, "Другой день", "Other day"),
        ]

    def test_sends_both_channels_then_a_rerun_sends_nothing(self):
        state = digest.empty_state()
        day = datetime.date(2026, 11, 13)
        code, logs, saved, sent = run(self.stories(), state, day)
        self.assertEqual(code, 0)
        self.assertEqual([payload["chat_id"] for payload in sent], ["@cynews24", "@cynews24en"])
        self.assertEqual(sent[0]["parse_mode"], "HTML")
        self.assertTrue(sent[0]["link_preview_options"]["is_disabled"])
        self.assertIn("🗞 Главное за день — 13 ноября", sent[0]["text"])
        self.assertIn("https://cynews24.net/ru/one/", sent[0]["text"])
        self.assertIn("Первая &amp; новость", sent[0]["text"])
        self.assertNotIn("other", sent[0]["text"])
        self.assertIn("🗞 Today in Cyprus — 13 November", sent[1]["text"])
        self.assertIn("https://cynews24.net/en/two/", sent[1]["text"])
        self.assertNotIn("other", sent[1]["text"])
        self.assertEqual(len(saved), 2)
        self.assertEqual(set(state["sent"]["2026-11-13"]), {"ru", "en"})
        self.assertTrue(any("message_id=1" in line for line in logs))
        self.assertTrue(any("sent 2" in line for line in logs))

        again, again_logs, again_saved, again_sent = run(self.stories(), state, day)
        self.assertEqual(again, 0)
        self.assertEqual(again_sent, [])
        self.assertEqual(again_saved, [])
        self.assertTrue(any("already sent" in line for line in again_logs))

    def test_empty_day_posts_nothing_and_does_not_record_the_date(self):
        state = digest.empty_state()
        code, logs, saved, sent = run(self.stories(), state, datetime.date(2026, 11, 1))
        self.assertEqual(code, 0)
        self.assertEqual(sent, [])
        self.assertEqual(saved, [])
        self.assertEqual(state["sent"], {})
        self.assertTrue(any("no articles" in line for line in logs))

    def test_failed_channel_is_not_marked_and_is_retried(self):
        state = digest.empty_state()
        token = "super-secret-value"

        def send(payload):
            if payload["chat_id"] == "@cynews24en":
                return False, f"Boom {token} rejected"
            self.assertNotIn(token, json.dumps(payload))
            return True, "9"

        code, logs, saved, sent = run(self.stories(), state, datetime.date(2026, 11, 13), token=token, send=send)
        self.assertEqual(code, 1)
        self.assertIn("ru", state["sent"]["2026-11-13"])
        self.assertNotIn("en", state["sent"]["2026-11-13"])
        self.assertEqual(len(saved), 1)
        joined = "\n".join(logs)
        self.assertNotIn(token, joined)
        self.assertIn("***", joined)

        retried = []

        def send_rest(payload):
            retried.append(payload["chat_id"])
            return True, "10"

        code, logs, saved, sent = run(self.stories(), state, datetime.date(2026, 11, 13), token=token, send=send_rest)
        self.assertEqual(code, 0)
        self.assertEqual(retried, ["@cynews24en"])
        self.assertEqual(sent, [])
        self.assertIn("en", state["sent"]["2026-11-13"])

    def test_missing_token_does_not_send_or_write_state(self):
        state = digest.empty_state()
        code, logs, saved, sent = run(self.stories(), state, datetime.date(2026, 11, 13), token="")
        self.assertEqual(code, 0)
        self.assertEqual(sent, [])
        self.assertEqual(saved, [])
        self.assertEqual(state["sent"], {})
        self.assertTrue(any("TELEGRAM_BOT_TOKEN is not set" in line for line in logs))
        self.assertTrue(any("not set" in line and "value not printed" in line for line in logs))

    def test_dry_run_prints_the_digest_and_leaves_state_alone(self):
        state = digest.empty_state()
        before = digest.serialize(state)
        code, logs, saved, sent = run(self.stories(), state, datetime.date(2026, 11, 13), dry_run=True, token="super-secret-value")
        self.assertEqual(code, 0)
        self.assertEqual(sent, [])
        self.assertEqual(saved, [])
        self.assertEqual(digest.serialize(state), before)
        text = "\n".join(logs)
        self.assertIn("DRY RUN @cynews24 sendMessage", text)
        self.assertIn("DRY RUN @cynews24en sendMessage", text)
        self.assertIn("link_preview=disabled", text)
        self.assertIn("🗞 Главное за день — 13 ноября", text)
        self.assertIn("🗞 Today in Cyprus — 13 November", text)
        self.assertIn("https://cynews24.net/ru/one/", text)
        self.assertIn("https://cynews24.net/en/two/", text)
        self.assertIn("Все новости:", text)
        self.assertIn("All news:", text)
        self.assertIn("Nothing was sent and the state file was not changed.", text)
        self.assertNotIn("super-secret-value", text)
        self.assertIn("would send 2", text)

    def test_dry_run_of_an_already_sent_day_does_not_offer_to_post_again(self):
        state = digest.empty_state()
        day = datetime.date(2026, 11, 13)
        digest.mark(state, day, "ru", "sent", datetime.datetime(2026, 11, 13, tzinfo=datetime.timezone.utc), 2)
        digest.mark(state, day, "en", "sent", datetime.datetime(2026, 11, 13, tzinfo=datetime.timezone.utc), 2)
        code, logs, saved, sent = run(self.stories(), state, day, dry_run=True)
        self.assertEqual(code, 0)
        self.assertEqual(sent, [])
        self.assertEqual(saved, [])
        self.assertTrue(all("would not post again" in line or "summary" in line or "TELEGRAM_BOT_TOKEN" in line or "Digest date" in line for line in logs))
        self.assertIn("would send 0", "\n".join(logs))

    def test_redacts_tokens_in_git_errors(self):
        text = digest.redact(
            "fatal: https://x-access-token:ghs_abcdefghijklmnopqrstuvwxyz@github.com/acme/repo rejected super-secret",
            "super-secret",
        )
        self.assertNotIn("super-secret", text)
        self.assertNotIn("ghs_abcdefghijklmnopqrstuvwxyz", text)
        self.assertIn("x-access-token:***", text)
        self.assertIn("***", text)

    def test_main_dry_run_for_13_november_does_not_call_telegram(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = os.path.join(tmp, "telegram-digest.json")
            with open(state_path, "w", encoding="utf-8") as handle:
                handle.write(digest.serialize(digest.empty_state()))
            with open(state_path, encoding="utf-8") as handle:
                before = handle.read()
            output = io.StringIO()
            env = os.environ.copy()
            env["TELEGRAM_BOT_TOKEN"] = "super-secret-value"
            env["DRY_RUN"] = "false"
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(tg, "send_telegram") as send:
                    with contextlib.redirect_stdout(output):
                        code = digest.main([
                            "--dry-run",
                            "--today", "2026-11-13",
                            "--articles", ARTICLES,
                            "--state", state_path,
                            "--base", "https://cynews24.net",
                        ])
            self.assertEqual(code, 0)
            send.assert_not_called()
            with open(state_path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), before)
            printed = output.getvalue()
            self.assertNotIn("super-secret-value", printed)
            self.assertIn("🗞 Главное за день — 13 ноября", printed)
            self.assertIn("🗞 Today in Cyprus — 13 November", printed)
            self.assertIn("would send 2", printed)
            for slug in NOV13:
                self.assertIn(f"https://cynews24.net/ru/{slug}/", printed)
                self.assertIn(f"https://cynews24.net/en/{slug}/", printed)
            self.assertNotIn("fitto-cyprus-talks", printed)

    def test_bad_date_is_rejected(self):
        with self.assertRaises(SystemExit):
            digest.parse_day("13 November")
        with self.assertRaises(SystemExit):
            digest.parse_day("2026-02-31")
        self.assertEqual(digest.parse_day(" 2026-11-13 "), datetime.date(2026, 11, 13))


class WorkflowTests(unittest.TestCase):
    def test_workflow_schedule_dispatch_and_secret_handling(self):
        with open(os.path.join(ROOT, ".github", "workflows", "telegram-digest.yml"), encoding="utf-8") as handle:
            workflow = handle.read()
        with open(os.path.join(ROOT, ".github", "workflows", "build.yml"), encoding="utf-8") as handle:
            build = handle.read()
        self.assertIn("name: Telegram evening digest", workflow)
        self.assertIn('cron: "0 18 * * *"', workflow)
        self.assertIn("UTC+2", workflow)
        self.assertIn("winter", workflow)
        self.assertIn("Asia/Nicosia", workflow)
        self.assertIn("dry_run", workflow)
        self.assertIn("TELEGRAM_BOT_TOKEN", workflow)
        self.assertIn("value not printed", workflow)
        self.assertNotIn('echo "$TELEGRAM_BOT_TOKEN"', workflow)
        self.assertNotIn("echo $TELEGRAM_BOT_TOKEN", workflow)
        self.assertNotIn("api.telegram.org", workflow)
        self.assertIn("PUSH_STATE", workflow)
        self.assertIn("python source/telegram_digest.py", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertEqual(build.count("!source/content/telegram-digest.json"), 2)
        self.assertEqual(build.count("!source/content/telegram-posted.json"), 2)
        self.assertEqual(build.count("!source/content/facebook-posted.json"), 2)

    def test_existing_posters_are_not_wired_to_the_digest(self):
        for relative in (
            "source/telegram_post.py",
            "source/facebook_post.py",
            ".github/workflows/telegram.yml",
            ".github/workflows/facebook.yml",
        ):
            with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
                source = handle.read()
            self.assertNotIn("telegram_digest", source, relative)
            self.assertNotIn("telegram-digest", source, relative)
            self.assertNotIn("Главное за день", source, relative)
        with open(os.path.join(HERE, "telegram_digest.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("api.telegram.org", source)
        self.assertIn("send_telegram", source)

    def test_commit_and_push_only_the_digest_state(self):
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
            state = os.path.join(work, "source", "content", "telegram-digest.json")
            os.makedirs(os.path.dirname(state))
            with open(state, "w", encoding="utf-8") as handle:
                handle.write(digest.serialize(digest.empty_state()))
            subprocess.check_call(["git", "-C", work, "add", "source/content/telegram-digest.json"])
            subprocess.check_call(["git", "-C", work, "commit", "-q", "-m", "state"])
            subprocess.check_call(["git", "-C", work, "push", "-q", "origin", "HEAD:main"])
            with open(state, "w", encoding="utf-8") as handle:
                marked = digest.empty_state()
                digest.mark(
                    marked,
                    datetime.date(2026, 11, 13),
                    "ru",
                    "sent",
                    datetime.datetime(2026, 11, 13, tzinfo=datetime.timezone.utc),
                    2,
                )
                handle.write(digest.serialize(marked))
            with open(os.path.join(work, "README"), "a", encoding="utf-8") as handle:
                handle.write("dirty but must not be committed\n")
            with contextlib.redirect_stdout(io.StringIO()):
                digest.commit_and_push(work, state)
            shown = subprocess.check_output(
                ["git", "-C", work, "show", "--name-only", "--pretty=format:%s", "HEAD"],
                text=True,
            )
            self.assertIn(digest.COMMIT_MESSAGE, shown)
            self.assertIn("source/content/telegram-digest.json", shown)
            self.assertNotIn("README", shown.splitlines()[-1])
            clone = os.path.join(tmp, "clone")
            subprocess.check_call(["git", "clone", "-q", bare, clone])
            with open(os.path.join(clone, "source", "content", "telegram-digest.json"), encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["sent"]["2026-11-13"]["ru"]["status"], "sent")
            with open(os.path.join(clone, "README"), encoding="utf-8") as handle:
                self.assertNotIn("dirty", handle.read())


if __name__ == "__main__":
    unittest.main()
