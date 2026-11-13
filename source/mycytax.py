# -*- coding: utf-8 -*-
"""Cross-links to the sister site MyCyTax (Cyprus tax and property guides).

The live URL layout, checked against https://mycytax.com and its sitemap, is:

- English pages are at the domain root (https://mycytax.com/guides/...), not /en/.
- Russian pages are under /ru/.
- Greek pages are under /el/.

The catalog is read from the sitemap at build time. A timeout or any other
fetch failure uses the committed fallback so a build still finishes.
"""
from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK_PATH = os.path.join(HERE, "mycytax_fallback.json")
SITEMAP_URL = "https://mycytax.com/sitemap.xml"
ORIGIN = "https://mycytax.com"
LANGS = ("ru", "en", "el")
# English is unprefixed. /en/ is accepted if the sitemap ever grows one, and is
# stripped so links stay on the root layout the site uses today.
_PREFIXES = ("ru", "el", "en")

PROJECTS_HEADING = {
    "ru": "Наши проекты",
    "en": "Our projects",
    "el": "Τα έργα μας",
}
SITE_LABEL = {
    "ru": "MyCyTax — налоги и недвижимость на Кипре",
    "en": "MyCyTax — Cyprus tax & property",
    "el": "MyCyTax — φόροι και ακίνητα στην Κύπρο",
}
USEFUL_HEADING = {
    "ru": "Полезно: гайды и калькуляторы MyCyTax",
    "en": "Useful: MyCyTax guides and calculators",
    "el": "Χρήσιμο: οδηγοί και υπολογιστές MyCyTax",
}

# When a topic matches but fewer than two catalog pages score, fill the box
# from this list so a related article still gets two or three links.
TOPIC_DEFAULTS = {
    "tax": ["taxes-overview", "selling-and-taxes", "tax-residency"],
    "vat": ["vat", "off-plan", "taxes-overview"],
    "property": ["title-deeds", "buying-as-a-foreigner", "total-cost"],
    "salary": ["tax-residency", "non-dom", "taxes-overview"],
    "pension": ["tax-residency", "non-dom", "taxes-overview"],
    "social": ["tax-residency", "non-dom", "taxes-overview"],
    "residency": ["tax-residency", "residence-permit", "non-dom"],
    "rent": ["renting-out", "rental-yield", "taxes-overview"],
    "mortgage": ["mortgage", "transfer-fees", "title-deeds"],
    "purchase": ["total-cost", "transfer-fees", "stamp-duty"],
    "sale": ["selling-and-taxes", "capital-gains", "title-deeds"],
}

