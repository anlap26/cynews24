# -*- coding: utf-8 -*-
"""Post new CyNews 24 articles to Telegram after the pages are live.

Russian goes to @cynews24 and links to /ru/<slug>/. English goes to
@cynews24en and links to /en/<slug>/. English is skipped until the article
has its own English title, lede and body, then posted once.

Slugs already handled are stored in source/content/telegram-posted.json.
Editing an article does not post it again. An article (or a late English
translation) first seen more than 3 days after its publication date is
recorded without sending, so enabling the bot later cannot flood the channels.

TELEGRAM_BOT_TOKEN is the repository secret. When it is missing this script
logs a notice, leaves the state file untouched and exits 0. DRY_RUN=1 (or
--dry-run) prints the messages and does not call Telegram or write state.
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
import urllib.request
from dataclasses import dataclass
from zoneinfo import ZoneInfo

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_ARTICLES = os.path.join(ROOT, "source", "content", "articles")
DEFAULT_STATE = os.path.join(ROOT, "source", "content", "telegram-posted.json")

NOTE = (
    "Slugs already handled for Telegram. ru is @cynews24 (link /ru/), "
    "en is @cynews24en (link /en/). A language entry means do not post again. "
    "Missing en means the English text was not posted yet."
)

CHANNELS = {"ru": "@cynews24", "en": "@cynews24en"}
READ_MORE = {"ru": "Читать полностью", "en": "Read more"}
LANGS = ("ru", "en")
CATS = ("politics", "economy", "real-estate", "society", "tourism", "sport", "world")
HASHTAGS = {
    "ru": {
        "politics": "#Политика",
        "economy": "#Экономика",
        "real-estate": "#Недвижимость",
        "society": "#Общество",
        "tourism": "#Туризм",
        "sport": "#Спорт",
        "world": "#ВМире",
    },
    "en": {
        "politics": "#Politics",
        "economy": "#Economy",
        "real-estate": "#RealEstate",
        "society": "#Society",
        "tourism": "#Tourism",
        "sport": "#Sport",
        "world": "#World",
    },
}
COUNTRY = {"ru": "#Кипр", "en": "#Cyprus"}
CAPTION_LIMIT = 1024
# Keep in sync with source/build.py so page addresses match the site.
_TR = dict(zip("абвгдеёзийклмнопрстуфхыэ", "abvgdeezijklmnoprstufhye")) | {
    "ж": "zh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ю": "yu", "я": "ya", "ъ": "", "ь": "",
}
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
USER_AGENT = "cynews24-telegram-poster"
COMMIT_MESSAGE = "Telegram: отмечены отправленные статьи"


def slugify(value) -> str:
    text = "".join(_TR.get(ch, ch) for ch in str(value).lower())
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text)).strip("-")[:70].strip("-")


def _clean(value):
    if value is None:
        return ""
    return value.strip() if isinstance(value, str) else value


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


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


def escape_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_attr(value: str) -> str:
    return escape_text(value).replace('"', "&quot;")


def article_url(base: str, lang: str, slug: str) -> str:
    return f"{base.rstrip('/')}/{lang}/{slug}/"


def image_url(base: str, key: str) -> str:
    return f"{base.rstrip('/')}/assets/img/{key}-og.jpg"


def hashtags(lang: str, cat: str) -> str:
    return f"{HASHTAGS[lang][cat]} {COUNTRY[lang]}"


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


def visible_text(title: str, lede: str, link_text: str, tags: str) -> str:
    parts = []
    if title:
        parts.append(title)
    if lede:
        parts.append(lede)
    parts.append(link_text)
    parts.append(tags)
    return "\n\n".join(parts)


def render_caption(title: str, lede: str, url: str, link_text: str, tags: str) -> str:
    """HTML caption/text. Visible length (after tag parsing) stays within 1024."""
    title = " ".join((title or "").split())
    lede = " ".join((lede or "").split())
    link_text = " ".join((link_text or "").split())
    tags = " ".join((tags or "").split())

    def pack(title_text: str, lede_text: str) -> int:
        return len(visible_text(title_text, lede_text, link_text, tags))

    if pack(title, lede) > CAPTION_LIMIT:
        without_lede = pack(title, "")
        spare = CAPTION_LIMIT - without_lede - 2
        if spare >= 1 and lede:
            lede = clip(lede, spare)
        else:
            lede = ""
        if pack(title, lede) > CAPTION_LIMIT:
            lede = ""
            spare_title = CAPTION_LIMIT - (pack("", "") + 2)
            title = clip(title, max(spare_title, 1))
            while pack(title, "") > CAPTION_LIMIT and len(title) > 1:
                title = clip(title, len(title) - 1)
    if pack(title, lede) > CAPTION_LIMIT:
        raise RuntimeError("Telegram caption still exceeds 1024 characters")

    blocks = []
    if title:
        blocks.append(f"<b>{escape_text(title)}</b>")
    if lede:
        blocks.append(escape_text(lede))
    blocks.append(f'<a href="{escape_attr(url)}">{escape_text(link_text)}</a>')
    if tags:
        blocks.append(escape_text(tags))
    return "\n\n".join(blocks)


def visible_length(caption_html: str) -> int:
    text = re.sub(r"<[^>]+>", "", caption_html)
    return len(html.unescape(text))


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
    kind: str  # send, stale, untranslated
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
    en = data.get("en") if isinstance(data.get("en"), dict) else {}
    titles = {"ru": _text(ru, "title"), "en": _text(en, "title")}
    ledes = {"ru": _text(ru, "lede"), "en": _text(en, "lede")}
    translated = {"ru": True, "en": _translated(en)}
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
    for slug, entry in data["posted"].items():
        if not isinstance(slug, str) or not isinstance(entry, dict):
            raise SystemExit(f"{path}: {slug} must be an object")
        for lang, record in entry.items():
            if lang not in LANGS:
                raise SystemExit(f"{path}: {slug} has unknown language {lang}")
            if not isinstance(record, dict) or not isinstance(record.get("status"), str) or not record["status"]:
                raise SystemExit(f"{path}: {slug}.{lang} must be an object with a status")
            if not isinstance(record.get("at"), str) or not record["at"]:
                raise SystemExit(f"{path}: {slug}.{lang} must include at")
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


def is_marked(state: dict, slug: str, lang: str) -> bool:
    entry = state.get("posted", {}).get(slug)
    if entry is None:
        return False
    if not isinstance(entry, dict):
        raise SystemExit(f"telegram state for {slug} must be an object")
    return lang in entry


def mark(state: dict, slug: str, lang: str, status: str, moment: datetime.datetime) -> None:
    entry = state.setdefault("posted", {}).setdefault(slug, {})
    if not isinstance(entry, dict):
        raise SystemExit(f"telegram state for {slug} must be an object")
    if lang not in entry:
        entry[lang] = {"at": stamp(moment), "status": status}


def initial_seed(articles: list[Article]) -> dict:
    """Mark every current article handled, so the first real run posts nothing old."""
    posted = {}
    for article in sorted(articles, key=lambda item: item.slug):
        entry = {}
        for lang in LANGS:
            if lang == "en" and not article.translated["en"]:
                continue
            entry[lang] = {"at": article.date.isoformat() + "T00:00:00Z", "status": "seeded"}
        posted[article.slug] = entry
    return {"note": NOTE, "posted": posted}


def plan(articles: list[Article], state: dict, today: datetime.date) -> list[Action]:
    actions = []
    ordered = sorted(articles, key=lambda article: (article.date, article.slug))
    for article in ordered:
        for lang in LANGS:
            if is_marked(state, article.slug, lang):
                continue
            if lang == "en" and not article.translated["en"]:
                actions.append(Action("untranslated", lang, article))
                continue
            kind = "stale" if older_than_three_days(article.date, today) else "send"
            actions.append(Action(kind, lang, article))
    return actions


def build_post(article: Article, lang: str, base: str) -> dict:
    url = article_url(base, lang, article.slug)
    caption = render_caption(
        article.titles[lang],
        article.ledes[lang],
        url,
        READ_MORE[lang],
        hashtags(lang, article.cat),
    )
    post = {
        "method": "sendPhoto" if article.image_key else "sendMessage",
        "chat_id": CHANNELS[lang],
        "parse_mode": "HTML",
        "url": url,
    }
    if article.image_key:
        post["photo"] = image_url(base, article.image_key)
        post["caption"] = caption
    else:
        post["text"] = caption
        post["link_preview_options"] = {"is_disabled": False, "url": url}
    return post


def is_page_ready(body: bytes, lang: str, slug: str, title: str) -> bool:
    text = body.decode("utf-8", errors="replace")
    if f"/{lang}/{slug}/" not in text:
        return False
    if 'name="robots" content="noindex' in text:
        return False
    return title in html.unescape(text)


def is_image_ready(body: bytes) -> bool:
    return len(body) >= 100 and body.startswith(b"\xff\xd8")


def http_get(url: str, timeout: float = 20) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Accept": "*/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return exc.code, body
    except Exception:
        return 0, b""


def http_post(url: str, data: bytes, timeout: float = 30) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return exc.code, body
    except Exception as exc:
        return 0, str(exc).encode("utf-8", errors="replace")


def redact(text: str, token: str) -> str:
    if token and token in text:
        text = text.replace(token, "***")
    return text


def parse_telegram(status: int, raw: bytes) -> tuple[bool, str, int | None]:
    try:
        data = json.loads(raw.decode("utf-8", errors="replace") or "{}")
    except json.JSONDecodeError:
        return False, f"HTTP {status}", None
    if data.get("ok"):
        message_id = (data.get("result") or {}).get("message_id")
        return True, "" if message_id is None else str(message_id), None
    retry = (data.get("parameters") or {}).get("retry_after")
    try:
        retry_after = int(retry) if retry is not None else None
    except (TypeError, ValueError):
        retry_after = None
    description = data.get("description") or f"HTTP {status}"
    return False, str(description), retry_after


def send_telegram(token: str, payload: dict, *, post, sleep, attempts: int = 4) -> tuple[bool, str]:
    method = payload["method"]
    body = {key: value for key, value in payload.items() if key not in {"method", "url"}}
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last = "no response"
    for attempt in range(attempts):
        try:
            status, raw = post(url, data)
        except Exception as exc:
            last = redact(str(exc), token)
            if attempt == attempts - 1:
                return False, last
            sleep(2)
            continue
        ok, info, retry_after = parse_telegram(status, raw)
        if ok:
            return True, info
        last = redact(info, token)
        transient = status in {0, 429, 500, 502, 503, 504}
        if not transient or attempt == attempts - 1:
            return False, last
        sleep(retry_after if retry_after is not None else 2)
    return False, last


def wait_until_live(action: Action, base: str, *, get, sleep, monotonic, deadline, log) -> bool:
    post = build_post(action.article, action.lang, base)
    checks = [(post["url"], lambda body: is_page_ready(body, action.lang, action.article.slug, action.article.titles[action.lang]))]
    if action.article.image_key:
        checks.append((post["photo"], is_image_ready))
    waits = (15, 30, 45, 60)
    attempt = 0
    while True:
        ready = True
        for url, check in checks:
            status, body = get(url)
            if status != 200 or not check(body):
                log(f"waiting for {url} (HTTP {status})")
                ready = False
                break
        if ready:
            log(f"live {post['url']}")
            return True
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
    _git(repo, ["git", "config", "user.name", "cynews24-telegram[bot]"], env)
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
            print("Pushed Telegram state to main.", flush=True)
            return
        print(f"Push failed ({attempt}/3); rebasing onto origin/main.", flush=True)
        print((push.stderr or push.stdout or "").strip(), flush=True)
        pull = _git(repo, ["git", "pull", "--rebase", "-q", "origin", "main"], env, check=False)
        if pull.returncode != 0:
            _git(repo, ["git", "rebase", "--abort"], env, check=False)
            raise SystemExit((pull.stderr or pull.stdout or "could not rebase telegram state").strip())
    raise SystemExit("could not push telegram state")


def _dry_line(action: Action, base: str, get) -> str:
    article = action.article
    if action.kind == "untranslated":
        return (
            f"DRY RUN skip {CHANNELS['en']} slug={article.slug}: "
            "no English translation yet; not marked"
        )
    if action.kind == "stale":
        return (
            f"DRY RUN skip {CHANNELS[action.lang]} slug={article.slug}: "
            f"older than 3 days ({article.date.isoformat()}); would mark posted without sending"
        )
    post = build_post(article, action.lang, base)
    status, body = get(post["url"])
    live = status == 200 and is_page_ready(body, action.lang, article.slug, article.titles[action.lang])
    if live and article.image_key:
        image_status, image_body = get(post["photo"])
        live = image_status == 200 and is_image_ready(image_body)
    lines = [f"DRY RUN {post['chat_id']} {post['method']} slug={article.slug} live={'yes' if live else 'no'}"]
    if post["method"] == "sendPhoto":
        lines.append(f"photo: {post['photo']}")
        lines.append("caption:")
        lines.append(post["caption"])
    else:
        lines.append(f"link_preview: {post['link_preview_options']['url']}")
        lines.append("text:")
        lines.append(post["text"])
    lines.append("---")
    return "\n".join(lines)


def execute(
    articles: list[Article],
    state: dict,
    *,
    today: datetime.date,
    now: datetime.datetime,
    token: str,
    dry_run: bool,
    base: str,
    max_wait: float,
    http_get,
    sleep,
    monotonic,
    send,
    log,
    save,
) -> int:
    actions = plan(articles, state, today)
    if dry_run:
        if not actions:
            log("DRY RUN nothing new to post.")
        for action in actions:
            log(_dry_line(action, base, http_get))
        log(
            "DRY RUN summary: "
            f"would send {sum(item.kind == 'send' for item in actions)}, "
            f"would mark old {sum(item.kind == 'stale' for item in actions)}, "
            f"waiting for English {sum(item.kind == 'untranslated' for item in actions)}. "
            "Nothing was sent and the state file was not changed."
        )
        return 0
    if not token:
        pending = sum(item.kind == "send" for item in actions)
        log(
            "::notice title=Telegram::TELEGRAM_BOT_TOKEN is not set, so nothing was posted "
            f"({pending} post(s) pending). The state file was not changed."
        )
        return 0

    deadline = monotonic() + max_wait
    failures = []
    sent = stale = 0
    dirty = False

    def flush() -> bool:
        nonlocal dirty
        if not dirty:
            return True
        try:
            save()
        except SystemExit as exc:
            log(f"::error title=Telegram::{exc}")
            return False
        dirty = False
        return True

    for action in actions:
        article = action.article
        if action.kind == "untranslated":
            log(f"skip {CHANNELS['en']} slug={article.slug}: no English translation yet")
            continue
        if action.kind == "stale":
            mark(state, article.slug, action.lang, "skipped-old", now)
            dirty = True
            stale += 1
            log(
                f"mark {CHANNELS[action.lang]} slug={article.slug} posted without sending "
                f"(older than 3 days: {article.date.isoformat()})"
            )
            continue
        if not flush():
            return 1
        if not wait_until_live(
            action, base, get=http_get, sleep=sleep, monotonic=monotonic, deadline=deadline, log=log
        ):
            failures.append(f"{article.slug} {action.lang}: page was not live in time")
            log(f"::error title=Telegram::{failures[-1]}")
            continue
        post = build_post(article, action.lang, base)
        ok, info = send(post)
        if not ok:
            failures.append(f"{article.slug} {action.lang}: {info}")
            log(f"::error title=Telegram::{failures[-1]}")
            continue
        mark(state, article.slug, action.lang, "sent", now)
        dirty = True
        sent += 1
        log(f"sent {post['chat_id']} {post['method']} slug={article.slug} message_id={info or '-'}")
        if not flush():
            return 1
        sleep(1)
    if not flush():
        return 1
    waiting = sum(item.kind == "untranslated" for item in actions)
    log(f"Telegram: sent {sent}, marked old {stale}, waiting for English {waiting}, failed {len(failures)}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post new CyNews 24 articles to Telegram.")
    parser.add_argument("--dry-run", action="store_true", help="print messages without sending or writing state")
    parser.add_argument("--articles", default=DEFAULT_ARTICLES)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--base", default=os.environ.get("BASE", "https://cynews24.net"))
    parser.add_argument("--today", default=os.environ.get("TODAY") or "")
    parser.add_argument("--max-wait", type=float, default=float(os.environ.get("TELEGRAM_MAX_WAIT", "360")))
    args = parser.parse_args(argv)
    dry_run = args.dry_run or env_flag("DRY_RUN")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    today = datetime.date.fromisoformat(args.today) if args.today else cyprus_today()
    articles = load_articles(args.articles)
    state = load_state(args.state)
    base = args.base.rstrip("/")
    push = env_flag("PUSH_STATE") and not dry_run and bool(token)

    def save() -> None:
        save_state(args.state, state)
        if push:
            commit_and_push(ROOT, args.state)

    def send(payload: dict) -> tuple[bool, str]:
        return send_telegram(token, payload, post=http_post, sleep=time.sleep)

    return execute(
        articles,
        state,
        today=today,
        now=utcnow(),
        token=token,
        dry_run=dry_run,
        base=base,
        max_wait=args.max_wait,
        http_get=http_get,
        sleep=time.sleep,
        monotonic=time.monotonic,
        send=send,
        log=lambda message: print(message, flush=True),
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
