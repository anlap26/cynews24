# -*- coding: utf-8 -*-
"""Submit CyNews 24 URLs to IndexNow after a push to main.

The key is the 32-hex file at the site root (https://cynews24.net/<key>.txt).
URLs come from sitemap.xml and news-sitemap.xml. When the push has a parent
commit, only URLs whose pages changed are sent. If none of those pages changed
but the generator did, every sitemap URL is sent. Otherwise the two sitemap
addresses themselves are sent.

IndexNow fetches the key file, so this waits until that URL returns the key.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENDPOINT = "https://api.indexnow.org/indexnow"
KEY_NAME = re.compile(r"^[0-9a-f]{32}\.txt$")
LOC = re.compile(r"<loc>([^<]+)</loc>")
SITEMAPS = ("sitemap.xml", "news-sitemap.xml")
# A generator change with no rebuilt page in the diff still means the public
# URLs should be sent. A content-only diff sends just the pages that moved.
GLOBAL_PREFIXES = ("source/build.py", "assets/css/")


def find_key(repo: str) -> str:
    names = sorted(
        name for name in os.listdir(repo)
        if KEY_NAME.match(name) and os.path.isfile(os.path.join(repo, name))
    )
    if len(names) != 1:
        found = ", ".join(names) if names else "none"
        raise SystemExit(f"expected one 32-hex IndexNow key file at the site root, found {found}")
    key = names[0][:-4]
    with open(os.path.join(repo, names[0]), encoding="utf-8") as handle:
        body = handle.read().strip()
    if body != key:
        raise SystemExit("IndexNow key file contents do not match its name")
    return key


def sitemap_urls(repo: str, origin: str) -> list[str]:
    origin = origin.rstrip("/")
    found: list[str] = []
    for name in SITEMAPS:
        path = os.path.join(repo, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            for loc in LOC.findall(handle.read()):
                loc = loc.strip().replace("&amp;", "&")
                if loc.startswith(origin + "/") or loc == origin:
                    found.append(loc)
    return list(dict.fromkeys(found))


def url_to_repo_path(url: str, origin: str) -> str | None:
    origin = origin.rstrip("/")
    if url == origin or url == origin + "/":
        return "index.html"
    prefix = origin + "/"
    if not url.startswith(prefix):
        return None
    rel = url[len(prefix):]
    if not rel or rel.startswith("/"):
        return None
    if rel.endswith("/"):
        return rel + "index.html"
    return rel


def changed_paths(repo: str, before: str, head: str) -> list[str] | None:
    """None means the parent is unknown and every sitemap URL should be sent."""
    before = (before or "").strip()
    if not before or set(before) <= {"0"}:
        return None
    proc = subprocess.run(
        ["git", "-C", repo, "diff", "--name-only", before, head],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"No diff against {before}; submitting every sitemap URL.")
        return None
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def choose_urls(urls: list[str], changed: list[str] | None, origin: str) -> list[str]:
    if changed is None:
        return list(urls)
    changed_set = set(changed)
    picked = [url for url in urls if url_to_repo_path(url, origin) in changed_set]
    if picked:
        return picked
    if any(path.startswith(GLOBAL_PREFIXES) for path in changed):
        return list(urls)
    root = origin.rstrip("/")
    return [f"{root}/sitemap.xml", f"{root}/news-sitemap.xml"]


def chunks(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def http_post(url: str, payload: dict) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "cynews24-indexnow",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", "replace")


def fetch(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "cynews24-indexnow"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()
    except Exception as exc:
        return 0, str(exc).encode("utf-8", "replace")


def wait_for_key(key_url: str, key: str, fetch_url, sleep, attempts: int = 30, delay: int = 10) -> bool:
    for i in range(attempts):
        status, raw = fetch_url(key_url)
        if status == 200 and raw.decode("utf-8", "replace").strip() == key:
            return True
        if i + 1 < attempts:
            sleep(delay)
    return False


def post_indexnow(payload: dict, post, sleep, attempts: int = 6) -> tuple[int, str]:
    last = (0, "")
    for i in range(attempts):
        status, body = post(ENDPOINT, payload)
        last = (status, body)
        if status in (200, 202):
            return status, body
        if status in (403, 429, 500, 502, 503) and i + 1 < attempts:
            sleep(min(30, 5 * (i + 1)))
            continue
        break
    return last


def main() -> int:
    repo = os.environ.get("REPO") or os.path.normpath(os.path.join(HERE, ".."))
    host = (os.environ.get("SITE_HOST") or "cynews24.net").strip()
    origin = (os.environ.get("SITE_ORIGIN") or f"https://{host}").rstrip("/")
    before = os.environ.get("INDEXNOW_BEFORE", "")
    head = os.environ.get("INDEXNOW_HEAD", "HEAD")
    dry = os.environ.get("INDEXNOW_DRY_RUN") == "1"
    key = find_key(repo)
    urls = sitemap_urls(repo, origin)
    if not urls:
        raise SystemExit(f"no sitemap URLs for {origin}")
    chosen = choose_urls(urls, changed_paths(repo, before, head), origin)
    print(f"IndexNow: {len(chosen)} URL(s); {len(urls)} in the sitemaps; key {key}.txt")
    if dry:
        for url in chosen:
            print(url)
        return 0
    key_url = f"{origin}/{key}.txt"
    if not wait_for_key(key_url, key, fetch, time.sleep):
        raise SystemExit(f"key file not reachable at {key_url}")
    for group in chunks(chosen, 10000):
        payload = {"host": host, "key": key, "keyLocation": key_url, "urlList": group}
        status, body = post_indexnow(payload, http_post, time.sleep)
        print(f"IndexNow response {status} for {len(group)} URL(s)")
        if body.strip():
            print(body[:500])
        if status not in (200, 202):
            raise SystemExit(f"IndexNow rejected the list ({status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