# Keyword patterns are matched against a case-folded, accent-stripped string.
# Stems use a trailing word boundary so "tax" does not match "taxi" and "rent"
# does not match "current".
_RAW_KEYWORDS = {
    "en": {
        "tax": [r"\btax(?:es|ation|able|ed|ing)?\b", r"\bstamp dut(?:y|ies)\b", r"\bcapital gains?\b", r"\bincome tax\b"],
        "vat": [r"\bvat\b"],
        "property": [r"\breal estate\b", r"\btitle deeds?\b", r"\bland registry\b"],
        "salary": [r"\bsalar(?:y|ies)\b", r"\bwages?\b", r"\bpayroll\b"],
        "pension": [r"\bpensions?\b", r"\bpensioners?\b", r"\bprovident funds?\b"],
        "social": [r"\bsocial insurance\b", r"\bsocial security\b", r"\bnational insurance\b", r"\bsocial contributions?\b"],
        "residency": [r"\bresidency\b", r"\bresidence permits?\b", r"\btax residents?\b", r"\bpermanent residence\b", r"\bnon-?dom\b"],
        "rent": [r"\brents?\b", r"\brental\b", r"\brenting\b", r"\btenants?\b", r"\blandlords?\b"],
        "mortgage": [r"\bmortgages?\b", r"\bmortgaged\b"],
        "purchase": [r"\bbuying property\b", r"\bproperty purchase\b", r"\boff-plan\b", r"\boff plan\b"],
        "sale": [r"\bselling property\b", r"\bproperty sale\b", r"\bsale of (?:a |the )?property\b"],
    },
    "ru": {
        "tax": [r"\bналог\w*\b", r"\bндс\b", r"\bпошлин\w*\b", r"\bгербов\w*\b", r"\bподоходн\w*\b"],
        "vat": [r"\bндс\b"],
        "property": [r"\bнедвижимост\w*\b", r"\bквартир\w*\b", r"\bжиль[её]\w*\b", r"\bжилищн\w*\b", r"\bкадастр\w*\b", r"\bтитул\w*\b", r"\bзастройщик\w*\b", r"\bновострой\w*\b"],
        "salary": [r"\bзарплат\w*\b", r"\bоклад\w*\b"],
        "pension": [r"\bпенси\w*\b", r"\bпровидент\w*\b"],
        "social": [r"\bсоцстрах\w*\b", r"социальн\w{0,12}\s+страхов\w*", r"социальн\w{0,12}\s+взнос\w*", r"страхов\w{0,12}\s+взнос\w*", r"социальн\w{0,12}\s+обеспечен\w*"],
        "residency": [r"\bрезидент\w*\b", r"\bвнж\b", r"\bпмж\b", r"вид на жительство", r"разрешени\w*\s+на\s+проживан\w*", r"\bnon-?dom\b"],
        "rent": [r"\bаренд\w*\b", r"\bсъ[её]м\w*\b"],
        "mortgage": [r"\bипотек\w*\b", r"\bипотечн\w*\b"],
        "purchase": [r"покупк\w*\s+недвижимост\w*", r"\bдолев\w*\s+строительств\w*"],
        "sale": [r"продаж\w*\s+недвижимост\w*", r"купл[ия]-продаж\w*"],
    },
    "el": {
        "tax": [r"\bφορο(?:σ|υ|ι|ν|ουσ)?\b", r"\bφοροι\b", r"\bφορων\b", r"\bφορουσ\b", r"\bφορολογ\w*\b", r"\bχαρτοσημ\w*\b"],
        "vat": [r"\bφπα\b"],
        "property": [r"\bακινητ\w*\b", r"\bκτηματολογ\w*\b", r"τιτλ\w*\s+ιδιοκτησ\w*", r"\bκατοικι\w*\b", r"\bσπιτ\w*\b", r"\bδιαμερισμα\w*\b"],
        "salary": [r"\bμισθ(?:οσ|ου|ο|οι|ων|ουσ)\b", r"\bμισθολογ\w*\b"],
        "pension": [r"\bσυνταξ\w*\b", r"\bσυνταξιοδοτ\w*\b", r"\bσυνταξιουχ\w*\b"],
        "social": [r"κοινωνικ\w*\s+ασφαλ\w*", r"ασφαλιστικ\w*\s+εισφορ\w*"],
        "residency": [r"αδεια διαμον\w*", r"αδεια παραμον\w*", r"φορολογικ\w*\s+κατοικ\w*", r"μονιμ\w*\s+διαμον\w*", r"\bnon-?dom\b"],
        "rent": [r"\bενοικ\w*\b", r"\bμισθωσ\w*\b"],
        "mortgage": [r"\bυποθηκ\w*\b", r"\bστεγαστικ\w*\b"],
        "purchase": [r"αγορ\w*\s+ακινητ\w*"],
        "sale": [r"πωλησ\w*\s+ακινητ\w*"],
    },
}

_ACCENTS = str.maketrans({
    "ά": "α", "έ": "ε", "ή": "η", "ί": "ι", "ό": "ο", "ύ": "υ", "ώ": "ω",
    "ϊ": "ι", "ϋ": "υ", "ΐ": "ι", "ΰ": "υ", "ς": "σ",
    "ё": "е",
})


def _compile(table):
    compiled = {}
    for lang, topics in table.items():
        compiled[lang] = {topic: [re.compile(pat) for pat in pats] for topic, pats in topics.items()}
    return compiled


# Broad English words. They count in the title and tags, not in a single body mention,
# and a few set phrases (intellectual property, a department name) are removed first.
_WEAK_RAW = {
    "en": {
        "property": [r"\bpropert(?:y|ies)\b", r"\bhousing\b"],
    },
}

KEYWORDS = _compile(_RAW_KEYWORDS)
WEAK_KEYWORDS = _compile(_WEAK_RAW)


def _searchable(text, lang, topic):
    text = normalize(text)
    if lang == "en":
        text = re.sub(r"\bintellectual property\b", " ", text)
        text = re.sub(r"\btown planning and housing\b", " ", text)
        text = re.sub(r"\bhousing department\b", " ", text)
    if lang == "el" and topic == "property":
        # "φορολογική κατοικία" is tax residency, not a house.
        text = re.sub(r"φορολογικ\w*\s+κατοικ\w*", " ", text)
    return text


def _hits(patterns, text):
    return any(pat.search(text) for pat in patterns)


def normalize(text):
    return (text or "").casefold().translate(_ACCENTS)


class Page:
    def __init__(self, id, kind, path, topics, title):
        self.id = id
        self.kind = kind
        self.path = path if path.endswith("/") else path + "/"
        self.topics = {str(k): int(v) for k, v in (topics or {}).items()}
        self.title = {lang: (title or {}).get(lang) or "" for lang in LANGS}

    def label(self, lang):
        return self.title.get(lang) or self.title.get("en") or self.id.replace("-", " ")


