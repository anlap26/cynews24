# -*- coding: utf-8 -*-
"""IndexNow URL selection. No calls to api.indexnow.org."""
from __future__ import annotations

import os
import tempfile
import unittest

import indexnow_submit as idx

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
ORIGIN = "https://cynews24.net"


class ChooseTests(unittest.TestCase):
    def setUp(self):
        self.urls = [
            ORIGIN + "/",
            ORIGIN + "/en/",
            ORIGIN + "/en/cookies/",
            ORIGIN + "/ru/privacy/",
        ]

    def test_unknown_parent_sends_every_sitemap_url(self):
        self.assertEqual(idx.choose_urls(self.urls, None, ORIGIN), self.urls)

    def test_changed_page_is_the_only_url_sent(self):
        got = idx.choose_urls(self.urls, ["en/cookies/index.html", "README.md"], ORIGIN)
        self.assertEqual(got, [ORIGIN + "/en/cookies/"])

    def test_root_and_feed_paths_map_to_files(self):
        self.assertEqual(idx.url_to_repo_path(ORIGIN + "/", ORIGIN), "index.html")
        self.assertEqual(idx.url_to_repo_path(ORIGIN + "/en/", ORIGIN), "en/index.html")
        self.assertEqual(idx.url_to_repo_path(ORIGIN + "/feed.xml", ORIGIN), "feed.xml")

    def test_generator_change_without_pages_sends_the_sitemap_list(self):
        self.assertEqual(idx.choose_urls(self.urls, ["source/build.py"], ORIGIN), self.urls)

    def test_unrelated_push_sends_the_sitemap_addresses(self):
        got = idx.choose_urls(self.urls, ["README.md"], ORIGIN)
        self.assertEqual(got, [ORIGIN + "/sitemap.xml", ORIGIN + "/news-sitemap.xml"])

    def test_zero_before_means_no_parent(self):
        self.assertIsNone(idx.changed_paths(ROOT, "0" * 40, "HEAD"))


class KeyFileTests(unittest.TestCase):
    def test_key_file_must_match_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = "a" * 32
            with open(os.path.join(tmp, key + ".txt"), "w", encoding="utf-8") as handle:
                handle.write(key + "\n")
            self.assertEqual(idx.find_key(tmp), key)

    def test_two_key_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for key in ("a" * 32, "b" * 32):
                with open(os.path.join(tmp, key + ".txt"), "w", encoding="utf-8") as handle:
                    handle.write(key)
            with self.assertRaises(SystemExit):
                idx.find_key(tmp)


class PostTests(unittest.TestCase):
    def test_forbidden_is_retried_until_accepted(self):
        calls = []

        def post(url, payload):
            calls.append(payload["urlList"])
            if len(calls) == 1:
                return 403, "key"
            return 200, ""

        status, _body = idx.post_indexnow({"urlList": ["https://cynews24.net/en/"]}, post, lambda _n: None, attempts=3)
        self.assertEqual(status, 200)
        self.assertEqual(len(calls), 2)

    def test_bad_request_is_not_retried(self):
        calls = []

        def post(url, payload):
            calls.append(url)
            return 400, "bad"

        status, body = idx.post_indexnow({"urlList": []}, post, lambda _n: None, attempts=4)
        self.assertEqual(status, 400)
        self.assertEqual(body, "bad")
        self.assertEqual(calls, [idx.ENDPOINT])


class WorkflowTests(unittest.TestCase):
    def test_workflow_submits_on_push_to_main(self):
        with open(os.path.join(ROOT, ".github", "workflows", "indexnow.yml"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("branches: [main]", text)
        self.assertIn("python source/indexnow_submit.py", text)
        self.assertIn("INDEXNOW_BEFORE", text)
        with open(os.path.join(ROOT, "source", "indexnow_submit.py"), encoding="utf-8") as handle:
            script = handle.read()
        self.assertIn("https://api.indexnow.org/indexnow", script)
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as handle:
            readme = handle.read()
        self.assertIn("IndexNow", readme)
        self.assertIn("api.indexnow.org", readme)
