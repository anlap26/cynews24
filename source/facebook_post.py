# -*- coding: utf-8 -*-
"""Post new CyNews 24 articles to the Facebook Page after the pages are live.

The post language is FB_POST_LANG (default en). English links to /en/<slug>/,
Russian to /ru/<slug>/ and Greek to /el/<slug>/. The message is the title, a
one- or two-sentence lead, and a few hashtags. Facebook builds the link
preview from the article's og:title, og:description and og:image.

Slugs already handled are stored in source/content/facebook-posted.json.
Editing an article does not post it again. An article first seen more than
3 days after its publication date is recorded without sending, so enabling
the Page later cannot flood it. A run publishes at most 10 articles.

FB_PAGE_TOKEN and FB_PAGE_ID are repository secrets. When the token or the
Page id is missing this script logs a notice, leaves the state file untouched
and exits 0. DRY_RUN=1 (or --dry-run) prints the messages, checks that the
Page is reachable, and does not publish or write state. Secrets are never
printed.
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from zoneinfo import ZoneInfo

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_ARTICLES = os.path.join(ROOT, "source", "content", "articles")
DEFAULT_STATE = os.path.join(ROOT, "source", "content", "facebook-posted.json")
GRAPH = "https://graph.facebook.com/v21.0"

NOTE = (
    "Slugs already handled for the Facebook Page. "
    "FB_POST_LANG chooses the post language (default en, link /en/; "
    "ru links to /ru/, el to /el/). An entry means do not post again."
)

LANGS = ("ru", "en", "el")
DEFAULT_LANG = "en"
CATS = ("politics", "economy", "real-estate", "society", "tourism", "sport", "world")
CAT_TAGS = {
    "en": {
        "politics": "#Politics",
        "economy": "#Economy",
        "real-estate": "#RealEstate",
        "society": "#Society",
        "tourism": "#Tourism",
        "sport": "#Sport",
        "world": "#World",
    },
    "ru": {
        "politics": "#Политика",
        "economy": "#Экономика",
        "real-estate": "#Недвижимость",
        "society": "#Общество",
        "tourism": "#Туризм",
        "sport": "#Спорт",
        "world": "#ВМире",
    },
    "el": {
        "politics": "#Πολιτική",
        "economy": "#Οικονομία",
        "real-estate": "#Ακίνητα",
        "society": "#Κοινωνία",
        "tourism": "#Τουρισμός",
        "sport": "#Αθλητισμός",
        "world": "#Κόσμος",
    },
}
COUNTRY = {"en": "#Cyprus", "ru": "#Кипр", "el": "#Κύπρος"}
NEWS = {"en": "#CyprusNews", "ru": "#новостиКипра", "el": "#ΕιδήσειςΚύπρου"}
MAX_POSTS = 10
POST_DELAY = 3.0
LEAD_SENTENCES = 2
LEAD_LIMIT = 500
# Keep in sync with source/build.py so page addresses match the site.
_TR = dict(zip("абвгдеёзийклмнопрстуфхыэ", "abvgdeezijklmnoprstufhye")) | {
    "ж": "zh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ю": "yu", "я": "ya", "ъ": "", "ь": "",
}
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]*)"')
USER_AGENT = "cynews24-facebook-poster"
COMMIT_MESSAGE = "Facebook: отмечены опубликованные статьи"
# Application / Page rate-limit codes, plus Facebook's transient codes.
TRANSIENT_CODES = {1, 2, 4, 17, 32, 613}
TRANSIENT_HTTP = {0, 429, 500, 502, 503, 504}


def slugify(value) -> str:
    text = "".join(_TR.get(ch, ch) for ch in str(value).lower())
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text)).strip("-")[:70].strip("-")


def _clean(value):
    if value is None:
        return ""
    return value.strip() if isinstance(value, str) else value


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def require_lang(lang: str) -> str:
    value = (lang or "").strip().lower() or DEFAULT_LANG
    if value not in LANGS:
        raise SystemExit(f"FB_POST_LANG must be one of: {', '.join(LANGS)}")
    return value


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer") from exc
    if value < 0:
        raise SystemExit(f"{name} must be >= 0")
    return value


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be a number") from exc
    if value < 0:
        raise SystemExit(f"{name} must be >= 0")
    return value


def cyprus_today() -> datetime.date:
    override = os.environ.get("TODAY")
    if override:
        return datetime.date.fromisoformat(override)
    return datetime.datetime.now(ZoneInfo("Asia/Nicosia")).date()


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def stamp(moment: datetime.datetime) -> str:
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def older_than_three_days(article_date: datetime.date, today: datetime.date) -> bool:
    return (today - article_date).days > 3


def article_url(base: str, lang: str, slug: str) -> str:
    return f"{base.rstrip('/')}/{lang}/{slug}/"


def hashtags(lang: str, cat: str) -> str:
    return f"{CAT_TAGS[lang][cat]} {COUNTRY[lang]} {NEWS[lang]}"


def clip(text: str, room: int) -> str:
    """Shorten text to at most `room` characters, keeping a word boundary when it fits."""
    if room <= 0 or not text:
        return ""
    if len(text) <= room:
        return text
    if room == 1:
        return "…"
    budget = room - 1
    cut = text[:budget].rstrip()
    space = cut.rfind(" ")
    if space >= budget // 2:
        cut = cut[:space].rstrip()
    if not cut:
        cut = text[:budget]
    return cut + "…"


def lead_summary(lede: str, sentences: int = LEAD_SENTENCES, limit: int = LEAD_LIMIT) -> str:
    """The article lead, kept to one or two sentences."""
    text = " ".join((lede or "").split())
    if not text:
        return ""
    parts = [part.strip() for part in _SENTENCE.split(text) if part.strip()]
    chosen = " ".join(parts[:sentences]) if parts else text
    if len(chosen) > limit:
        chosen = clip(chosen, limit)
    return chosen


def render_message(title: str, lede: str, tags: str) -> str:
    title = " ".join((title or "").split())
    lead = lead_summary(lede)
    tags = " ".join((tags or "").split())
    return "\n\n".join(part for part in (title, lead, tags) if part)


def redact(text: str, token: str = "", page_id: str = "") -> str:
    if token and token in text:
        text = text.replace(token, "***")
    if page_id and page_id in text:
        text = text.replace(page_id, "***")
    return text


def page_name_ok(name: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", name.casefold())
    return "cynews24" in compact


def visible_post_id(post_id: str, page_id: str) -> str:
    """Drop the Page id prefix Facebook puts on a post id."""
    prefix = f"{page_id}_" if page_id else ""
    if prefix and post_id.startswith(prefix):
        return post_id[len(prefix):] or "-"
    if page_id and page_id in post_id:
        return "***"
    return post_id or "-"


@dataclass(frozen=True)
class Article:
    slug: str
    cat: str
    date: datetime.date
    titles: dict
    ledes: dict
    translated: dict
    image_key: str | None


@dataclass(frozen=True)
class Action:
    kind: str  # send, stale, untranslated, deferred
    lang: str
    article: Article


def _translated(block: dict) -> bool:
    if not isinstance(block, dict):
        return False
    return bool(_clean(block.get("title"))) and bool(_clean(block.get("lede"))) and bool(_clean(block.get("body")))


def _text(block: dict, key: str) -> str:
    value = _clean(block.get(key)) if isinstance(block, dict) else ""
    if not isinstance(value, str):
        value = "" if value is None else str(value)
    return value


def load_article(path: str) -> Article:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: article must be a JSON object")
    stem = os.path.splitext(os.path.basename(path))[0]
    slug = slugify(_clean(data.get("slug")) or stem) or slugify((data.get("ru") or {}).get("title", ""))
    if not slug or not SLUG_RE.fullmatch(slug):
        raise SystemExit(f"{path}: cannot make a page address (slug)")
    cat = _clean(data.get("cat"))
    if cat not in CATS:
        raise SystemExit(f"{path}: unknown category {cat!r}")
    try:
        date = datetime.date.fromisoformat(str(_clean(data.get("date")))[:10])
    except ValueError as exc:
        raise SystemExit(f"{path}: bad date") from exc
    ru = data.get("ru") if isinstance(data.get("ru"), dict) else {}
    if not _translated(ru):
        raise SystemExit(f"{path}: Russian title, lede and body are required")
    titles = {}
    ledes = {}
    translated = {}
    for lang in LANGS:
        block = data.get(lang) if isinstance(data.get(lang), dict) else {}
        titles[lang] = _text(block, "title")
        ledes[lang] = _text(block, "lede")
        translated[lang] = True if lang == "ru" else _translated(block)
    image = _clean(data.get("image"))
    img = _clean(data.get("img"))
    if isinstance(image, str) and image.strip():
        image_key = slug
    elif isinstance(img, str) and img.strip():
        image_key = img.strip()
    else:
        image_key = None
    return Article(slug, cat, date, titles, ledes, translated, image_key)


def load_articles(directory: str) -> list[Article]:
    if not os.path.isdir(directory):
        raise SystemExit(f"Articles directory not found: {directory}")
    names = sorted(name for name in os.listdir(directory) if name.endswith(".json"))
    articles = [load_article(os.path.join(directory, name)) for name in names]
    slugs = [article.slug for article in articles]
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        raise SystemExit(f"Duplicate slugs: {duplicates}")
    return articles


def empty_state() -> dict:
    return {"note": NOTE, "posted": {}}


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return empty_state()
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("posted"), dict):
        raise SystemExit(f"{path}: expected an object with a posted map")
    for slug, record in data["posted"].items():
        if not isinstance(slug, str) or not isinstance(record, dict):
            raise SystemExit(f"{path}: {slug} must be an object")
        if not isinstance(record.get("status"), str) or not record["status"]:
            raise SystemExit(f"{path}: {slug} must be an object with a status")
        if not isinstance(record.get("at"), str) or not record["at"]:
            raise SystemExit(f"{path}: {slug} must include at")
        lang = record.get("lang")
        if lang is not None and lang not in LANGS:
            raise SystemExit(f"{path}: {slug} has unknown language {lang}")
    if "note" not in data:
        data["note"] = NOTE
    return data


def serialize(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(serialize(state))
    os.replace(temporary, path)


def is_marked(state: dict, slug: str) -> bool:
    entry = state.get("posted", {}).get(slug)
    if entry is None:
        return False
    if not isinstance(entry, dict):
        raise SystemExit(f"facebook state for {slug} must be an object")
    return True


def mark(state: dict, slug: str, status: str, moment: datetime.datetime, lang: str) -> None:
    entry = state.setdefault("posted", {})
    if not isinstance(entry, dict):
        raise SystemExit("facebook state posted map must be an object")
    if slug not in entry:
        entry[slug] = {"at": stamp(moment), "lang": lang, "status": status}


def initial_seed(articles: list[Article], lang: str = DEFAULT_LANG) -> dict:
    """Mark every current article handled, so the first real run posts nothing old."""
    lang = require_lang(lang)
    posted = {}
    for article in sorted(articles, key=lambda item: item.slug):
        posted[article.slug] = {
            "at": article.date.isoformat() + "T00:00:00Z",
            "lang": lang,
            "status": "seeded",
        }
    return {"note": NOTE, "posted": posted}


def plan(articles: list[Article], state: dict, today: datetime.date, lang: str) -> list[Action]:
    actions = []
    ordered = sorted(articles, key=lambda article: (article.date, article.slug))
    for article in ordered:
        if is_marked(state, article.slug):
            continue
        if not article.translated.get(lang):
            actions.append(Action("untranslated", lang, article))
            continue
        kind = "stale" if older_than_three_days(article.date, today) else "send"
        actions.append(Action(kind, lang, article))
    return actions


def apply_cap(actions: list[Action], max_posts: int) -> list[Action]:
    """Keep at most `max_posts` sends. Further sends stay unmarked for the next run."""
    kept = []
    sends = 0
    for action in actions:
        if action.kind != "send":
            kept.append(action)
            continue
        if sends >= max_posts:
            kept.append(Action("deferred", action.lang, action.article))
            continue
        sends += 1
        kept.append(action)
    return kept


def build_post(article: Article, lang: str, base: str) -> dict:
    return {
        "message": render_message(article.titles[lang], article.ledes[lang], hashtags(lang, article.cat)),
        "link": article_url(base, lang, article.slug),
    }


def og_image_url(body: bytes) -> str:
    text = body.decode("utf-8", errors="replace")
    match = _OG_IMAGE.search(text)
    if not match:
        return ""
    return html.unescape(match.group(1)).strip()


def is_page_ready(body: bytes, lang: str, slug: str, title: str) -> bool:
    text = body.decode("utf-8", errors="replace")
    if f"/{lang}/{slug}/" not in text:
        return False
    if 'name="robots" content="noindex' in text:
        return False
    if title not in html.unescape(text):
        return False
    for prop in ("og:title", "og:description", "og:image"):
        if f'property="{prop}"' not in text:
            return False
    image = og_image_url(body)
    return image.startswith("https://")


def is_image_ready(body: bytes) -> bool:
    return len(body) >= 100 and body.startswith(b"\xff\xd8")


def http_request(method: str, url: str, data: bytes | None = None, headers: dict | None = None,
                 timeout: float = 30, token: str = "", page_id: str = "") -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return exc.code, body
    except Exception as exc:
        return 0, redact(str(exc), token, page_id).encode("utf-8", errors="replace")


def http_get(url: str, timeout: float = 20) -> tuple[int, bytes]:
    return http_request(
        "GET",
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Accept": "*/*",
        },
        timeout=timeout,
    )


def http_post(url: str, data: bytes, timeout: float = 30) -> tuple[int, bytes]:
    return http_request(
        "POST",
        url,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        timeout=timeout,
    )


def _graph_error(status: int, data: dict, token: str, page_id: str) -> tuple[str, bool]:
    err = data.get("error") if isinstance(data.get("error"), dict) else {}
    message = str(err.get("message") or f"HTTP {status}")
    try:
        code = int(err["code"]) if err.get("code") is not None else None
    except (TypeError, ValueError):
        code = None
    parts = [message]
    if err.get("type"):
        parts.append(f"type={err['type']}")
    if code is not None:
        parts.append(f"code={code}")
    if err.get("fbtrace_id"):
        parts.append(f"fbtrace_id={err['fbtrace_id']}")
    transient = bool(err.get("is_transient")) or code in TRANSIENT_CODES or status in TRANSIENT_HTTP
    return redact("; ".join(parts), token, page_id), transient


def parse_graph(status: int, raw: bytes, token: str, page_id: str) -> tuple[bool, str, bool]:
    text = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(text or "{}")
    except json.JSONDecodeError:
        return False, redact(f"HTTP {status}", token, page_id), status in TRANSIENT_HTTP
    if not isinstance(data, dict):
        return False, redact(f"HTTP {status}", token, page_id), status in TRANSIENT_HTTP
    if isinstance(data.get("error"), dict):
        info, transient = _graph_error(status, data, token, page_id)
        return False, info, transient
    if data.get("id") and (status == 0 or 200 <= status < 300):
        return True, visible_post_id(str(data["id"]), page_id), False
    return False, redact(f"HTTP {status}", token, page_id), status in TRANSIENT_HTTP


def parse_page(status: int, raw: bytes, token: str, page_id: str) -> tuple[bool, str]:
    text = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(text or "{}")
    except json.JSONDecodeError:
        return False, redact(f"HTTP {status}", token, page_id)
    if not isinstance(data, dict):
        return False, redact(f"HTTP {status}", token, page_id)
    if isinstance(data.get("error"), dict):
        info, _transient = _graph_error(status, data, token, page_id)
        return False, info
    name = data.get("name")
    if isinstance(name, str) and name.strip() and (status == 0 or 200 <= status < 300):
        return True, name.strip()
    return False, redact(f"HTTP {status}", token, page_id)


def probe_page(page_id: str, token: str, get) -> tuple[bool, str]:
    """GET /{page-id}?fields=name. The token stays in the query and is never logged."""
    url = (
        f"{GRAPH}/{urllib.parse.quote(page_id, safe='')}"
        f"?fields=name&access_token={urllib.parse.quote(token, safe='')}"
    )
    try:
        status, raw = get(url)
    except Exception as exc:
        return False, redact(str(exc), token, page_id)
    return parse_page(status, raw, token, page_id)


def send_facebook(token: str, page_id: str, payload: dict, *, post, sleep, attempts: int = 4) -> tuple[bool, str]:
    url = f"{GRAPH}/{urllib.parse.quote(page_id, safe='')}/feed"
    data = urllib.parse.urlencode({
        "message": payload["message"],
        "link": payload["link"],
        "access_token": token,
    }).encode("utf-8")
    last = "no response"
    for attempt in range(attempts):
        try:
            status, raw = post(url, data)
        except Exception as exc:
            last = redact(str(exc), token, page_id)
            if attempt == attempts - 1:
                return False, last
            sleep(2)
            continue
        ok, info, transient = parse_graph(status, raw, token, page_id)
        if ok:
            return True, info
        last = info
        if not transient or attempt == attempts - 1:
            return False, last
        sleep(2)
    return False, last


def wait_until_live(action: Action, base: str, *, get, sleep, monotonic, deadline, log) -> bool:
    url = article_url(base, action.lang, action.article.slug)
    title = action.article.titles[action.lang]
    waits = (15, 30, 45, 60)
    attempt = 0
    while True:
        status, body = get(url)
        ready = status == 200 and is_page_ready(body, action.lang, action.article.slug, title)
        image = og_image_url(body) if ready else ""
        if ready:
            image_status, image_body = get(image)
            ready = image_status == 200 and is_image_ready(image_body)
        if ready:
            log(f"live {url}")
            return True
        log(f"waiting for {url} (HTTP {status})")
        remaining = deadline - monotonic()
        if remaining <= 0:
            return False
        step = min(waits[min(attempt, len(waits) - 1)], remaining)
        attempt += 1
        log(f"retrying in {int(step)}s")
        sleep(step)


def _git(repo: str, args: list[str], env: dict, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=repo, env=env, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"git {' '.join(args[1:] if args and args[0] == 'git' else args)} failed: {detail}")
    return result


def commit_and_push(repo: str, path: str) -> None:
    """Commit only the state file and push it to main. Retries if main moved."""
    env = os.environ.copy()
    env["GIT_MERGE_AUTOEDIT"] = "no"
    env["GIT_TERMINAL_PROMPT"] = "0"
    _git(repo, ["git", "config", "user.name", "cynews24-facebook[bot]"], env)
    _git(repo, ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], env)
    _git(repo, ["git", "add", "--", path], env)
    diff = _git(repo, ["git", "diff", "--cached", "--quiet"], env, check=False)
    if diff.returncode == 0:
        print("State file unchanged; not committing.", flush=True)
        return
    if diff.returncode != 1:
        raise SystemExit((diff.stderr or "git diff failed").strip())
    _git(repo, ["git", "commit", "-q", "-m", COMMIT_MESSAGE], env)
    for attempt in range(1, 4):
        push = _git(repo, ["git", "push", "origin", "HEAD:main"], env, check=False)
        if push.returncode == 0:
            print("Pushed Facebook state to main.", flush=True)
            return
        print(f"Push failed ({attempt}/3); rebasing onto origin/main.", flush=True)
        print(redact(push.stderr or push.stdout or ""), flush=True)
        pull = _git(repo, ["git", "pull", "--rebase", "-q", "origin", "main"], env, check=False)
        if pull.returncode != 0:
            _git(repo, ["git", "rebase", "--abort"], env, check=False)
            raise SystemExit((pull.stderr or pull.stdout or "could not rebase facebook state").strip())
    raise SystemExit("could not push facebook state")


def _dry_line(action: Action, base: str, get) -> str:
    article = action.article
    if action.kind == "untranslated":
        return (
            f"DRY RUN skip slug={article.slug}: "
            f"no {action.lang} translation yet; not marked"
        )
    if action.kind == "stale":
        return (
            f"DRY RUN skip slug={article.slug}: "
            f"older than 3 days ({article.date.isoformat()}); would mark posted without sending"
        )
    if action.kind == "deferred":
        return f"DRY RUN defer slug={article.slug}: post cap reached; left unmarked"
    post = build_post(article, action.lang, base)
    status, body = get(post["link"])
    live = status == 200 and is_page_ready(body, action.lang, article.slug, article.titles[action.lang])
    if live:
        image = og_image_url(body)
        image_status, image_body = get(image) if image else (0, b"")
        live = image_status == 200 and is_image_ready(image_body)
    return "\n".join([
        f"DRY RUN slug={article.slug} link={post['link']} live={'yes' if live else 'no'}",
        "message:",
        post["message"],
        "---",
    ])


def _log_secrets(log, token: str, page_id: str, lang: str) -> None:
    log("FB_PAGE_TOKEN is " + ("configured" if token else "not set") + " (value not printed).")
    log("FB_PAGE_ID is " + ("configured" if page_id else "not set") + " (value not printed).")
    log(f"FB_POST_LANG={lang}")


def execute(
    articles: list[Article],
    state: dict,
    *,
    today: datetime.date,
    now: datetime.datetime,
    lang: str,
    token: str,
    page_id: str,
    dry_run: bool,
    base: str,
    max_posts: int,
    delay: float,
    max_wait: float,
    http_get,
    sleep,
    monotonic,
    send,
    probe,
    log,
    save,
) -> int:
    lang = require_lang(lang)
    planned = plan(articles, state, today, lang)
    actions = apply_cap(planned, max_posts)
    pending = sum(item.kind == "send" for item in planned)
    _log_secrets(log, token, page_id, lang)

    def report_probe() -> bool:
        if not token or not page_id:
            return True
        ok, info = probe()
        info = redact(info, token, page_id)
        if ok and page_name_ok(info):
            log(f"Facebook page name: {info}")
            return True
        if ok:
            log(f"::error title=Facebook::Page name {info!r} is not CyNews24")
            return False
        log(f"::error title=Facebook::{info}")
        return False

    if dry_run:
        reachable = report_probe() if token and page_id else True
        if not token:
            log("FB_PAGE_TOKEN is not set, so the Page was not requested.")
        elif not page_id:
            log("FB_PAGE_ID is not set, so the Page was not requested.")
        if not actions:
            log("DRY RUN nothing new to post.")
        for action in actions:
            log(_dry_line(action, base, http_get))
        log(
            "DRY RUN summary: "
            f"would send {sum(item.kind == 'send' for item in actions)}, "
            f"would mark old {sum(item.kind == 'stale' for item in actions)}, "
            f"waiting for {lang} {sum(item.kind == 'untranslated' for item in actions)}, "
            f"deferred {sum(item.kind == 'deferred' for item in actions)}. "
            "Nothing was published and the state file was not changed."
        )
        return 0 if reachable else 1

    if not token or not page_id:
        which = "FB_PAGE_TOKEN" if not token else "FB_PAGE_ID"
        log(
            f"::notice title=Facebook::{which} is not set, so nothing was posted "
            f"({pending} post(s) pending). The state file was not changed."
        )
        return 0

    deadline = monotonic() + max_wait
    failures = []
    sent = stale = 0
    dirty = False
    checked = False

    def flush() -> bool:
        nonlocal dirty
        if not dirty:
            return True
        try:
            save()
        except SystemExit as exc:
            log(f"::error title=Facebook::{redact(str(exc), token, page_id)}")
            return False
        dirty = False
        return True

    def ensure_page() -> bool:
        nonlocal checked
        if checked:
            return True
        checked = True
        return report_probe()

    for index, action in enumerate(actions):
        article = action.article
        if action.kind == "untranslated":
            log(f"skip slug={article.slug}: no {lang} translation yet")
            continue
        if action.kind == "deferred":
            log(f"defer slug={article.slug}: post cap of {max_posts} reached; left unmarked")
            continue
        if action.kind == "stale":
            mark(state, article.slug, "skipped-old", now, lang)
            dirty = True
            stale += 1
            log(
                f"mark slug={article.slug} posted without sending "
                f"(older than 3 days: {article.date.isoformat()})"
            )
            continue
        if not flush():
            return 1
        if not ensure_page():
            failures.append(f"{article.slug}: Facebook Page was not reachable")
            continue
        if not wait_until_live(
            action, base, get=http_get, sleep=sleep, monotonic=monotonic, deadline=deadline, log=log
        ):
            failures.append(f"{article.slug}: page was not live in time")
            log(f"::error title=Facebook::{failures[-1]}")
            continue
        post = build_post(article, lang, base)
        ok, info = send(post)
        info = redact(info, token, page_id)
        if not ok:
            failures.append(f"{article.slug}: {info}")
            log(f"::error title=Facebook::{failures[-1]}")
            continue
        mark(state, article.slug, "sent", now, lang)
        dirty = True
        sent += 1
        log(f"sent slug={article.slug} link={post['link']} post={info or '-'}")
        if not flush():
            return 1
        more = any(item.kind == "send" for item in actions[index + 1:])
        if more and delay:
            log(f"pause {delay:g}s")
            sleep(delay)
    if not flush():
        return 1
    waiting = sum(item.kind == "untranslated" for item in actions)
    deferred = sum(item.kind == "deferred" for item in actions)
    log(
        f"Facebook: sent {sent}, marked old {stale}, waiting for {lang} {waiting}, "
        f"deferred {deferred}, failed {len(failures)}"
    )
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post new CyNews 24 articles to the Facebook Page.")
    parser.add_argument("--dry-run", action="store_true", help="print posts without publishing or writing state")
    parser.add_argument("--articles", default=DEFAULT_ARTICLES)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--base", default=os.environ.get("BASE", "https://cynews24.net"))
    parser.add_argument("--lang", default=os.environ.get("FB_POST_LANG", DEFAULT_LANG))
    parser.add_argument("--today", default=os.environ.get("TODAY") or "")
    parser.add_argument("--max-posts", type=int, default=env_int("FB_MAX_POSTS", MAX_POSTS))
    parser.add_argument("--delay", type=float, default=env_float("FB_POST_DELAY", POST_DELAY))
    parser.add_argument("--max-wait", type=float, default=env_float("FB_MAX_WAIT", 360))
    args = parser.parse_args(argv)
    dry_run = args.dry_run or env_flag("DRY_RUN")
    lang = require_lang(args.lang)
    token = os.environ.get("FB_PAGE_TOKEN", "").strip()
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    today = datetime.date.fromisoformat(args.today) if args.today else cyprus_today()
    articles = load_articles(args.articles)
    state = load_state(args.state)
    base = args.base.rstrip("/")
    push = env_flag("PUSH_STATE") and not dry_run and bool(token) and bool(page_id)

    def save() -> None:
        save_state(args.state, state)
        if push:
            commit_and_push(ROOT, args.state)

    def send(payload: dict) -> tuple[bool, str]:
        return send_facebook(token, page_id, payload, post=http_post, sleep=time.sleep)

    def probe() -> tuple[bool, str]:
        return probe_page(page_id, token, http_get)

    return execute(
        articles,
        state,
        today=today,
        now=utcnow(),
        lang=lang,
        token=token,
        page_id=page_id,
        dry_run=dry_run,
        base=base,
        max_posts=args.max_posts,
        delay=args.delay,
        max_wait=args.max_wait,
        http_get=http_get,
        sleep=time.sleep,
        monotonic=time.monotonic,
        send=send,
        probe=probe,
        log=lambda message: print(redact(message, token, page_id), flush=True),
        save=save,
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as exc:
        if isinstance(exc.code, int):
            raise
        print(exc.code or exc, file=sys.stderr)
        sys.exit(1)