class Catalog:
    def __init__(self, pages, origin=ORIGIN, source="fallback"):
        self.pages = list(pages)
        self.origin = origin.rstrip("/")
        self.source = source
        self.by_id = {page.id: page for page in self.pages}

    def home(self, lang):
        if lang == "ru":
            return self.origin + "/ru/"
        if lang == "el":
            return self.origin + "/el/"
        return self.origin + "/"

    def url(self, lang, page):
        path = page.path
        if lang == "ru":
            return self.origin + "/ru" + path
        if lang == "el":
            return self.origin + "/el" + path
        return self.origin + path


def _page_from_obj(obj):
    return Page(obj["id"], obj.get("kind") or "guide", obj["path"], obj.get("topics") or {}, obj.get("title") or {})


def load_fallback(path=FALLBACK_PATH):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    origin = (data.get("origin") or ORIGIN).rstrip("/")
    pages = [_page_from_obj(obj) for obj in data.get("pages") or []]
    return Catalog(pages, origin=origin, source="fallback")


def _leaf_path(path):
    """Guide or calculator page, not the section index and not about/privacy."""
    parts = [part for part in path.split("/") if part]
    return len(parts) == 2 and parts[0] in ("guides", "calculators")


def split_url(url):
    path = urlparse(url).path or "/"
    if not path.endswith("/"):
        path += "/"
    parts = [part for part in path.split("/") if part]
    if parts and parts[0] in _PREFIXES:
        rest = "/" + "/".join(parts[1:]) + "/" if len(parts) > 1 else "/"
        return parts[0], rest
    return "en", path


def parse_sitemap(xml):
    """Return canonical leaf paths found in a MyCyTax sitemap."""
    found = []
    seen = set()
    for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml or ""):
        if not (loc.startswith(ORIGIN + "/") or loc.rstrip("/") == ORIGIN):
            continue
        _lang, path = split_url(loc)
        if not _leaf_path(path) or path in seen:
            continue
        seen.add(path)
        found.append(path)
    return found


def _humanize(path):
    slug = [part for part in path.split("/") if part][-1]
    return slug.replace("-", " ").capitalize()


def _infer_topics(path):
    tokens = set(re.split(r"[^a-z0-9]+", path.lower()))
    weights = {}

    def add(topic, weight):
        weights[topic] = max(weights.get(topic, 0), weight)

    mapping = {
        "vat": {"vat": 5, "tax": 1},
        "mortgage": {"mortgage": 5, "property": 1},
        "rental": {"rent": 5, "property": 1},
        "rent": {"rent": 4},
        "renting": {"rent": 5, "property": 1},
        "tax": {"tax": 4},
        "taxes": {"tax": 4},
        "residency": {"residency": 5, "tax": 2},
        "residence": {"residency": 4},
        "stamp": {"tax": 3, "purchase": 2},
        "property": {"property": 3},
        "title": {"property": 3},
        "selling": {"sale": 4, "property": 2},
        "buying": {"purchase": 3, "property": 2},
        "pension": {"pension": 5},
        "salary": {"salary": 5},
        "wage": {"salary": 4},
        "wages": {"salary": 4},
    }
    if "off" in tokens and "plan" in tokens:
        add("property", 3)
        add("vat", 3)
        add("purchase", 3)
    if "capital" in tokens or "gains" in tokens:
        add("tax", 3)
        add("sale", 3)
    if "social" in tokens and ("insurance" in tokens or "contributions" in tokens):
        add("social", 5)
    if "non" in tokens and "dom" in tokens:
        add("residency", 4)
        add("tax", 3)
    for token in tokens:
        for topic, weight in mapping.get(token, {}).items():
            add(topic, weight)
    return weights or {"tax": 1, "property": 1}


def _synthesize(path):
    slug = [part for part in path.split("/") if part][-1]
    kind = "calculator" if path.startswith("/calculators/") else "guide"
    label = _humanize(path)
    return Page(slug, kind, path, _infer_topics(path), {lang: label for lang in LANGS})


def merge_sitemap(fallback, paths):
    """Keep fallback pages that are still listed, and add new leaf URLs."""
    if not paths:
        return fallback
    live = set(paths)
    pages = [page for page in fallback.pages if page.path in live]
    known = {page.path for page in pages}
    for path in paths:
        if path not in known:
            pages.append(_synthesize(path))
    return Catalog(pages, origin=fallback.origin, source="sitemap")


