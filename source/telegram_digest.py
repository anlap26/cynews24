# -*- coding: utf-8 -*-
"""Post one evening digest to the CyNews 24 Telegram channels.

Articles whose publication date is today in Asia/Nicosia are collected from
source/content/articles/. One HTML message goes to @cynews24 (Russian,
links under /ru/) and one to @cynews24en (English, links under /en/).
Greek is not posted. An article with no English translation is left out of
the English digest. A day with nothing to list sends nothing.

Dates already sent are stored in source/content/telegram-digest.json, per
language, so a re-run does not post the same digest again. The file is
committed back only after a successful send.

TELEGRAM_BOT_TOKEN is the repository secret. When it is missing this script
logs a notice, leaves the state file untouched and exits 0. DRY_RUN=1 (or
--dry-run) prints the messages and does not call Telegram or write state.
The token is never printed.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

import telegram_post as tg

ROOT = tg.ROOT
DEFAULT_ARTICLES = tg.DEFAULT_ARTICLES
DEFAULT_STATE = os.path.join(ROOT, "source", "content", "telegram-digest.json")

NOTE = (
    "Evening digest dates already sent to Telegram. ru is @cynews24, "
    "en is @cynews24en. A language entry for a YYYY-MM-DD date means that "
    "digest was posted and must not be sent again. An empty day is not recorded."
)

# Same month names as source/build.py, without the year, as in "14 ноября".
MONTHS = {
    "ru": [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ],
    "en": [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ],
}
HEADERS = {
    "ru": "🗞 Главное за день — {when}",
    "en": "🗞 Today in Cyprus — {when}",
}
CLOSINGS = {"ru": "Все новости", "en": "All news"}
MESSAGE_LIMIT = 4096
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
COMMIT_MESSAGE = "Telegram: отправлен вечерний дайджест"


def parse_day(value: str) -> datetime.date:
    text = value.strip()
    if not DATE_RE.fullmatch(text):
        raise SystemExit(f"bad date {value!r}; expected YYYY-MM-DD")
    try:
        return datetime.date.fromisoformat(text)
    except ValueError as exc:
        raise SystemExit(f"bad date {value!r}") from exc


def resolve_today(explicit: str) -> datetime.date:
    if explicit.strip():
        return parse_day(explicit)
    try:
        return tg.cyprus_today()
    except ValueError as exc:
        raise SystemExit(f"bad TODAY date: {exc}") from exc


def format_when(day: datetime.date, lang: str) -> str:
    return f"{day.day} {MONTHS[lang][day.month - 1]}"


def header(day: datetime.date, lang: str) -> str:
    return HEADERS[lang].format(when=format_when(day, lang))


class Item:
    """One article plus the editorial order used by the site."""

    def __init__(self, article: tg.Article, seq: int | None):
        self.article = article
        self.seq = seq


def _seq(path: str, value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise SystemExit(f"{path}: seq must be an integer")
    return value


def load_items(directory: str) -> list[Item]:
    if not os.path.isdir(directory):
        raise SystemExit(f"Articles directory not found: {directory}")
    names = sorted(name for name in os.listdir(directory) if name.endswith(".json"))
    items = []
    for name in names:
        path = os.path.join(directory, name)
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise SystemExit(f"{path}: article must be a JSON object")
        article = tg.load_article(path)
        items.append(Item(article, _seq(path, data.get("seq"))))
    slugs = [item.article.slug for item in items]
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        raise SystemExit(f"Duplicate slugs: {duplicates}")
    return items


def sort_key(item: Item):
    # Same order as source/build.py: original seq first, then newer articles.
    return (
        item.seq is None,
        item.seq if item.seq is not None else 0,
        item.article.date,
        item.article.slug,
    )


def select(items: list[Item], day: datetime.date, lang: str) -> list[Item]:
    chosen = []
    for item in items:
        if item.article.date != day:
            continue
        if lang == "en" and not item.article.translated.get("en"):
            continue
        title = " ".join((item.article.titles.get(lang) or "").split())
        if not title:
            continue
        chosen.append(item)
    return sorted(chosen, key=sort_key)


def render_digest(day: datetime.date, lang: str, items: list[Item], base: str) -> str:
    """One HTML message: header, numbered linked headlines, site link."""
    lines = [f"<b>{tg.escape_text(header(day, lang))}</b>", ""]
    root = base.rstrip("/")
    for index, item in enumerate(items, start=1):
        title = " ".join(item.article.titles[lang].split())
        url = tg.article_url(root, lang, item.article.slug)
        lines.append(f'{index}. <a href="{tg.escape_attr(url)}">{tg.escape_text(title)}</a>')
    home = f"{root}/{lang}/"
    lines.append("")
    lines.append(f'{tg.escape_text(CLOSINGS[lang])}: <a href="{tg.escape_attr(home)}">cynews24.net</a>')
    return "\n".join(lines)


def build_payload(lang: str, text: str) -> dict:
    return {
        "method": "sendMessage",
        "chat_id": tg.CHANNELS[lang],
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }


def empty_state() -> dict:
    return {"note": NOTE, "sent": {}}


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return empty_state()
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("sent"), dict):
        raise SystemExit(f"{path}: expected an object with a sent map")
    for day, entry in data["sent"].items():
        if not isinstance(day, str) or not DATE_RE.fullmatch(day):
            raise SystemExit(f"{path}: {day!r} is not a YYYY-MM-DD date")
        try:
            datetime.date.fromisoformat(day)
        except ValueError as exc:
            raise SystemExit(f"{path}: bad date {day}") from exc
        if not isinstance(entry, dict):
            raise SystemExit(f"{path}: {day} must be an object")
        for lang, record in entry.items():
            if lang not in tg.LANGS:
                raise SystemExit(f"{path}: {day} has unknown language {lang}")
            if not isinstance(record, dict) or not isinstance(record.get("status"), str) or not record["status"]:
                raise SystemExit(f"{path}: {day}.{lang} must be an object with a status")
            if not isinstance(record.get("at"), str) or not record["at"]:
                raise SystemExit(f"{path}: {day}.{lang} must include at")
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


def is_marked(state: dict, day: datetime.date, lang: str) -> bool:
    entry = state.get("sent", {}).get(day.isoformat())
    if entry is None:
        return False
    if not isinstance(entry, dict):
        raise SystemExit(f"digest state for {day.isoformat()} must be an object")
    return lang in entry


def mark(state: dict, day: datetime.date, lang: str, status: str, moment: datetime.datetime, count: int) -> None:
    entry = state.setdefault("sent", {}).setdefault(day.isoformat(), {})
    if not isinstance(entry, dict):
        raise SystemExit(f"digest state for {day.isoformat()} must be an object")
    if lang not in entry:
        entry[lang] = {"at": tg.stamp(moment), "count": count, "status": status}


def redact(text: str, token: str = "") -> str:
    text = tg.redact(text or "", token)
    text = re.sub(r"x-access-token:[^@\s]+", "x-access-token:***", text)
    text = re.sub(r"gh[ps]_[A-Za-z0-9]+", "gh*_***", text)
    return text


def _git(repo: str, args: list[str], env: dict, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=repo, env=env, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = redact((result.stderr or result.stdout or "").strip())
        shown = " ".join(args[1:] if args and args[0] == "git" else args)
        raise SystemExit(f"git {shown} failed: {detail}")
    return result


def commit_and_push(repo: str, path: str) -> None:
    """Commit only the digest state file and push it to main."""
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
        raise SystemExit(redact((diff.stderr or "git diff failed").strip()))
    _git(repo, ["git", "commit", "-q", "-m", COMMIT_MESSAGE], env)
    for attempt in range(1, 4):
        push = _git(repo, ["git", "push", "origin", "HEAD:main"], env, check=False)
        if push.returncode == 0:
            print("Pushed Telegram digest state to main.", flush=True)
            return
        print(f"Push failed ({attempt}/3); rebasing onto origin/main.", flush=True)
        print(redact((push.stderr or push.stdout or "").strip()), flush=True)
        pull = _git(repo, ["git", "pull", "--rebase", "-q", "origin", "main"], env, check=False)
        if pull.returncode != 0:
            _git(repo, ["git", "rebase", "--abort"], env, check=False)
            raise SystemExit(redact((pull.stderr or pull.stdout or "could not rebase digest state").strip()))
    raise SystemExit("could not push telegram digest state")


def _plan_one(items: list[Item], state: dict, day: datetime.date, lang: str, base: str) -> dict:
    chosen = select(items, day, lang)
    if not chosen:
        return {"lang": lang, "items": chosen, "text": None, "kind": "empty"}
    if is_marked(state, day, lang):
        return {"lang": lang, "items": chosen, "text": None, "kind": "already"}
    text = render_digest(day, lang, chosen, base)
    kind = "too_long" if len(text) > MESSAGE_LIMIT else "send"
    return {"lang": lang, "items": chosen, "text": text, "kind": kind}


def plan(items: list[Item], state: dict, day: datetime.date, base: str) -> list[dict]:
    return [_plan_one(items, state, day, lang, base) for lang in tg.LANGS]


def _dry_block(entry: dict, day: datetime.date) -> str:
    lang = entry["lang"]
    channel = tg.CHANNELS[lang]
    count = len(entry["items"])
    if entry["kind"] == "empty":
        return f"DRY RUN skip {channel} date={day.isoformat()}: no articles; nothing to post"
    if entry["kind"] == "already":
        return (
            f"DRY RUN skip {channel} date={day.isoformat()}: "
            f"already sent ({count} headlines); would not post again"
        )
    if entry["kind"] == "too_long":
        return (
            f"DRY RUN skip {channel} date={day.isoformat()}: "
            f"message is {len(entry['text'])} characters, over the {MESSAGE_LIMIT} limit; would not send"
        )
    lines = [
        f"DRY RUN {channel} sendMessage date={day.isoformat()} items={count} link_preview=disabled",
        "text:",
        entry["text"],
        "---",
    ]
    return "\n".join(lines)


def execute(
    items: list[Item],
    state: dict,
    *,
    today: datetime.date,
    now: datetime.datetime,
    token: str,
    dry_run: bool,
    base: str,
    send,
    sleep,
    log,
    save,
) -> int:
    log(
        "TELEGRAM_BOT_TOKEN is "
        + ("configured" if token else "not set")
        + " (value not printed)."
    )
    log(f"Digest date: {today.isoformat()} (Asia/Nicosia)")
    planned = plan(items, state, today, base)
    if dry_run:
        for entry in planned:
            log(_dry_block(entry, today))
        would = sum(entry["kind"] == "send" for entry in planned)
        already = sum(entry["kind"] == "already" for entry in planned)
        empty = sum(entry["kind"] == "empty" for entry in planned)
        too_long = sum(entry["kind"] == "too_long" for entry in planned)
        log(
            "DRY RUN summary: "
            f"would send {would}, already sent {already}, nothing to list {empty}, "
            f"too long {too_long}. "
            "Nothing was sent and the state file was not changed."
        )
        return 0

    actionable = [entry for entry in planned if entry["kind"] in {"send", "too_long"}]
    if not actionable:
        for entry in planned:
            channel = tg.CHANNELS[entry["lang"]]
            if entry["kind"] == "empty":
                log(f"skip {channel} date={today.isoformat()}: no articles; nothing to post")
            else:
                log(f"skip {channel} date={today.isoformat()}: already sent; not posting again")
        return 0

    if not token:
        pending = sum(entry["kind"] == "send" for entry in planned)
        if pending:
            log(
                "::notice title=Telegram digest::TELEGRAM_BOT_TOKEN is not set, so nothing was posted "
                f"({pending} digest(s) pending). The state file was not changed."
            )
        too_long = [entry for entry in planned if entry["kind"] == "too_long"]
        for entry in too_long:
            log(
                "::error title=Telegram digest::"
                f"{today.isoformat()} {entry['lang']}: message is {len(entry['text'])} characters"
            )
        return 1 if too_long else 0

    failures = []
    sent = 0
    dirty = False

    def flush() -> bool:
        nonlocal dirty
        if not dirty:
            return True
        try:
            save()
        except SystemExit as exc:
            log(f"::error title=Telegram digest::{redact(str(exc), token)}")
            return False
        dirty = False
        return True

    for entry in planned:
        channel = tg.CHANNELS[entry["lang"]]
        if entry["kind"] == "empty":
            log(f"skip {channel} date={today.isoformat()}: no articles; nothing to post")
            continue
        if entry["kind"] == "already":
            log(f"skip {channel} date={today.isoformat()}: already sent; not posting again")
            continue
        if entry["kind"] == "too_long":
            failures.append(
                f"{today.isoformat()} {entry['lang']}: message is {len(entry['text'])} characters"
            )
            log(f"::error title=Telegram digest::{failures[-1]}")
            continue
        if not flush():
            return 1
        payload = build_payload(entry["lang"], entry["text"])
        ok, info = send(payload)
        if not ok:
            failures.append(f"{today.isoformat()} {entry['lang']}: {redact(info, token)}")
            log(f"::error title=Telegram digest::{failures[-1]}")
            continue
        mark(state, today, entry["lang"], "sent", now, len(entry["items"]))
        dirty = True
        sent += 1
        log(
            f"sent {payload['chat_id']} sendMessage date={today.isoformat()} "
            f"items={len(entry['items'])} message_id={info or '-'}"
        )
        if not flush():
            return 1
        sleep(1)
    if not flush():
        return 1
    log(f"Telegram digest: sent {sent}, failed {len(failures)}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post the CyNews 24 evening Telegram digest.")
    parser.add_argument("--dry-run", action="store_true", help="print the digest without sending or writing state")
    parser.add_argument("--articles", default=DEFAULT_ARTICLES)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--base", default=os.environ.get("BASE", "https://cynews24.net"))
    parser.add_argument("--today", default=os.environ.get("TODAY") or "")
    args = parser.parse_args(argv)
    dry_run = args.dry_run or tg.env_flag("DRY_RUN")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    today = resolve_today(args.today)
    items = load_items(args.articles)
    state = load_state(args.state)
    base = args.base.rstrip("/")
    push = tg.env_flag("PUSH_STATE") and not dry_run and bool(token)

    def save() -> None:
        save_state(args.state, state)
        if push:
            commit_and_push(ROOT, args.state)

    def send(payload: dict) -> tuple[bool, str]:
        return tg.send_telegram(token, payload, post=tg.http_post, sleep=tg.time.sleep)

    return execute(
        items,
        state,
        today=today,
        now=tg.utcnow(),
        token=token,
        dry_run=dry_run,
        base=base,
        send=send,
        sleep=tg.time.sleep,
        log=lambda message: print(redact(message, token), flush=True),
        save=save,
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as exc:
        if isinstance(exc.code, int):
            raise
        print(redact(str(exc.code or exc)), file=sys.stderr)
        sys.exit(1)