def fetch_sitemap(url=SITEMAP_URL, timeout=8, opener=None):
    opener = opener or urllib.request.urlopen
    request = urllib.request.Request(url, headers={"User-Agent": "cynews24-build/1.0"})
    with opener(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        payload = response.read(1_000_000)
    if status and int(status) >= 400:
        raise urllib.error.HTTPError(url, int(status), "sitemap request failed", hdrs=None, fp=None)
    return payload.decode("utf-8", "replace")


def load_catalog(path=FALLBACK_PATH, timeout=None, opener=None, use_network=True, sitemap_url=SITEMAP_URL):
    """Sitemap first. Any failure, including a timeout, returns the fallback."""
    fallback = load_fallback(path)
    if not use_network:
        return fallback
    if timeout is None:
        timeout = float(os.environ.get("MYCYTAX_TIMEOUT", "8"))
    try:
        xml = fetch_sitemap(sitemap_url, timeout=timeout, opener=opener)
        paths = parse_sitemap(xml)
        if not paths:
            raise ValueError("sitemap listed no guides or calculators")
        catalog = merge_sitemap(fallback, paths)
        print(f"MyCyTax catalog: {len(catalog.pages)} pages from sitemap", flush=True)
        return catalog
    except Exception as exc:
        print(f"WARNING: MyCyTax sitemap unavailable ({exc}); using the committed fallback", flush=True)
        return fallback


def _field_text(title, body, tags):
    if isinstance(body, (list, tuple)):
        body = "\n".join(str(part) for part in body)
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",")]
    tag_text = " ".join(str(tag) for tag in (tags or []) if str(tag).strip())
    return normalize(title), normalize(body), normalize(tag_text)


def topic_scores(lang, title, body, tags):
    """How strongly title (3), tags (2) and body (1) mention each topic.

    Weak patterns, such as the bare English word "property", count only in the
    title and the tags. A passing use in the body is not enough on its own.
    """
    strong = KEYWORDS.get(lang) or {}
    weak = WEAK_KEYWORDS.get(lang) or {}
    title_n, body_n, tags_n = _field_text(title, body, tags)
    scores = {}
    for topic in set(strong) | set(weak):
        title_s = _searchable(title_n, lang, topic)
        body_s = _searchable(body_n, lang, topic)
        tags_s = _searchable(tags_n, lang, topic)
        score = 0
        strong_pats = strong.get(topic, [])
        weak_pats = weak.get(topic, [])
        if _hits(strong_pats, title_s) or _hits(weak_pats, title_s):
            score += 3
        if tags_s and (_hits(strong_pats, tags_s) or _hits(weak_pats, tags_s)):
            score += 2
        if body_s and _hits(strong_pats, body_s):
            score += 1
        if score:
            scores[topic] = score
    return scores


def _page_score(page, scores):
    return sum(scores.get(topic, 0) * weight for topic, weight in page.topics.items())


def relevant_pages(lang, title, body, tags, catalog, limit=3):
    """Two or three best guide/calculator pages, or none when nothing matches."""
    scores = topic_scores(lang, title, body, tags)
    if not scores or not catalog.pages:
        return []
    ranked = sorted(catalog.pages, key=lambda page: (-_page_score(page, scores), page.id))
    picked = [page for page in ranked if _page_score(page, scores) > 0][:limit]
    if len(picked) >= min(2, limit):
        return picked
    seen = {page.id for page in picked}
    for topic, _score in sorted(scores.items(), key=lambda item: (-item[1], item[0])):
        for page_id in TOPIC_DEFAULTS.get(topic, []):
            page = catalog.by_id.get(page_id)
            if page is None or page.id in seen:
                continue
            picked.append(page)
            seen.add(page.id)
            if len(picked) >= limit:
                return picked
    return picked


def _esc(value):
    return html.escape(value, quote=True)


def projects_html(lang, catalog):
    """Footer block: heading plus one language-specific link to the MyCyTax home."""
    heading = PROJECTS_HEADING[lang]
    label = SITE_LABEL[lang]
    url = catalog.home(lang)
    return (
        f'<nav class="projects" aria-label="{_esc(heading)}">'
        f'<p class="plabel">{_esc(heading)}</p>'
        f'<p><a href="{_esc(url)}" target="_blank" rel="noopener">{_esc(label)}</a></p>'
        f"</nav>"
    )


def article_crosslink(lang, title, body, tags, catalog):
    """Related-guides box, or one generic line when the article is not about these topics."""
    pages = relevant_pages(lang, title, body, tags, catalog)
    if not pages:
        url = catalog.home(lang)
        label = SITE_LABEL[lang]
        return f'<p class="sisterline"><a href="{_esc(url)}" target="_blank" rel="noopener">{_esc(label)}</a></p>'
    heading = USEFUL_HEADING[lang]
    items = "".join(
        f'<li><a href="{_esc(catalog.url(lang, page))}" target="_blank" rel="noopener">{_esc(page.label(lang))}</a></li>'
        for page in pages
    )
    return f'<aside class="sister" aria-label="{_esc(heading)}"><h2>{_esc(heading)}</h2><ul>{items}</ul></aside>'
