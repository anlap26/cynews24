# -*- coding: utf-8 -*-
import os, sys, json, html, shutil, re, datetime
from urllib.parse import quote_plus, urlparse
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mycytax
with open(os.path.join(HERE,"events.json"),encoding="utf8") as _ef:
    _EV=json.load(_ef)
EV_EVENTS=_EV["events"]
EV_PHOTOS=_EV["photos"]
SITE = "CyNews 24"
ADSENSE = '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1547877294743851" crossorigin="anonymous"></script>'
YANDEX_VERIFICATION = '<meta name="yandex-verification" content="4db90fdda985d0e0" />'
IMPACT_VERIFICATION = '<meta name="impact-site-verification" value="04c75eec-b177-4aab-a06b-a7dc4db45d6b">'
# Travelpayouts Drive. Marker 603740. Pasted as issued; the loader pulls emrldtp.com.
TRAVELPAYOUTS_DRIVE = """<script nowprocket data-noptimize="1" data-cfasync="false" data-wpfc-render="false" seraph-accel-crit="1" data-no-defer="1" data-cmp-ab="2">
  (function () {
      var script = document.createElement("script");
      script.async = 1;
      script.setAttribute("data-cmp-ab","2");
      script.src = 'https://emrldtp.com/NjAzNzQw.js?t=603740';
      document.head.appendChild(script);
  })();
</script>"""
# Bing Webmaster Tools value for <meta name="msvalidate.01">. Empty omits the tag.
BING_VERIFICATION = ""
# Google Analytics 4 measurement ID (G-XXXXXXXX). Empty means the tag is not loaded.
GA4_ID = ""
# IndexNow key. Every build rewrites /<key>.txt at the site root; the file body is the key.
INDEXNOW_KEY = "c9b38f2f2d7a4e59bfc566f01e259c2e"
ADS_TXT = "google.com, pub-1547877294743851, DIRECT, f08c47fec0942fa0\n"
# Absolute origin, no trailing slash. Include the repo path for GitHub project pages:
#   BASE=https://cynews24.net python3 build.py
BASE = os.environ.get("BASE","https://cynews24.net").rstrip("/")
# Root-relative prefix so CSS, images and internal links work when the site is not at
# the domain root. Taken from BASE (https://host/cynews24 → /cynews24) unless PREFIX is set.
# PREFIX= (empty) keeps domain-root links.
_prefix_env = os.environ.get("PREFIX")
if _prefix_env is None:
    PREFIX = urlparse(BASE).path.rstrip("/")
else:
    PREFIX = _prefix_env.rstrip("/")
# Repo root by default (parent of source/) so Pages can serve branch main / root.
OUT = os.environ.get("OUT", os.path.normpath(os.path.join(HERE, "..")))
SRC = os.path.join(HERE, "src")
LANGS = ["ru","en","el"]
LOCALE = {"ru":"ru_RU","en":"en_GB","el":"el_GR"}
LANGNAME = {"ru":"Русский","en":"English","el":"Ελληνικά"}
CATS = ["politics","economy","real-estate","society","tourism","sport","world"]
TRAVEL_MENU = {"en":"Travel","ru":"Путешествия","el":"Ταξίδια"}
GUIDE_MENU = {"en":"Guides","ru":"Гиды","el":"Οδηγοί"}
CATN = {
 "en":dict(zip(CATS,["Politics","Economy","Real Estate","Society","Tourism","Sport","World news"])),
 "ru":dict(zip(CATS,["Политика","Экономика","Недвижимость","Общество","Туризм","Спорт","Мировые новости"])),
 "el":dict(zip(CATS,["Πολιτική","Οικονομία","Ακίνητα","Κοινωνία","Τουρισμός","Αθλητισμός","Διεθνή νέα"]))}
# Regional desks under /{lang}/world/{region}/. The parent /world/ address stays.
REGIONS = ["europe","middle-east","russia-cis","asia","americas","africa"]
REGION_N = {
 "en":{"europe":"Europe","middle-east":"Middle East","russia-cis":"Russia & CIS","asia":"Asia","americas":"Americas","africa":"Africa"},
 "ru":{"europe":"Европа","middle-east":"Ближний Восток","russia-cis":"Россия и СНГ","asia":"Азия","americas":"Америка","africa":"Африка"},
 "el":{"europe":"Ευρώπη","middle-east":"Μέση Ανατολή","russia-cis":"Ρωσία και ΚΑΚ","asia":"Ασία","americas":"Αμερική","africa":"Αφρική"}}
REGION_MENU = {"en":"Regions","ru":"Регионы","el":"Περιοχές"}
RELOCATION_MENU = {"en":"Relocation","ru":"Переезд","el":"Μετακόμιση"}
# ---------- articles ----------
# One JSON file per article in content/articles/ (edited by hand or in the /admin/ CMS).
# Russian is required for news. English and Greek are optional: a missing translation
# falls back to the Russian text, and that language version is marked noindex until it
# is translated. A guide may be English only: Russian and Greek stay noindex and out of
# the sitemap, and the fallback text is the English text.
CONTENT = os.path.join(HERE, "content")
ART_DIR = os.path.join(CONTENT, "articles")
TEXT_FIELDS = ("title", "lede", "body", "alt", "kw")
def _clean(v):
    if v is None: return ""
    return v.strip() if isinstance(v, str) else v
def _paras(v):
    """Body as a list of paragraphs. Accepts a list, or text with blank lines between paragraphs.

    A block whose lines are all bullets, or all table rows, keeps the line breaks
    so the renderer can make a list or a table. Ordinary paragraphs are joined.
    """
    if isinstance(v, list): return [str(p).strip() for p in v if str(p).strip()]
    v = (v or "").replace("\r\n", "\n")
    out = []
    for p in re.split(r"\n\s*\n", v):
        lines = [x.strip() for x in p.split("\n") if x.strip()]
        if not lines:
            continue
        if all(x.startswith(("- ", "* ")) for x in lines) or (len(lines) >= 2 and all(x.startswith("|") for x in lines)):
            out.append("\n".join(lines))
        else:
            out.append(" ".join(lines))
    return out
def _kw(v):
    if isinstance(v, str): v = v.split(",")
    return [str(k).strip() for k in (v or []) if str(k).strip()]
def _media_path(v):
    """CMS image value (/source/src/x.jpg, source/src/x.jpg or x.jpg) -> file on disk."""
    v = (v or "").strip()
    if not v: return ""
    for cand in (os.path.join(HERE, "..", v.lstrip("/")), os.path.join(SRC, os.path.basename(v)), os.path.join(HERE, v.lstrip("/"))):
        if os.path.exists(cand): return os.path.normpath(cand)
    print(f"WARNING: image not found, using a placeholder: {v}")
    return ""
_TR = dict(zip("абвгдеёзийклмнопрстуфхыэ", "abvgdeezijklmnoprstufhye")) | {"ж":"zh","ц":"ts","ч":"ch","ш":"sh","щ":"sch","ю":"yu","я":"ya","ъ":"","ь":""}
def slugify(v):
    v = "".join(_TR.get(ch, ch) for ch in str(v).lower())
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", v)).strip("-")[:70].strip("-")
def _offers(path, lang, v):
    if not v: return {}
    if not isinstance(v, list): raise SystemExit(f"{path}: {lang} offers must be a list")
    out = {}
    for item in v:
        if not isinstance(item, dict): raise SystemExit(f"{path}: {lang} offer must be an object")
        partner = _clean(item.get("partner"))
        label = _clean(item.get("label"))
        note = _clean(item.get("note"))
        if not partner or not label: raise SystemExit(f"{path}: {lang} offer needs partner and label")
        if partner in out: raise SystemExit(f"{path}: duplicate offer {partner}")
        out[partner] = {"partner": partner, "label": label, "note": note}
    return out
def _faq(path, lang, v):
    if not v: return []
    if not isinstance(v, list): raise SystemExit(f"{path}: {lang} faq must be a list")
    out = []
    for item in v:
        if not isinstance(item, dict): raise SystemExit(f"{path}: {lang} faq item must be an object")
        q, a = _clean(item.get("q")), _clean(item.get("a"))
        if not q or not a: raise SystemExit(f"{path}: {lang} faq item needs q and a")
        out.append({"q": q, "a": a})
    return out
def _steps(path, lang, v):
    """Optional HowTo steps. A guide with two or more gets HowTo; news leaves this empty."""
    if not v: return []
    if not isinstance(v, list): raise SystemExit(f"{path}: {lang} steps must be a list")
    out = []
    for item in v:
        if not isinstance(item, dict): raise SystemExit(f"{path}: {lang} step must be an object")
        name, text = _clean(item.get("name")), _clean(item.get("text"))
        if not name or not text: raise SystemExit(f"{path}: {lang} step needs name and text")
        out.append({"name": name, "text": text})
    if len(out) == 1:
        raise SystemExit(f"{path}: {lang} HowTo needs at least two steps")
    return out
def load_story(path):
    with open(path, encoding="utf8") as f: d = json.load(f)
    stem = os.path.splitext(os.path.basename(path))[0]
    # Page address: the slug field, else the file name, else the Russian title, in Latin letters.
    slug = slugify(_clean(d.get("slug")) or stem) or slugify((d.get("ru") or {}).get("title", ""))
    if not slug: raise SystemExit(f"{path}: cannot make a page address (slug)")
    cat = _clean(d.get("cat"))
    if cat not in CATS: raise SystemExit(f"{path}: unknown category {cat!r}")
    region = _clean(d.get("region"))
    if region and region not in REGIONS: raise SystemExit(f"{path}: unknown region {region!r}")
    if region and cat != "world": raise SystemExit(f"{path}: region is only for world news")
    date = str(_clean(d.get("date")))[:10]
    datetime.date.fromisoformat(date)
    ru = d.get("ru") or {}
    en = d.get("en") or {}
    def _ready(src):
        return all(_clean(src.get(k)) for k in ("title", "lede", "body"))
    # News needs Russian. An English-only guide is allowed: the other languages are noindex.
    if _ready(ru):
        base_lang, base = "ru", ru
    elif d.get("guide") and _ready(en):
        base_lang, base = "en", en
    else:
        raise SystemExit(f"{path}: Russian title, lede and body are required")
    s = {"slug": slug, "file": stem, "cat": cat, "date": date, "region": region, "seq": d.get("seq"), "missing": set(), "guide": bool(d.get("guide"))}
    for k in ("title", "lede", "alt", "desc"): s[k] = {}
    s["body"] = {}; s["kw"] = {}; s["offers"] = {}; s["faq"] = {}; s["steps"] = {}
    for l in LANGS:
        src = d.get(l) or {}
        if l != base_lang and not _ready(src):
            s["missing"].add(l); src = base
        s["title"][l] = _clean(src.get("title")); s["lede"][l] = _clean(src.get("lede"))
        s["body"][l] = _paras(src.get("body"))
        s["alt"][l] = _clean(src.get("alt")) or _clean(ru.get("alt")) or s["title"][l]
        s["kw"][l] = _kw(src.get("kw"))
        s["desc"][l] = _clean(src.get("desc"))
        s["offers"][l] = _offers(path, l, src.get("offers"))
        s["faq"][l] = _faq(path, l, src.get("faq"))
        s["steps"][l] = _steps(path, l, src.get("steps"))
    s["sources"] = [(_clean(x.get("name")) or _clean(x.get("url")), _clean(x.get("url")))
                    for x in (d.get("sources") or []) if _clean(x.get("url"))]
    if _clean(d.get("updated")): s["updated"] = _clean(d["updated"])
    image = _clean(d.get("image"))
    if image:
        # Uploaded in the CMS: the picture is cropped to 16:9 and watermarked under the slug's name.
        s["img"] = slug; s["upload"] = _media_path(image)
        pc = d.get("photo_credit") or {}
        s["credit"] = {k: _clean(pc.get(k)) for k in ("author", "source", "page", "license", "license_url")}
    elif _clean(d.get("img")):
        s["img"] = _clean(d["img"])
    else:
        # No picture yet: a plain card is drawn. A new article still fails the build
        # until a photograph at least 1200px wide is added. See KNOWN_SMALL_LEADS.
        s["img"] = slug; s["upload"] = None; s["credit"] = {}
    return s
def load_stories():
    out = [load_story(os.path.join(ART_DIR, f)) for f in sorted(os.listdir(ART_DIR)) if f.endswith(".json")]
    slugs = [s["slug"] for s in out]
    dup = {x for x in slugs if slugs.count(x) > 1}
    if dup: raise SystemExit(f"Duplicate slugs: {sorted(dup)}")
    taken = set(slugs)
    for s in out:
        # A CMS file keeps its transliterated name after the address field is filled in.
        # That name must not be another article's public address, or the alias would replace it.
        if s["file"] != s["slug"] and s["file"] in taken:
            raise SystemExit(f"{s['file']}: file name is already another article's address")
    # Articles migrated from the old generator keep their original order (seq). New ones follow, oldest first.
    return sorted(out, key=lambda s: (s["seq"] is None, s["seq"] if s["seq"] is not None else 0, s["date"], s["slug"]))
STORIES = load_stories()
MONTHS = {"en":["January","February","March","April","May","June","July","August","September","October","November","December"],
 "ru":["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"],
 "el":["Ιανουαρίου","Φεβρουαρίου","Μαρτίου","Απριλίου","Μαΐου","Ιουνίου","Ιουλίου","Αυγούστου","Σεπτεμβρίου","Οκτωβρίου","Νοεμβρίου","Δεκεμβρίου"]}
WD = {"en":["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
 "ru":["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"],
 "el":["Δευτέρα","Τρίτη","Τετάρτη","Πέμπτη","Παρασκευή","Σάββατο","Κυριακή"]}
def fdate(d,l,wd=False):
    dt=datetime.date.fromisoformat(d)
    s = f"{dt.day} {MONTHS[l][dt.month-1]} {dt.year}" if l!="en" else f"{dt.day} {MONTHS[l][dt.month-1]} {dt.year}"
    return (WD[l][dt.weekday()]+", "+s) if wd else s
# Site date (header, events "this week", sitemap lastmod): today in Cyprus unless TODAY=YYYY-MM-DD is set.
def _today():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Asia/Nicosia")).date().isoformat()
    except Exception:
        return (datetime.datetime.utcnow()+datetime.timedelta(hours=2)).date().isoformat()
TODAY=os.environ.get("TODAY") or _today()
UI = {
 "en":dict(home="Home",latest="Latest",more="More news",sources="Sources",related="Related stories",toplines="Top stories",
  byline="CyNews 24 Editorial Team",illus="Illustration created for CyNews 24 (AI-generated, not a photograph)",
  sources_note="This article is an original rewrite of facts reported by the outlets below; read the originals for full detail.",
  read="Read more",tags="Topics",lang="Language",about="About us",ads="Advertise & Contact",events="Events",menu="Sections",skip="Skip to content",
  policy="Editorial policy",privacy="Privacy policy",cookies="Cookie policy",cookie_settings="Cookie settings",
  cookie_title="Cookies",cookie_accept="Accept",cookie_reject="Reject",
  cookie_text="We use cookies so Google can show ads and, when analytics is switched on, count visits. Until you accept, those cookies stay off.",
  published="Published",team="CyNews 24 Editorial Team",
  tg="Telegram",tg_cta="Follow Cyprus news on Telegram",
  tg_ru="Telegram (RU)",tg_en="Telegram (EN)",
  tagline="Cyprus news in three languages",
  footer="CyNews 24 summarises public reporting from Cypriot and international media in Russian, English and Greek. Articles are rewritten in our own words and link to their sources; photographs are used under open licences and credited. CyNews 24 is not affiliated with the outlets cited.",
  copy="All rights reserved.",updated="Updated",home_h="Top stories from Cyprus",realestate_h="Real estate & planning",allnews="All news",
  cat_h="{c} — news from Cyprus", crumb_home="Home",
  faq="Questions readers ask",
  disclosure="Affiliate disclosure",
  disclosure_text="Some links on this page are affiliate links. If you use one, CyNews 24 may earn a commission. The provider sets the price. Terms change, so read them on the provider’s site before you buy. This page is not insurance, legal or security advice.",
  sources_note_guide="The links below are the public pages this guide relies on. They are not a quotation, and a provider’s terms can change."),
 "ru":dict(home="Главная",latest="Последние новости",more="Ещё новости",sources="Источники",related="Читайте также",toplines="Главное",
  byline="Редакционная группа CyNews 24",illus="Иллюстрация создана для CyNews 24 (сгенерирована ИИ, не фотография)",
  sources_note="Материал — авторский пересказ фактов, опубликованных изданиями ниже; полные подробности — в оригиналах.",
  read="Читать далее",tags="Темы",lang="Язык",about="О проекте",ads="Реклама и контакты",events="Мероприятия",menu="Разделы",skip="Перейти к содержанию",
  policy="Редакционная политика",privacy="Политика конфиденциальности",cookies="Политика cookie",cookie_settings="Настройки cookie",
  cookie_title="Файлы cookie",cookie_accept="Принять",cookie_reject="Отклонить",
  cookie_text="Мы используем cookie, чтобы Google мог показывать рекламу и, если аналитика включена, считать визиты. Пока вы не примите их, такие cookie выключены.",
  published="Опубликовано",team="Редакционная группа CyNews 24",
  tg="Telegram",tg_cta="Подписывайтесь на наш Telegram-канал — новости Кипра первыми",
  tg_ru="Telegram (RU)",tg_en="Telegram (EN)",
  tagline="Новости Кипра на трёх языках",
  footer="CyNews 24 обобщает публикации кипрских и международных СМИ на русском, английском и греческом языках. Тексты написаны своими словами и содержат ссылки на источники; фотографии используются по открытым лицензиям с указанием автора. CyNews 24 не связан с упомянутыми изданиями.",
  copy="Все права защищены.",updated="Обновлено",home_h="Главные новости Кипра",realestate_h="Недвижимость и градостроительство",allnews="Все новости",
  cat_h="{c} — новости Кипра", crumb_home="Главная",
  faq="Вопросы читателей",
  disclosure="Раскрытие партнёрских ссылок",
  disclosure_text="Часть ссылок на этой странице — партнёрские. Если вы перейдёте по такой ссылке, CyNews 24 может получить комиссию. Цену назначает сам сервис. Условия меняются: перед покупкой прочитайте их на сайте сервиса. Эта страница — не страховая, юридическая или иная профессиональная консультация.",
  sources_note_guide="Ниже — публичные страницы, на которые опирается этот материал. Это не цитата из договора, и условия сервиса могут измениться."),
 "el":dict(home="Αρχική",latest="Τελευταία νέα",more="Περισσότερες ειδήσεις",sources="Πηγές",related="Σχετικά θέματα",toplines="Κορυφαία θέματα",
  byline="Συντακτική ομάδα CyNews 24",illus="Εικονογράφηση για το CyNews 24 (δημιουργήθηκε με ΤΝ, όχι φωτογραφία)",
  sources_note="Το κείμενο είναι πρωτότυπη αναδιατύπωση γεγονότων που δημοσίευσαν τα παρακάτω μέσα· για πλήρεις λεπτομέρειες δείτε τα πρωτότυπα.",
  read="Διαβάστε περισσότερα",tags="Θέματα",lang="Γλώσσα",about="Σχετικά με εμάς",ads="Διαφήμιση & Επικοινωνία",events="Εκδηλώσεις",menu="Ενότητες",skip="Μετάβαση στο περιεχόμενο",
  policy="Συντακτική πολιτική",privacy="Πολιτική απορρήτου",cookies="Πολιτική cookies",cookie_settings="Ρυθμίσεις cookies",
  cookie_title="Cookies",cookie_accept="Αποδοχή",cookie_reject="Απόρριψη",
  cookie_text="Χρησιμοποιούμε cookies ώστε η Google να εμφανίζει διαφημίσεις και, όταν τα αναλυτικά είναι ενεργά, να μετρά τις επισκέψεις. Μέχρι να τα αποδεχτείτε, αυτά τα cookies μένουν κλειστά.",
  published="Δημοσιεύτηκε",team="Συντακτική ομάδα CyNews 24",
  tg="Telegram",tg_cta="Ακολουθήστε μας στο Telegram",
  tg_ru="Telegram (RU)",tg_en="Telegram (EN)",
  tagline="Ειδήσεις Κύπρου σε τρεις γλώσσες",
  footer="Το CyNews 24 συνοψίζει δημοσιεύματα κυπριακών και διεθνών μέσων στα ρωσικά, αγγλικά και ελληνικά. Τα κείμενα γράφονται με δικά μας λόγια και παραπέμπουν στις πηγές τους· οι φωτογραφίες χρησιμοποιούνται με ανοιχτές άδειες και αναφέρουν τον δημιουργό. Το CyNews 24 δεν συνδέεται με τα μέσα που αναφέρονται.",
  copy="Με επιφύλαξη παντός δικαιώματος.",updated="Ενημερώθηκε",home_h="Κορυφαίες ειδήσεις από την Κύπρο",realestate_h="Ακίνητα και πολεοδομία",allnews="Όλες οι ειδήσεις",
  cat_h="{c} — ειδήσεις από την Κύπρο", crumb_home="Αρχική",
  faq="Ερωτήσεις αναγνωστών",
  disclosure="Γνωστοποίηση συνεργατών",
  disclosure_text="Ορισμένοι σύνδεσμοι σε αυτή τη σελίδα είναι σύνδεσμοι συνεργατών. Αν τους χρησιμοποιήσετε, το CyNews 24 μπορεί να λάβει προμήθεια. Την τιμή την ορίζει ο πάροχος. Οι όροι αλλάζουν· διαβάστε τους στον ιστότοπο του παρόχου πριν αγοράσετε. Η σελίδα δεν είναι ασφαλιστική, νομική ή άλλη επαγγελματική συμβουλή.",
  sources_note_guide="Οι σύνδεσμοι παρακάτω είναι οι δημόσιες σελίδες στις οποίες στηρίζεται αυτός ο οδηγός. Δεν είναι παράθεμα σύμβασης, και οι όροι ενός παρόχου μπορεί να αλλάξουν."),
}
HOME_T = {"en":"CyNews 24 – Cyprus and world news today: politics, economy, property",
 "ru":"CyNews 24 — Новости Кипра и мира сегодня: политика, экономика, недвижимость",
 "el":"CyNews 24 — Ειδήσεις Κύπρου και κόσμου: πολιτική, οικονομία, ακίνητα"}
HOME_D = {"en":"Cyprus and world news today in English, Russian and Greek: politics, economy, real estate, tourism, relocation and sport, with sources linked.",
 "ru":"Новости Кипра и мира сегодня на русском, английском и греческом: политика, экономика, недвижимость, туризм, переезд и спорт со ссылками на источники.",
 "el":"Ειδήσεις Κύπρου και κόσμου σήμερα σε ελληνικά, αγγλικά και ρωσικά: πολιτική, οικονομία, ακίνητα, τουρισμός, μετακόμιση και αθλητισμός, με πηγές."}
GKW = {"en":["Cyprus news","Cyprus news today","latest news Cyprus","Cyprus real estate news","Cyprus property market","Limassol news","Nicosia news","Paphos news","Larnaca news","Cyprus politics","Cyprus economy","news from Cyprus in English"],
 "ru":["Кипр новости","новости Кипра сегодня","последние новости Кипра","новости недвижимости Кипра","рынок недвижимости Кипра","новости Лимассола","новости Никосии","новости Пафоса","Кипр на русском","политика Кипра","экономика Кипра"],
 "el":["Κύπρος ειδήσεις","ειδήσεις Κύπρου σήμερα","τελευταία νέα Κύπρος","ειδήσεις ακινήτων Κύπρος","αγορά ακινήτων Κύπρος","ειδήσεις Λεμεσός","ειδήσεις Λευκωσία","ειδήσεις Πάφος","πολιτική Κύπρος","οικονομία Κύπρου"]}
CAT_D = {
 "en":{"politics":"Cyprus politics news: the Cyprus problem, government, parliament and EU affairs, with sources linked.","economy":"Cyprus economy news: prices, tax, energy, jobs, pensions and finance, rewritten from linked sources.","real-estate":"Cyprus real estate news: property law, planning, new homes and the housing market, with sources linked.","society":"Cyprus society news: courts, police, health, schools and everyday life, with sources linked.","tourism":"Cyprus tourism news: visitor numbers, flights, beaches, holidays and what is on, with sources linked.","sport":"Cyprus sport news: results, athletes and major events, with sources linked.","world":"World news by region — Europe, the Middle East, Russia and the CIS, Asia, the Americas and Africa — rewritten from linked sources."},
 "ru":{"politics":"Политические новости Кипра: кипрская проблема, правительство, парламент и дела ЕС, со ссылками на источники.","economy":"Экономика Кипра: цены, налоги, энергия, работа, пенсии и финансы, пересказ со ссылками на источники.","real-estate":"Недвижимость Кипра: законы, градостроительство, новостройки и рынок жилья, со ссылками на источники.","society":"Общество Кипра: суды, полиция, здоровье, школы и повседневная жизнь, со ссылками на источники.","tourism":"Туризм Кипра: приезды, рейсы, пляжи, отпуска и афиша, со ссылками на источники.","sport":"Спорт Кипра: результаты, спортсмены и крупные старты, со ссылками на источники.","world":"Мировые новости по регионам — Европа, Ближний Восток, Россия и СНГ, Азия, Америка и Африка — пересказ со ссылками на источники."},
 "el":{"politics":"Πολιτικές ειδήσεις Κύπρου: Κυπριακό, κυβέρνηση, Βουλή και ευρωπαϊκά θέματα, με συνδέσμους στις πηγές.","economy":"Οικονομία Κύπρου: τιμές, φόροι, ενέργεια, εργασία, συντάξεις και χρηματοοικονομικά, με πηγές.","real-estate":"Ακίνητα Κύπρου: νομοθεσία, πολεοδομία, νεόδμητα και αγορά κατοικίας, με συνδέσμους στις πηγές.","society":"Κοινωνία Κύπρου: δικαστήρια, αστυνομία, υγεία, σχολεία και καθημερινότητα, με πηγές.","tourism":"Τουρισμός Κύπρου: αφίξεις, πτήσεις, παραλίες, διακοπές και πρόγραμμα, με συνδέσμους στις πηγές.","sport":"Αθλητισμός Κύπρου: αποτελέσματα, αθλητές και μεγάλες διοργανώσεις, με πηγές.","world":"Διεθνή νέα ανά περιοχή — Ευρώπη, Μέση Ανατολή, Ρωσία και ΚΑΚ, Ασία, Αμερική και Αφρική — με συνδέσμους στις πηγές."}}
CAT_TITLE = {
 "en":{"politics":"Cyprus politics news | CyNews 24","economy":"Cyprus economy news | CyNews 24","real-estate":"Cyprus real estate news | CyNews 24","society":"Cyprus society news | CyNews 24","tourism":"Cyprus tourism news | CyNews 24","sport":"Cyprus sport news | CyNews 24","world":"World news today | CyNews 24"},
 "ru":{"politics":"Политика Кипра — новости | CyNews 24","economy":"Экономика Кипра — новости | CyNews 24","real-estate":"Недвижимость Кипра — новости | CyNews 24","society":"Общество Кипра — новости | CyNews 24","tourism":"Туризм Кипра — новости | CyNews 24","sport":"Спорт Кипра — новости | CyNews 24","world":"Мировые новости сегодня | CyNews 24"},
 "el":{"politics":"Πολιτική Κύπρου — ειδήσεις | CyNews 24","economy":"Οικονομία Κύπρου — ειδήσεις | CyNews 24","real-estate":"Ακίνητα Κύπρου — ειδήσεις | CyNews 24","society":"Κοινωνία Κύπρου — ειδήσεις | CyNews 24","tourism":"Τουρισμός Κύπρου — ειδήσεις | CyNews 24","sport":"Αθλητισμός Κύπρου — ειδήσεις | CyNews 24","world":"Διεθνή νέα σήμερα | CyNews 24"}}
AD_EMAIL="cynews24@gmail.com"
PUBLISHER="Anna"
# Real profile URLs only. An empty string is not rendered.
# Facebook stays hidden: Post to Facebook stores the page id in a secret, not a public URL.
THREADS_URL="https://www.threads.com/@cynews24"
SOCIAL={"facebook":"","instagram":"https://www.instagram.com/cynews24/","threads":THREADS_URL}
TELEGRAM={"ru":"https://t.me/cynews24","en":"https://t.me/cynews24en"}
ABOUT = {
 "en":dict(t="About CyNews 24",d="CyNews 24 is an independent trilingual Cyprus news aggregator and digest, published in Russian, English and Greek and based in Cyprus.",
  sections=[
   ("Who we are",["CyNews 24 is an independent trilingual Cyprus news aggregator and digest. It is published in Russian, English and Greek, and every story is available in all three languages. The site is based in Cyprus. The publisher is Anna. CyNews 24 is not affiliated with the outlets it cites."]),
   ("Mission",["Our mission is to give readers a clear, sourced briefing of what is happening in Cyprus, in the language they read. We select distinct, newsworthy reports and rewrite them so the same facts can be read in Russian, English and Greek."]),
   ("Coverage",["We cover Cyprus politics, the economy, real estate and planning, society, tourism, sport, and world news with a Cyprus connection. A separate Events section lists confirmed upcoming events. We do not publish every brief: a story has to be distinct and newsworthy."]),
   ("CyNews 24 Editorial Team",["Stories carry the byline CyNews 24 Editorial Team. We do not use individual reporter bylines, and this page does not name members of staff. For editorial questions, corrections or tips, email cynews24@gmail.com."]),
   ("How stories are produced",["We follow reporting from Cypriot and international outlets and write each article as an original rewritten summary. Facts come only from the cited sources. We do not invent numbers, quotes or events. Every article ends with a Sources box that links to the originals.","Photographs are real pictures under open licences that allow commercial use and adaptation — CC0, CC BY or CC BY-SA, from Wikimedia Commons, Unsplash or Pexels. They are never taken from news sites. Each picture is credited with its author, source and licence and links to the original file. Where the licence is CC BY-SA, the cropped and watermarked version stays under that same licence. A picture shows the place or subject of a story; it is not a photograph of a person named in the article unless the credit says so."]),
   ("Contact",["Publisher: Anna.","Based in Cyprus.","Email: cynews24@gmail.com.","Advertising and other enquiries use the advertising and contact page. Editorial standards are set out in the editorial policy, and the privacy policy explains the contact form."])]),
 "ru":dict(t="О проекте CyNews 24",d="CyNews 24 — независимый трёхъязычный агрегатор и дайджест новостей Кипра на русском, английском и греческом. Сайт базируется на Кипре.",
  sections=[
   ("Кто мы",["CyNews 24 — независимый трёхъязычный агрегатор и дайджест новостей Кипра. Сайт выходит на русском, английском и греческом языках, и каждый материал доступен на всех трёх. Сайт базируется на Кипре. Издатель — Анна. CyNews 24 не связан с изданиями, на которые ссылается."]),
   ("Задача",["Наша задача — давать читателю ясный пересказ того, что происходит на Кипре, со ссылками на источники и на том языке, на котором он читает. Мы отбираем отдельные стоящие новости и переписываем их так, чтобы одни и те же факты можно было прочитать по-русски, по-английски и по-гречески."]),
   ("О чём мы пишем",["Мы освещаем политику Кипра, экономику, недвижимость и градостроительство, общество, туризм, спорт и мировые новости, связанные с Кипром. Отдельный раздел «Мероприятия» собирает подтверждённые предстоящие события. Мы публикуем не каждую заметку: материал должен быть отдельной и значимой новостью."]),
   ("Редакционная группа CyNews 24",["Материалы выходят с подписью «Редакционная группа CyNews 24». Мы не ставим подписи отдельных корреспондентов, и на этой странице нет имён сотрудников. Вопросы редакции, поправки и сообщения присылайте на cynews24@gmail.com."]),
   ("Как готовятся материалы",["Мы следим за публикациями кипрских и международных изданий и пишем каждый материал как оригинальный пересказ. Факты берутся только из указанных источников. Мы не выдумываем цифры, цитаты и события. В конце каждого материала — блок «Источники» со ссылками на оригиналы.","Фотографии — настоящие снимки по открытым лицензиям, которые разрешают коммерческое использование и переработку: CC0, CC BY или CC BY-SA, с Wikimedia Commons, Unsplash или Pexels. Мы не берём фотографии с новостных сайтов. У каждого снимка указаны автор, источник и лицензия и есть ссылка на оригинал. Если лицензия CC BY-SA, кадрированная версия с водяным знаком остаётся под той же лицензией. Снимок показывает место или тему материала и не является фотографией человека, названного в тексте, если это прямо не сказано в подписи."]),
   ("Контакты",["Издатель: Анна.","Базируется на Кипре.","Эл. почта: cynews24@gmail.com.","Реклама и прочие обращения — на странице рекламы и контактов. Редакционные правила изложены в редакционной политике, а политика конфиденциальности объясняет контактную форму."])]),
 "el":dict(t="Σχετικά με το CyNews 24",d="Το CyNews 24 είναι ανεξάρτητος τρίγλωσσος συναθροιστής και σύνοψη ειδήσεων Κύπρου, στα ρωσικά, αγγλικά και ελληνικά, με έδρα την Κύπρο.",
  sections=[
   ("Ποιοι είμαστε",["Το CyNews 24 είναι ανεξάρτητος τρίγλωσσος συναθροιστής και σύνοψη ειδήσεων Κύπρου. Δημοσιεύεται στα ρωσικά, αγγλικά και ελληνικά, και κάθε θέμα υπάρχει και στις τρεις γλώσσες. Ο ιστότοπος έχει έδρα την Κύπρο. Εκδότρια είναι η Άννα. Το CyNews 24 δεν συνδέεται με τα μέσα στα οποία παραπέμπει."]),
   ("Αποστολή",["Αποστολή μας είναι να δίνουμε στους αναγνώστες μια σαφή, τεκμηριωμένη σύνοψη όσων συμβαίνουν στην Κύπρο, στη γλώσσα που διαβάζουν. Επιλέγουμε διακριτά, άξια λόγου ρεπορτάζ και τα αναδιατυπώνουμε ώστε τα ίδια γεγονότα να διαβάζονται στα ρωσικά, αγγλικά και ελληνικά."]),
   ("Κάλυψη",["Καλύπτουμε την πολιτική της Κύπρου, την οικονομία, τα ακίνητα και την πολεοδομία, την κοινωνία, τον τουρισμό, τον αθλητισμό και διεθνή θέματα με κυπριακή σύνδεση. Ξεχωριστή ενότητα Εκδηλώσεων συγκεντρώνει επιβεβαιωμένες προσεχείς εκδηλώσεις. Δεν δημοσιεύουμε κάθε ανακοίνωση: ένα θέμα πρέπει να είναι διακριτό και άξιο είδησης."]),
   ("Συντακτική ομάδα CyNews 24",["Τα άρθρα φέρουν την υπογραφή Συντακτική ομάδα CyNews 24. Δεν χρησιμοποιούμε ατομικές υπογραφές ρεπόρτερ και αυτή η σελίδα δεν κατονομάζει μέλη της ομάδας. Για συντακτικά ερωτήματα, διορθώσεις ή πληροφορίες, στείλτε email στο cynews24@gmail.com."]),
   ("Πώς παράγονται τα άρθρα",["Παρακολουθούμε ρεπορτάζ κυπριακών και διεθνών μέσων και γράφουμε κάθε άρθρο ως πρωτότυπη αναδιατυπωμένη σύνοψη. Τα γεγονότα προέρχονται μόνο από τις αναφερόμενες πηγές. Δεν επινοούμε αριθμούς, δηλώσεις ή γεγονότα. Κάθε άρθρο κλείνει με πλαίσιο Πηγών που συνδέεται με τα πρωτότυπα.","Οι φωτογραφίες είναι πραγματικές εικόνες με ανοιχτές άδειες που επιτρέπουν εμπορική χρήση και διασκευή — CC0, CC BY ή CC BY-SA, από τα Wikimedia Commons, το Unsplash ή το Pexels. Δεν τις παίρνουμε από ειδησεογραφικούς ιστότοπους. Κάθε εικόνα αναφέρει τον δημιουργό, την πηγή και την άδεια και συνδέεται με το πρωτότυπο αρχείο. Όταν η άδεια είναι CC BY-SA, η περικομμένη εκδοχή με το υδατογράφημα παραμένει στην ίδια άδεια. Η εικόνα δείχνει τον τόπο ή το θέμα του άρθρου και δεν είναι φωτογραφία προσώπου που κατονομάζεται στο κείμενο, εκτός αν αυτό αναφέρεται στη λεζάντα."]),
   ("Επικοινωνία",["Εκδότρια: Άννα.","Έδρα: Κύπρος.","Email: cynews24@gmail.com.","Η διαφήμιση και τα λοιπά αιτήματα γίνονται από τη σελίδα διαφήμισης και επικοινωνίας. Οι συντακτικοί κανόνες περιγράφονται στη συντακτική πολιτική και η πολιτική απορρήτου εξηγεί τη φόρμα επικοινωνίας."])])}
POLICY = {
 "en":dict(t="Editorial policy and corrections",d="How CyNews 24 checks facts, cites sources, separates advertising from news, and handles corrections.",
  sections=[
   ("Accuracy",["We publish facts that appear in the sources we cite. We do not invent quotes, statistics or events. If sources disagree, we say so or we do not treat the point as settled."]),
   ("Sourcing",["Each news article lists its sources and links to them. The article is a rewritten summary, not a copy of those reports. Readers should open the links for the full original. Citing an outlet is not an endorsement, and it does not mean that outlet wrote our text."]),
   ("Corrections",["If you believe a story is wrong, email cynews24@gmail.com with the article URL, the passage and the correction. We review the request. When a correction is needed, we change the article and its updated time. A correction is not removed because it is inconvenient."]),
   ("Advertising is separate from news",["Sponsored or paid material is labelled and kept separate from newsroom reporting. Advertising enquiries go through the advertising and contact page and are not handled as news. Rates are available on request."]),
   ("Affiliate links",["Some practical guides link to commercial partners such as an insurer or a security service. Those links are labelled, and the affiliate disclosure page explains them. A partner link is not a news story, and it is not a statement of a price or of what a policy covers. The guide does not invent prices, limits or statistics."]),
   ("Contact the newsroom",["Editorial questions and correction requests: cynews24@gmail.com. The publisher is Anna, and the site is based in Cyprus."])]),
 "ru":dict(t="Редакционная политика и поправки",d="Как CyNews 24 проверяет факты, указывает источники, отделяет рекламу от новостей и исправляет ошибки.",
  sections=[
   ("Точность",["Мы публикуем факты, которые есть в указанных источниках. Мы не выдумываем цитаты, статистику и события. Если источники расходятся, мы так и пишем или не подаём спорное как установленное."]),
   ("Источники",["У каждого новостного материала есть список источников и ссылки на них. Текст — пересказ, а не копия этих публикаций. Полный оригинал — по ссылке. Ссылка на издание не означает поддержки и не означает, что текст написало это издание."]),
   ("Поправки",["Если вы считаете, что в материале ошибка, напишите на cynews24@gmail.com: укажите адрес страницы, фрагмент и поправку. Мы рассматриваем обращение. Если поправка нужна, мы меняем материал и время его обновления. Поправку не снимают из-за того, что она неудобна."]),
   ("Реклама отделена от новостей",["Спонсорские и оплаченные материалы помечаются и отделены от редакционных новостей. Запросы о рекламе идут через страницу рекламы и контактов и не оформляются как новости. Стоимость — по запросу."]),
   ("Партнёрские ссылки",["В некоторых практических материалах есть ссылки на коммерческих партнёров, например на страховщика или сервис защиты данных. Такие ссылки помечены, а страница о партнёрских ссылках объясняет, как они устроены. Партнёрская ссылка — не новость и не утверждение о цене или о составе покрытия. Материал не выдумывает цены, лимиты и статистику."]),
   ("Связь с редакцией",["Вопросы редакции и просьбы об исправлении: cynews24@gmail.com. Издатель — Анна, сайт базируется на Кипре."])]),
 "el":dict(t="Συντακτική πολιτική και διορθώσεις",d="Πώς το CyNews 24 ελέγχει τα γεγονότα, αναφέρει πηγές, διαχωρίζει τη διαφήμιση από τις ειδήσεις και χειρίζεται διορθώσεις.",
  sections=[
   ("Ακρίβεια",["Δημοσιεύουμε γεγονότα που εμφανίζονται στις πηγές που αναφέρουμε. Δεν επινοούμε δηλώσεις, στατιστικά ή γεγονότα. Αν οι πηγές διαφωνούν, το λέμε ή δεν παρουσιάζουμε το σημείο ως δεδομένο."]),
   ("Πηγές",["Κάθε ειδησεογραφικό άρθρο παραθέτει τις πηγές του και συνδέεται με αυτές. Το άρθρο είναι αναδιατυπωμένη σύνοψη, όχι αντίγραφο εκείνων των ρεπορτάζ. Οι αναγνώστες ανοίγουν τους συνδέσμους για το πλήρες πρωτότυπο. Η παραπομπή σε ένα μέσο δεν είναι εύνοια και δεν σημαίνει ότι εκείνο έγραψε το κείμενό μας."]),
   ("Διορθώσεις",["Αν πιστεύετε ότι ένα άρθρο έχει λάθος, στείλτε email στο cynews24@gmail.com με τη διεύθυνση του άρθρου, το απόσπασμα και τη διόρθωση. Εξετάζουμε το αίτημα. Όταν χρειάζεται διόρθωση, αλλάζουμε το άρθρο και την ώρα ενημέρωσής του. Μια διόρθωση δεν αποσύρεται επειδή είναι άβολη."]),
   ("Η διαφήμιση είναι χωριστά από τις ειδήσεις",["Το χορηγούμενο ή πληρωμένο υλικό επισημαίνεται και μένει χωριστά από το ρεπορτάζ. Τα διαφημιστικά αιτήματα περνούν από τη σελίδα διαφήμισης και επικοινωνίας και δεν αντιμετωπίζονται ως ειδήσεις. Οι τιμές δίνονται κατόπιν αιτήματος."]),
   ("Σύνδεσμοι συνεργατών",["Ορισμένοι πρακτικοί οδηγοί παραπέμπουν σε εμπορικούς συνεργάτες, για παράδειγμα σε έναν ασφαλιστή ή σε μια υπηρεσία προστασίας δεδομένων. Οι σύνδεσμοι επισημαίνονται, και η σελίδα γνωστοποίησης εξηγεί πώς λειτουργούν. Ένας σύνδεσμος συνεργάτη δεν είναι είδηση και δεν δηλώνει τιμή ή τι καλύπτει ένα συμβόλαιο. Ο οδηγός δεν επινοεί τιμές, όρια ή στατιστικά."]),
   ("Επικοινωνία με τη σύνταξη",["Συντακτικά ερωτήματα και αιτήματα διόρθωσης: cynews24@gmail.com. Εκδότρια είναι η Άννα και ο ιστότοπος έχει έδρα την Κύπρο."])])}
DISCLOSURE = {
 "en":dict(t="Affiliate disclosure",d="How CyNews 24 uses affiliate links, which partners they point to, and what those links do not promise.",
  sections=[
   ("What an affiliate link is",["Some practical guides on CyNews 24 link to companies whose products a reader who lives or travels abroad may actually use: international health insurance, a travel eSIM, a VPN, encrypted email, or a password manager. If you follow one of those links and buy, the company may pay CyNews 24 a commission. You do not pay an extra fee to us. The price, if there is one, is the price on the company’s own site."]),
   ("Where the links live",["Every partner address is stored in one configuration file, source/affiliates.json. The site publishes that file as /assets/js/affiliates.js, and every partner button reads the address from there. Until a real address is added, the value is a placeholder such as #AFFILIATE_GENKI. A placeholder does not go to a shop. The partners named in the guides are Genki, Airalo, NordVPN, Surfshark, Proton (VPN, Pass and Mail) and 1Password. Some practical pages also link to Amazon.de. The Economy section, and articles about crypto, also link to a Trezor Safe 7 hardware wallet. That address is the trezor entry in the same file. The button does not state a price."]),
   ("Amazon",["Those Amazon links are searches on Amazon.de, not a page for one product, and they do not name a price. As an Amazon Associate I earn from qualifying purchases. The home address carries the tag cynews24-21, and a search uses the same tag. CyNews 24 does not invent a product code. What Amazon shows, and what it costs, is on Amazon at the time you look."]),
   ("Travel links",["Every travel-guide address lives in one file, source/travel_affiliates.json. Airalo, Yesim, Klook, Kiwitaxi, Welcome Pickups and Aviasales buttons inside the guides are Travelpayouts links, marker 603740. Booking, GetYourGuide, DiscoverCars and SafetyWing are still each company’s own homepage, until those programmes are approved. A separate row, Travel in Cyprus, uses marker 808586: Localrent, Welcome Pickups, Kiwitaxi, Klook, Tiqets, Airalo and Aviasales. A button is marked sponsored. None of these links states a price."]),
   ("How to recognise one",["A partner button opens in a new tab and is marked rel=\"nofollow sponsored\". The guide says, near the offers, that the links are affiliate links, and it links to this page. Stories about tourism, travel, beaches, airports, transport, events and hotels end with a Travel in Cyprus row of partner links. Politics, crime and economy stories do not, unless the story is about travel. A short box appears only on a few practical pages about moving, expat life, banking or technology, and it links back to the full guide."]),
   ("What the guide does not do",["The text does not invent a premium, a coverage limit, a server count or a statistic. Where a figure is not in a source we cite, the guide says to read the current terms, because they change. A partner link is not a recommendation that a product is right for you, and it is not insurance, legal, tax or security advice. CyNews 24 is not affiliated with the companies, except that we may earn a commission if you buy through a link."]),
   ("Corrections",["If a guide is wrong, email cynews24@gmail.com with the page address and the correction. The editorial policy explains how corrections are handled."])]),
 "ru":dict(t="Раскрытие партнёрских ссылок",d="Как CyNews 24 использует партнёрские ссылки, на какие сервисы они ведут и чего эти ссылки не обещают.",
  sections=[
   ("Что такое партнёрская ссылка",["В некоторых практических материалах CyNews 24 есть ссылки на компании, чьи услуги могут пригодиться человеку, который живёт или путешествует за границей: международная медицинская страховка, туристическая eSIM, VPN, шифрованная почта или менеджер паролей. Если вы перейдёте по такой ссылке и купите услугу, компания может выплатить CyNews 24 комиссию. Нам вы отдельно ничего не доплачиваете. Цена, если она есть, — та, что указана на сайте самой компании."]),
   ("Где лежат адреса",["Все партнёрские адреса собраны в одном файле настроек, source/affiliates.json. Сайт публикует его как /assets/js/affiliates.js, и каждая партнёрская кнопка берёт адрес оттуда. Пока вместо настоящего адреса стоит заглушка вроде #AFFILIATE_GENKI. Заглушка ни в какой магазин не ведёт. В материалах названы Genki, Airalo, NordVPN, Surfshark, Proton (VPN, Pass и Mail) и 1Password. На некоторых практических страницах есть ссылки на Amazon.de. В разделе «Экономика» и в материалах о крипто есть ссылка на аппаратный кошелёк Trezor Safe 7. Этот адрес — запись trezor в том же файле. Кнопка не называет цену."]),
   ("Amazon",["Ссылки на Amazon — это поиск на Amazon.de, а не страница одного товара, и в них нет цены. Как участник партнёрской программы Amazon я зарабатываю на соответствующих покупках. В адресе главной страницы стоит метка cynews24-21, и тот же тег стоит в поиске. CyNews 24 не выдумывает код товара. Что показывает Amazon и сколько это стоит, видно на Amazon в момент, когда вы смотрите."]),
   ("Ссылки для путешествий",["Все адреса путеводителей лежат в одном файле, source/travel_affiliates.json. Кнопки Airalo, Yesim, Klook, Kiwitaxi, Welcome Pickups и Aviasales внутри путеводителей — ссылки Travelpayouts, метка 603740. Booking, GetYourGuide, DiscoverCars и SafetyWing пока остаются главными страницами компаний, пока эти программы не одобрены. Отдельный блок «Путешествие по Кипру» использует метку 808586: Localrent, Welcome Pickups, Kiwitaxi, Klook, Tiqets, Airalo и Aviasales. Кнопка помечена как sponsored. Ни одна из ссылок не называет цену."]),
   ("Как её узнать",["Партнёрская кнопка открывается в новой вкладке и помечена rel=\"nofollow sponsored\". Рядом с предложениями материал прямо говорит, что ссылки партнёрские, и ведёт на эту страницу. Материалы о туризме, путешествиях, пляжах, аэропортах, транспорте, событиях и отелях заканчиваются блоком «Путешествие по Кипру». В политике, криминале и экономике его нет, если сам материал не о путешествии. Короткий блок стоит только на нескольких практических страницах о переезде, жизни за границей, банках или технологиях и ведёт на полный материал."]),
   ("Чего материал не делает",["Текст не выдумывает премию, лимит покрытия, число серверов или статистику. Если цифры нет в источнике, на который мы ссылаемся, материал отправляет к действующим условиям: они меняются. Партнёрская ссылка не означает, что продукт вам подходит, и не является страховой, юридической, налоговой или иной профессиональной консультацией. CyNews 24 не связан с этими компаниями, кроме того, что мы можем получить комиссию, если вы купите услугу по ссылке."]),
   ("Поправки",["Если в материале ошибка, напишите на cynews24@gmail.com и укажите адрес страницы и поправку. Как обрабатываются поправки, сказано в редакционной политике."])]),
 "el":dict(t="Γνωστοποίηση συνεργατών",d="Πώς το CyNews 24 χρησιμοποιεί συνδέσμους συνεργατών, σε ποιες εταιρείες οδηγούν και τι δεν υπόσχονται.",
  sections=[
   ("Τι είναι ένας σύνδεσμος συνεργάτη",["Ορισμένοι πρακτικοί οδηγοί του CyNews 24 παραπέμπουν σε εταιρείες των οποίων τις υπηρεσίες μπορεί να χρησιμοποιήσει κάποιος που ζει ή ταξιδεύει στο εξωτερικό: διεθνή ασφάλιση υγείας, ταξιδιωτική eSIM, VPN, κρυπτογραφημένο email ή διαχειριστή κωδικών. Αν ακολουθήσετε έναν τέτοιο σύνδεσμο και αγοράσετε, η εταιρεία μπορεί να πληρώσει προμήθεια στο CyNews 24. Δεν πληρώνετε σε εμάς επιπλέον τέλος. Η τιμή, αν υπάρχει, είναι η τιμή στον ιστότοπο της εταιρείας."]),
   ("Πού βρίσκονται οι διευθύνσεις",["Κάθε διεύθυνση συνεργάτη φυλάσσεται σε ένα αρχείο ρυθμίσεων, το source/affiliates.json. Ο ιστότοπος το δημοσιεύει ως /assets/js/affiliates.js, και κάθε κουμπί συνεργάτη διαβάζει τη διεύθυνση από εκεί. Μέχρι να προστεθεί πραγματική διεύθυνση, η τιμή είναι θέση όπως #AFFILIATE_GENKI. Η θέση δεν οδηγεί σε κατάστημα. Οι συνεργάτες που ονομάζονται στους οδηγούς είναι οι Genki, Airalo, NordVPN, Surfshark, Proton (VPN, Pass και Mail) και 1Password. Ορισμένες πρακτικές σελίδες παραπέμπουν και στο Amazon.de. Η ενότητα Οικονομία, και τα άρθρα για κρυπτονομίσματα, παραπέμπουν και σε ένα hardware wallet Trezor Safe 7. Η διεύθυνση είναι η εγγραφή trezor στο ίδιο αρχείο. Το κουμπί δεν αναφέρει τιμή."]),
   ("Amazon",["Οι σύνδεσμοι της Amazon είναι αναζητήσεις στο Amazon.de, όχι σελίδα ενός προϊόντος, και δεν αναφέρουν τιμή. Ως συνεργάτης της Amazon, κερδίζω από αγορές που πληρούν τις προϋποθέσεις. Η διεύθυνση της αρχικής σελίδας έχει την ετικέτα cynews24-21, και την ίδια ετικέτα έχει η αναζήτηση. Το CyNews 24 δεν επινοεί κωδικό προϊόντος. Τι δείχνει η Amazon και πόσο κοστίζει φαίνεται στην Amazon τη στιγμή που κοιτάτε."]),
   ("Σύνδεσμοι για ταξίδια",["Κάθε διεύθυνση των οδηγών είναι σε ένα αρχείο, το source/travel_affiliates.json. Τα κουμπιά Airalo, Yesim, Klook, Kiwitaxi, Welcome Pickups και Aviasales μέσα στους οδηγούς είναι σύνδεσμοι Travelpayouts, δείκτης 603740. Οι Booking, GetYourGuide, DiscoverCars και SafetyWing μένουν η αρχική σελίδα της εταιρείας, μέχρι να εγκριθούν αυτά τα προγράμματα. Ξεχωριστή σειρά, Ταξίδι στην Κύπρο, χρησιμοποιεί τον δείκτη 808586: Localrent, Welcome Pickups, Kiwitaxi, Klook, Tiqets, Airalo και Aviasales. Το κουμπί σημειώνεται sponsored. Κανένας σύνδεσμος δεν αναφέρει τιμή."]),
   ("Πώς ξεχωρίζει",["Ένα κουμπί συνεργάτη ανοίγει σε νέα καρτέλα και φέρει rel=\"nofollow sponsored\". Ο οδηγός λέει, κοντά στις προσφορές, ότι οι σύνδεσμοι είναι συνεργατών και παραπέμπει σε αυτή τη σελίδα. Θέματα για τουρισμό, ταξίδια, παραλίες, αεροδρόμια, μεταφορές, εκδηλώσεις και ξενοδοχεία κλείνουν με τη σειρά Ταξίδι στην Κύπρο. Η πολιτική, το έγκλημα και η οικονομία δεν την έχουν, εκτός αν το ίδιο το θέμα είναι για ταξίδι. Ένα σύντομο πλαίσιο εμφανίζεται μόνο σε λίγες πρακτικές σελίδες για μετακόμιση, ζωή στο εξωτερικό, τράπεζες ή τεχνολογία και οδηγεί πίσω στον πλήρη οδηγό."]),
   ("Τι δεν κάνει ο οδηγός",["Το κείμενο δεν επινοεί ασφάλιστρο, όριο κάλυψης, αριθμό διακομιστών ή στατιστικό. Όπου ένας αριθμός δεν υπάρχει σε πηγή που αναφέρουμε, ο οδηγός στέλνει στους τρέχοντες όρους, γιατί αλλάζουν. Ένας σύνδεσμος συνεργάτη δεν σημαίνει ότι ένα προϊόν σας ταιριάζει και δεν είναι ασφαλιστική, νομική, φορολογική ή άλλη επαγγελματική συμβουλή. Το CyNews 24 δεν συνδέεται με τις εταιρείες, εκτός του ότι μπορεί να λάβει προμήθεια αν αγοράσετε μέσω συνδέσμου."]),
   ("Διορθώσεις",["Αν ένας οδηγός έχει λάθος, στείλτε email στο cynews24@gmail.com με τη διεύθυνση της σελίδας και τη διόρθωση. Η συντακτική πολιτική εξηγεί πώς χειριζόμαστε τις διορθώσεις."])]),
}
PRIVACY = {
 "en":dict(t="Privacy policy",d="How CyNews 24 handles the advertising contact form, analytics and cookies.",
  sections=[
   ("Who we are",["This policy covers the CyNews 24 website. The publisher is Anna. The site is based in Cyprus. Email: cynews24@gmail.com."]),
   ("Advertising contact form",["The Advertise & Contact page has a form that sends your message through FormSubmit (formsubmit.co) to 2877novosti@gmail.com. The fields are your name, company, email, phone if you provide one, the formats you select, an optional budget range, your message and your consent. We use those details only to reply to that enquiry. FormSubmit processes the submission in order to deliver the email. We do not sell the details and we do not add them to a marketing list."]),
   ("Property consultation and Advertise",["The property consultation form, on articles and on its own page, the Advertise page, and the enquiry form on a property listing send what you type through FormSubmit to 2877novosti@gmail.com. The fields are the ones on that form, including your consent. We use them only to reply to that enquiry. We do not sell them and we do not add them to a marketing list."]),
   ("Analytics",["The site does not use Google Analytics. It loads Google AdSense (ca-pub-1547877294743851) so Google can show ads. Advertising and analytics storage stay denied until you accept cookies in the banner. If you accept, AdSense may receive technical data such as the page address and a cookie identifier. If you reject, that storage stays denied. Cookie settings in the footer opens the choice again."]),
   ("Cookies",["CyNews 24 does not set its own cookies. The accept or reject choice is stored in this browser's local storage under the name cynews24-consent, which is not a cookie. Google Consent Mode starts denied, before the AdSense script and before any analytics tag. AdSense may set advertising cookies only after you accept. The language chooser on the front page links to the Russian, English and Greek editions. It does not store a cookie. The cookie policy has the full account. If you follow a link to another site, that site has its own policy."]),
   ("Email",["If you email cynews24@gmail.com, we use the message to answer you or to correct a story. We keep it for as long as that purpose requires."]),
   ("Changes",["If this policy changes, the new text replaces this page."])]),
 "ru":dict(t="Политика конфиденциальности",d="Как CyNews 24 обрабатывает форму рекламного обращения, аналитику и файлы cookie.",
  sections=[
   ("Кто мы",["Эта политика относится к сайту CyNews 24. Издатель — Анна. Сайт базируется на Кипре. Эл. почта: cynews24@gmail.com."]),
   ("Форма рекламного обращения",["На странице «Реклама и контакты» есть форма. Она отправляет сообщение через FormSubmit (formsubmit.co) на 2877novosti@gmail.com. Поля: имя, компания, эл. почта, телефон, если вы его указали, выбранные форматы, необязательный диапазон бюджета, сообщение и согласие. Мы используем эти сведения только чтобы ответить на это обращение. FormSubmit обрабатывает отправку, чтобы доставить письмо. Мы не продаём эти сведения и не добавляем их в маркетинговый список."]),
   ("Консультация по недвижимости и «Реклама»",["Форма консультации по недвижимости — в материалах и на отдельной странице, — страница «Реклама» и форма заявки в объявлении отправляют введённые данные через FormSubmit на 2877novosti@gmail.com. Поля — те, что на форме, включая согласие. Мы используем их только чтобы ответить на это обращение. Мы не продаём их и не добавляем в маркетинговый список."]),
   ("Аналитика",["Сайт не использует Google Analytics. Он подключает Google AdSense (ca-pub-1547877294743851), чтобы Google мог показывать объявления. Хранение данных для рекламы и аналитики запрещено, пока вы не примите cookie в баннере. Если вы принимаете, AdSense может получать технические данные, например адрес страницы и идентификатор cookie. Если вы отклоняете, такое хранение остаётся запрещённым. «Настройки cookie» в подвале снова открывают выбор."]),
   ("Файлы cookie",["CyNews 24 не ставит собственные cookie. Выбор «принять» или «отклонить» хранится в local storage этого браузера под именем cynews24-consent — это не cookie. Google Consent Mode с самого начала запрещает хранение, ещё до скрипта AdSense и до любого тега аналитики. AdSense может ставить рекламные cookie только после вашего согласия. Выбор языка на первой странице ведёт на русскую, английскую и греческую версии. Cookie при этом не сохраняется. Подробности — в политике cookie. Если вы переходите по ссылке на другой сайт, у того сайта своя политика."]),
   ("Почта",["Если вы пишете на cynews24@gmail.com, мы используем письмо, чтобы ответить или исправить материал. Мы храним его, пока это нужно для этой цели."]),
   ("Изменения",["Если политика изменится, новый текст заменит эту страницу."])]),
 "el":dict(t="Πολιτική απορρήτου",d="Πώς το CyNews 24 χειρίζεται τη φόρμα διαφημιστικής επικοινωνίας, τα αναλυτικά και τα cookies.",
  sections=[
   ("Ποιοι είμαστε",["Αυτή η πολιτική καλύπτει τον ιστότοπο CyNews 24. Εκδότρια είναι η Άννα. Ο ιστότοπος έχει έδρα την Κύπρο. Email: cynews24@gmail.com."]),
   ("Φόρμα διαφημιστικής επικοινωνίας",["Η σελίδα Διαφήμιση & Επικοινωνία έχει φόρμα που στέλνει το μήνυμά σας μέσω του FormSubmit (formsubmit.co) στο 2877novosti@gmail.com. Τα πεδία είναι το όνομα, η εταιρεία, το email, το τηλέφωνο αν το δώσετε, οι μορφές που επιλέγετε, ένα προαιρετικό εύρος προϋπολογισμού, το μήνυμα και η συγκατάθεσή σας. Χρησιμοποιούμε αυτά τα στοιχεία μόνο για να απαντήσουμε σε εκείνο το αίτημα. Το FormSubmit επεξεργάζεται την υποβολή για να παραδώσει το email. Δεν πουλάμε τα στοιχεία και δεν τα προσθέτουμε σε λίστα μάρκετινγκ."]),
   ("Συμβουλευτική ακινήτων και Διαφήμιση",["Η φόρμα συμβουλευτικής ακινήτων, στα άρθρα και στη δική της σελίδα, η σελίδα Διαφήμιση και η φόρμα σε μια αγγελία ακινήτου στέλνουν όσα γράφετε μέσω FormSubmit στο 2877novosti@gmail.com. Τα πεδία είναι όσα έχει η φόρμα, μαζί με τη συγκατάθεση. Τα χρησιμοποιούμε μόνο για να απαντήσουμε σε εκείνο το αίτημα. Δεν τα πουλάμε και δεν τα προσθέτουμε σε λίστα μάρκετινγκ."]),
   ("Αναλυτικά",["Ο ιστότοπος δεν χρησιμοποιεί Google Analytics. Φορτώνει το Google AdSense (ca-pub-1547877294743851) ώστε η Google να εμφανίζει διαφημίσεις. Η αποθήκευση για διαφήμιση και αναλυτικά μένει σε άρνηση μέχρι να αποδεχτείτε τα cookies στο πλαίσιο. Αν αποδεχτείτε, το AdSense μπορεί να λαμβάνει τεχνικά δεδομένα, όπως τη διεύθυνση της σελίδας και ένα αναγνωριστικό cookie. Αν απορρίψετε, αυτή η αποθήκευση μένει σε άρνηση. Οι «Ρυθμίσεις cookies» στο υποσέλιδο ανοίγουν ξανά την επιλογή."]),
   ("Cookies",["Το CyNews 24 δεν τοποθετεί δικά του cookies. Η επιλογή αποδοχής ή απόρριψης αποθηκεύεται στο local storage αυτού του προγράμματος περιήγησης με το όνομα cynews24-consent και δεν είναι cookie. Το Google Consent Mode ξεκινά σε άρνηση, πριν από το script του AdSense και πριν από οποιαδήποτε ετικέτα αναλυτικών. Το AdSense μπορεί να τοποθετεί διαφημιστικά cookies μόνο αφού αποδεχτείτε. Η επιλογή γλώσσας στην πρώτη σελίδα οδηγεί στις ρωσικές, αγγλικές και ελληνικές εκδόσεις. Δεν αποθηκεύει cookie. Η πλήρης περιγραφή είναι στην πολιτική cookies. Αν ακολουθήσετε σύνδεσμο προς άλλον ιστότοπο, εκείνος έχει τη δική του πολιτική."]),
   ("Email",["Αν στείλετε email στο cynews24@gmail.com, χρησιμοποιούμε το μήνυμα για να απαντήσουμε ή για να διορθώσουμε ένα άρθρο. Το κρατάμε για όσο χρειάζεται αυτός ο σκοπός."]),
   ("Αλλαγές",["Αν η πολιτική αλλάξει, το νέο κείμενο αντικαθιστά αυτή τη σελίδα."])])}
# Analytics paragraphs below are the text used while GA4_ID is empty.
# cookies_for() replaces that section when a measurement ID is set.
COOKIES = {
 "en":dict(t="Cookie policy",d="How CyNews 24 asks before advertising or analytics cookies are stored, and how to change that choice.",
  sections=[
   ("Who we are",["This page covers cookies and similar storage on the CyNews 24 website. The publisher is Anna. The site is based in Cyprus. Email: cynews24@gmail.com."]),
   ("Your choice",["A banner offers Accept and Reject. Until you choose, Google Consent Mode keeps ad storage, ad user data, ad personalisation and analytics storage denied. That default is set in the page before the Google AdSense script and before any Google tag. Accept grants those four storage types. Reject leaves them denied. The choice is saved in local storage as cynews24-consent on this browser. It is not a cookie and it is not sent to the server."]),
   ("Advertising",["The pages load Google AdSense, publisher ca-pub-1547877294743851, so Google can show ads. If you accept, Google may set advertising cookies and use them to measure and personalise ads. If you reject, AdSense may still show an ad that does not use those cookies. What Google stores is described in Google's cookie policy."]),
   ("Analytics",["The site does not use Google Analytics, so it does not set analytics cookies. Analytics storage stays denied. If a measurement ID is configured later, analytics cookies are stored only after you accept."]),
   ("What this site does not store",["CyNews 24 does not set its own cookies. The language chooser on the front page links to the Russian, English and Greek editions. It does not store a cookie. The advertising contact form does not set a cookie on this site."]),
   ("Changing your mind",["Cookie settings in the footer opens the banner again. You can also block or delete cookies in the browser. Clearing site data removes the saved choice, and the banner is shown again."]),
   ("Contact",["Questions about this policy: cynews24@gmail.com. The supervisory authority in Cyprus is the Commissioner for Personal Data Protection."])]),
 "ru":dict(t="Политика cookie",d="Как CyNews 24 спрашивает согласие до сохранения рекламных и аналитических cookie и как изменить этот выбор.",
  sections=[
   ("Кто мы",["Эта страница — о cookie и похожем хранении на сайте CyNews 24. Издатель — Анна. Сайт базируется на Кипре. Эл. почта: cynews24@gmail.com."]),
   ("Ваш выбор",["Баннер предлагает «Принять» и «Отклонить». Пока вы не выбрали, Google Consent Mode запрещает хранение для рекламы, пользовательских данных рекламы, персонализации рекламы и аналитики. Этот запрет записан в странице до скрипта Google AdSense и до любого тега Google. «Принять» разрешает эти четыре вида хранения. «Отклонить» оставляет запрет. Выбор сохраняется в local storage этого браузера как cynews24-consent. Это не cookie, и на сервер он не отправляется."]),
   ("Реклама",["Страницы подключают Google AdSense, издатель ca-pub-1547877294743851, чтобы Google мог показывать объявления. Если вы принимаете, Google может ставить рекламные cookie и использовать их для измерения и персонализации рекламы. Если вы отклоняете, AdSense может показать объявление, которое эти cookie не использует. Что хранит Google, описано в политике cookie Google."]),
   ("Аналитика",["Сайт не использует Google Analytics и не ставит аналитические cookie. Хранение для аналитики остаётся запрещённым. Если идентификатор измерения появится позже, аналитические cookie сохраняются только после вашего согласия."]),
   ("Чего сайт не хранит",["CyNews 24 не ставит собственные cookie. Выбор языка на первой странице ведёт на русскую, английскую и греческую версии. Cookie при этом не сохраняется. Форма рекламного обращения не ставит cookie на этом сайте."]),
   ("Как изменить выбор",["«Настройки cookie» в подвале снова открывают баннер. Cookie можно также запретить или удалить в браузере. Очистка данных сайта удаляет сохранённый выбор, и баннер показывается снова."]),
   ("Контакты",["Вопросы об этой политике: cynews24@gmail.com. Надзорный орган на Кипре — Комиссар по защите персональных данных."])]),
 "el":dict(t="Πολιτική cookies",d="Πώς το CyNews 24 ζητά συγκατάθεση πριν αποθηκευτούν διαφημιστικά ή αναλυτικά cookies και πώς αλλάζετε την επιλογή.",
  sections=[
   ("Ποιοι είμαστε",["Αυτή η σελίδα καλύπτει τα cookies και παρόμοια αποθήκευση στον ιστότοπο CyNews 24. Εκδότρια είναι η Άννα. Ο ιστότοπος έχει έδρα την Κύπρο. Email: cynews24@gmail.com."]),
   ("Η επιλογή σας",["Ένα πλαίσιο προσφέρει Αποδοχή και Απόρριψη. Μέχρι να επιλέξετε, το Google Consent Mode κρατά σε άρνηση την αποθήκευση διαφημίσεων, τα δεδομένα χρήστη για διαφημίσεις, την εξατομίκευση διαφημίσεων και την αποθήκευση αναλυτικών. Η προεπιλογή μπαίνει στη σελίδα πριν από το script του Google AdSense και πριν από οποιαδήποτε ετικέτα Google. Η Αποδοχή επιτρέπει αυτά τα τέσσερα είδη αποθήκευσης. Η Απόρριψη τα αφήνει σε άρνηση. Η επιλογή αποθηκεύεται στο local storage αυτού του προγράμματος περιήγησης ως cynews24-consent. Δεν είναι cookie και δεν στέλνεται στον διακομιστή."]),
   ("Διαφήμιση",["Οι σελίδες φορτώνουν το Google AdSense, εκδότη ca-pub-1547877294743851, ώστε η Google να εμφανίζει διαφημίσεις. Αν αποδεχτείτε, η Google μπορεί να τοποθετεί διαφημιστικά cookies και να τα χρησιμοποιεί για μέτρηση και εξατομίκευση διαφημίσεων. Αν απορρίψετε, το AdSense μπορεί ακόμη να εμφανίσει διαφήμιση που δεν χρησιμοποιεί αυτά τα cookies. Τι αποθηκεύει η Google περιγράφεται στην πολιτική cookies της Google."]),
   ("Αναλυτικά",["Ο ιστότοπος δεν χρησιμοποιεί Google Analytics, άρα δεν τοποθετεί αναλυτικά cookies. Η αποθήκευση αναλυτικών μένει σε άρνηση. Αν αργότερα οριστεί αναγνωριστικό μέτρησης, τα αναλυτικά cookies αποθηκεύονται μόνο αφού αποδεχτείτε."]),
   ("Τι δεν αποθηκεύουμε",["Το CyNews 24 δεν τοποθετεί δικά του cookies. Η επιλογή γλώσσας στην πρώτη σελίδα οδηγεί στις ρωσικές, αγγλικές και ελληνικές εκδόσεις. Δεν αποθηκεύει cookie. Η φόρμα διαφημιστικής επικοινωνίας δεν τοποθετεί cookie σε αυτόν τον ιστότοπο."]),
   ("Αλλαγή επιλογής",["Οι «Ρυθμίσεις cookies» στο υποσέλιδο ανοίγουν ξανά το πλαίσιο. Μπορείτε επίσης να μπλοκάρετε ή να διαγράψετε cookies στο πρόγραμμα περιήγησης. Η εκκαθάριση δεδομένων του ιστότοπου αφαιρεί την αποθηκευμένη επιλογή και το πλαίσιο εμφανίζεται ξανά."]),
   ("Επικοινωνία",["Ερωτήματα για αυτή την πολιτική: cynews24@gmail.com. Η εποπτική αρχή στην Κύπρο είναι ο Επίτροπος Προστασίας Δεδομένων Προσωπικού Χαρακτήρα."])])}
e=html.escape
def href(path):
    """Site path (/en/) → path under the project subpath (/cynews24/en/)."""
    if not path.startswith("/"):
        path = "/" + path
    return f"{PREFIX}{path}" if PREFIX else path
def url(l,*p): return href("/"+"/".join([l]+list(p))+"/")
def abs_(path): return BASE+path
def trunc(s,n=158):
    if len(s)<=n: return s
    c=s[:n-1]; c=c[:c.rfind(" ")] if " " in c else c
    return c.rstrip(",;:—- ")+"…"

# ---------- photos ----------
FONT_BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def load_credits():
    p=os.path.join(HERE,"credits.json")
    if not os.path.exists(p): return {}
    with open(p,encoding="utf8") as f: return json.load(f)
CREDITS=load_credits()
# One shared illustration per event type. Used only when the event has no
# photograph of its own. Keys are entries in credits.json.
EV_FALLBACK={
 "theatre":"ev-fallback-theatre",
 "cinema":"ev-fallback-cinema",
 "concert":"ev-fallback-concert",
 "festival":"ev-fallback-festival",
 "fair":"ev-fallback-fair",
 "exhibition":"ev-fallback-exhibition",
 "kids":"ev-fallback-kids",
 "sport":"ev-fallback-sport",
}
def credit_for(s):
    """Photo credit: from the article itself for CMS uploads, otherwise from credits.json."""
    if "upload" in s:
        c=s.get("credit") or {}
        return c if c.get("author") else None
    return CREDITS.get(s["img"])
def cover_crop(im, tw, th, focus=(0.5,0.5)):
    im=im.convert("RGB"); sw,sh=im.size
    tr=tw/th; sr=sw/sh
    if sr>tr:
        nw=int(round(sh*tr)); left=int(round((sw-nw)*focus[0])); left=max(0,min(left,sw-nw))
        im=im.crop((left,0,left+nw,sh))
    else:
        nh=int(round(sw/tr)); top=int(round((sh-nh)*focus[1])); top=max(0,min(top,sh-nh))
        im=im.crop((0,top,sw,top+nh))
    return im.resize((tw,th),Image.LANCZOS)
def wordmark(img_w):
    """Semi-transparent CyNews 24 badge, matching the dark/orange header."""
    h=max(26,int(round(img_w*0.042)))
    pad=int(h*0.38); gap=int(h*0.18)
    font=ImageFont.truetype(FONT_BOLD,int(h*0.56))
    probe=ImageDraw.Draw(Image.new("RGB",(1,1)))
    def box(text):
        b=probe.textbbox((0,0),text,font=font); return b[2]-b[0], b[3]-b[1]
    tw1,th1=box("CyNews"); tw2,th2=box("24")
    box_w=tw2+int(h*0.46); box_h=int(h*0.72)
    bw=pad+tw1+gap+box_w+pad
    badge=Image.new("RGBA",(bw,h),(0,0,0,0)); d=ImageDraw.Draw(badge)
    d.rounded_rectangle((0,0,bw-1,h-1),radius=max(3,h//6),fill=(17,24,39,168))
    d.text((pad,(h-th1)/2-1),"CyNews",font=font,fill=(255,255,255,235))
    bx=pad+tw1+gap; by=(h-box_h)//2
    d.rounded_rectangle((bx,by,bx+box_w,by+box_h),radius=max(2,h//10),fill=(196,87,26,214))
    d.text((bx+(box_w-tw2)/2, by+(box_h-th2)/2-1),"24",font=font,fill=(255,255,255,245))
    return badge
def watermark(im):
    im=im.convert("RGBA"); badge=wordmark(im.width)
    m=max(8,int(im.width*0.016))
    im.paste(badge,(im.width-badge.width-m, im.height-badge.height-m),badge)
    return im.convert("RGB")
def photo_caption(s,l):
    c=credit_for(s)
    if not c: return "" if "upload" in s else UI[l]["illus"]
    label={"en":"Photo","ru":"Фото","el":"Φωτογραφία"}[l]
    if "upload" in s and not (c.get("page") and c.get("source") and c.get("license") and c.get("license_url")):
        bits=[e(c["author"])]
        if c.get("source"): bits.append(f'<a href="{e(c["page"])}">{e(c["source"])}</a>' if c.get("page") else e(c["source"]))
        out=f'{label}: '+" / ".join(bits)
        if c.get("license"): out+=", "+(f'<a href="{e(c["license_url"])}">{e(c["license"])}</a>' if c.get("license_url") else e(c["license"]))
        return out
    return (f'{label}: {e(c["author"])} / '
            f'<a href="{e(c["page"])}">{e(c["source"])}</a>, '
            f'<a href="{e(c["license_url"])}">{e(c["license"])}</a>')
# Photographs already published below 1200px stay. A new article has to clear that width.
KNOWN_SMALL_LEADS=frozenset({
 "avakoum-monastery-receipts",
 "christodoulides-erhurman-24-november",
 "christodoulides-erhurman-meeting",
 "christodoulides-property-witness",
 "cyprus-copper-hellenic-cuprum",
 "cyprus-students-uk-home-fees",
 "helleniq-energy-cyprus-gas",
 "limassol-funeral-schoolgirl-kakopetria",
 "mafia-state-tax-commissioner-dossier",
 "presidential-election-spending-cap",
})
FULL_LEAD=(1200,675)
FULL_OG=(1200,630)
FULL_SMALL=(600,338)
_GEO={}
def story_photo_path(s):
    """Source file for the lead photograph. Empty when the page uses the generated card."""
    if "upload" in s:
        return s.get("upload") or ""
    c=CREDITS.get(s["img"])
    if c:
        return os.path.join(HERE,"photos",c["file"])
    p=os.path.join(SRC,f"{s['img']}.jpg")
    return p if os.path.exists(p) else ""
def _native_16x9(sw,sh):
    """Largest 16:9 crop that fits inside the file. Never rounds up past the file."""
    if sw<=0 or sh<=0: return 0,0
    tr=16/9
    if sw/sh>tr:
        return max(int(sh*tr),1), sh
    return sw, max(int(sw/tr),1)
def lead_geometry(s):
    """Pixel sizes we actually publish. A small photograph is not enlarged."""
    # Property cards pass an image stub with no page address. Geometry follows the file.
    key=s["slug"] if s.get("slug") else "img:"+s["img"]
    if key in _GEO: return _GEO[key]
    path=story_photo_path(s)
    if not path or not os.path.exists(path):
        geo={"placeholder":True,"native":(0,0),"native_lead":(0,0),"lead":FULL_LEAD,"og":FULL_OG,"small":FULL_SMALL}
    else:
        with Image.open(path) as im:
            sw,sh=im.size
        nw,nh=_native_16x9(sw,sh)
        if nw>=1200:
            geo={"placeholder":False,"native":(sw,sh),"native_lead":(nw,nh),"lead":FULL_LEAD,"og":FULL_OG,"small":FULL_SMALL}
        else:
            og_h=min(nh, int(nw*630/1200)) or nh
            small=(nw,nh) if nw<=600 else (600, max(1, int(round(600*nh/nw))))
            geo={"placeholder":False,"native":(sw,sh),"native_lead":(nw,nh),"lead":(nw,nh),"og":(nw,og_h),"small":small}
    _GEO[key]=geo
    return geo
def og_image(s):
    w,h=lead_geometry(s)["og"]
    return f'/assets/img/{s["img"]}-og.jpg', w, h
def small_lead_stories():
    """Articles whose own photograph cannot fill a 1200px-wide 16:9 frame."""
    return [s for s in STORIES if lead_geometry(s)["placeholder"] or lead_geometry(s)["native_lead"][0]<1200]
def lead_size_error(slug, native_lead_width, placeholder=False):
    if placeholder or native_lead_width<1200:
        if slug not in KNOWN_SMALL_LEADS:
            if placeholder:
                return f"{slug}: no lead photograph. New articles need a photo at least 1200px wide (16:9)."
            return (f"{slug}: the lead photograph is {native_lead_width}px wide. "
                    "New articles need a photo at least 1200px wide (16:9). The build will not replace it.")
    return ""
def enforce_lead_images():
    bad=[]
    for s in small_lead_stories():
        geo=lead_geometry(s)
        err=lead_size_error(s["slug"], geo["native_lead"][0], geo["placeholder"])
        if err: bad.append(err)
    if bad:
        raise SystemExit("Lead image is too small for a new article:\n"+"\n".join(bad))
    return small_lead_stories()
def image_ld(s):
    c=credit_for(s)
    w,h=lead_geometry(s)["lead"]
    url=abs_(f"/assets/img/{s['img']}-1200.webp")
    obj={"@type":"ImageObject","url":url,"contentUrl":url,"width":w,"height":h}
    if c:
        credit=", ".join(x for x in (" / ".join(x for x in (c["author"],c.get("source")) if x),c.get("license")) if x)
        obj.update({"creditText":credit,"copyrightNotice":credit})
        if c.get("license_url"): obj["license"]=c["license_url"]
        if c.get("page"): obj["acquireLicensePage"]=c["page"]
        obj["creator"]={"@type":"Person","name":c["author"]}
    return obj
def write_credits_md():
    lines=["# Photo credits","","Story photographs are openly licensed pictures. The generator crops each one to 16:9, resizes it and adds a CyNews 24 watermark. Adaptations of CC BY-SA photographs stay under the same licence.","","| Image | What it shows | Author | Licence | Original |","|---|---|---|---|---|"]
    seen=set()
    for s in STORIES:
        # Two stories may share one photograph. List that photograph once.
        if s["img"] in seen:
            continue
        seen.add(s["img"])
        c=credit_for(s)
        if c and "upload" in s:
            lic=f'[{c.get("license") or "—"}]({c["license_url"]})' if c.get("license_url") else (c.get("license") or "—")
            orig=f'[{c.get("source") or "link"}]({c["page"]})' if c.get("page") else (c.get("source") or "—")
            lines.append(f'| `{s["img"]}` | {s["alt"]["en"]} | {c["author"]} | {lic} | {orig} |')
            continue
        if not c:
            lines.append(f'| `{s["img"]}` | Original illustration kept | — | — | — |')
            continue
        lines.append(f'| `{s["img"]}` | {c.get("depicts","")} | {c["author"]} | [{c["license"]}]({c["license_url"]}) | [{c["source"]}]({c["page"]}) |')
    lines += ["","## Event photographs","","| Image | Author | Licence | Original |","|---|---|---|---|"]
    for key,p in EV_PHOTOS.items():
        lines.append(f'| `events/{key}` | {p["author"]} | [{p["license"]}]({p["license_url"]}) | [{p["source"]}]({p["page"]}) |')
    lines += ["","## Event category fallbacks","","Shown when an event has no photograph of its own. These pictures are not used as the event image in structured data.","","| Category | Image | Author | Licence | Original |","|---|---|---|---|---|"]
    for kind,key in EV_FALLBACK.items():
        p=CREDITS[key]
        lines.append(f'| {kind} | `events/{key}` | {p["author"]} | [{p["license"]}]({p["license_url"]}) | [{p["source"]}]({p["page"]}) |')
    lines += ["","CC BY-SA files: the cropped, resized and watermarked images published with the site are adaptations and remain under the same CC BY-SA licence as the original.",""]
    text="\n".join(lines)+"\n"
    open(os.path.join(OUT,"CREDITS.md"),"w",encoding="utf8").write(text)

# ---------- assets ----------
def placeholder_image(s):
    """1200x675 dark card with the CyNews 24 wordmark and section name, for articles without a photo."""
    im=Image.new("RGB",(1200,675),(17,24,39)); d=ImageDraw.Draw(im)
    f1=ImageFont.truetype(FONT_BOLD,150); f2=ImageFont.truetype(FONT_BOLD,44)
    d.text((600,300),"CyNews",font=f1,fill=(255,255,255),anchor="mm")
    d.rectangle((420,390,780,470),fill=(196,87,26)); d.text((600,430),"24",font=ImageFont.truetype(FONT_BOLD,64),fill=(255,255,255),anchor="mm")
    d.text((600,560),CATN["en"][s["cat"]].upper(),font=f2,fill=(200,205,213),anchor="mm")
    return im
def save_lead_files(s, plain, d, mark=True):
    """Write the lead, the smaller srcset file and the social image. plain is unwatermarked 16:9."""
    geo=lead_geometry(s)
    lw,lh=geo["lead"]
    name=s["img"]
    def stamp(im):
        return watermark(im) if mark else im
    stamp(plain).save(f"{d}/{name}-1200.webp","WEBP",quality=78,method=6)
    sw,sh=geo["small"]
    thumb=plain if (sw,sh)==(lw,lh) else plain.resize((sw,sh),Image.LANCZOS)
    stamp(thumb).save(f"{d}/{name}-600.webp","WEBP",quality=76,method=6)
    if (lw,lh)==FULL_LEAD:
        og=plain.crop((0,22,1200,652))
    else:
        ow,oh=geo["og"]
        top=max(0,(lh-oh)//2)
        og=plain.crop((0,top,lw,min(lh,top+oh)))
    stamp(og).save(f"{d}/{name}-og.jpg","JPEG",quality=82,optimize=True,progressive=True)
def build_assets():
    d=OUT+"/assets/img"; os.makedirs(d,exist_ok=True)
    seen=set()
    for s in STORIES:
        # Two stories can share one photograph. Write that file once.
        if s["img"] in seen: continue
        seen.add(s["img"])
        geo=lead_geometry(s)
        if geo["placeholder"]:
            plain=placeholder_image(s)
            save_lead_files(s, plain, d, mark=False)
            continue
        c=None if "upload" in s else CREDITS.get(s["img"])
        focus=tuple(c.get("focus",[0.5,0.5])) if c else (0.5,0.5)
        lw,lh=geo["lead"]
        with Image.open(story_photo_path(s)) as src:
            plain=cover_crop(src,lw,lh,focus)
        save_lead_files(s, plain, d)
    # logo
    W=512; lg=Image.new("RGB",(W,W),(17,24,39)); dr=ImageDraw.Draw(lg)
    f1=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",150)
    f2=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",120)
    dr.text((W/2,200),"CyNews",font=f1,fill=(255,255,255),anchor="mm")
    dr.rectangle((86,300,W-86,420),fill=(196,87,26))
    dr.text((W/2,362),"24",font=f2,fill=(255,255,255),anchor="mm")
    lg.save(OUT+"/assets/logo-512.png","PNG",optimize=True)
    lg.resize((192,192)).save(OUT+"/assets/icon-192.png","PNG",optimize=True)
    # default og
    og=Image.new("RGB",(1200,630),(17,24,39)); d2=ImageDraw.Draw(og)
    f3=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",190)
    d2.text((120,260),"CyNews",font=f3,fill=(255,255,255),anchor="lm")
    d2.rectangle((120+620,170,1080,350),fill=(196,87,26)); d2.text((960-20,260),"24",font=f3,fill=(255,255,255),anchor="mm")
    f4=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",46)
    d2.text((120,470),"Cyprus news · Новости Кипра · Ειδήσεις Κύπρου",font=f4,fill=(220,226,235),anchor="lm")
    og.save(OUT+"/assets/og-default.jpg","JPEG",quality=85,optimize=True)
    open(OUT+"/favicon.svg","w").write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="10" fill="#111827"/><rect x="8" y="36" width="48" height="18" fill="#c4571a"/><text x="32" y="30" font-family="Arial,sans-serif" font-weight="700" font-size="22" fill="#fff" text-anchor="middle">Cy</text><text x="32" y="51" font-family="Arial,sans-serif" font-weight="700" font-size="16" fill="#fff" text-anchor="middle">24</text></svg>')
    shutil.copy(OUT+"/assets/icon-192.png",OUT+"/apple-touch-icon.png")

CSS = r""":root{--ink:#141414;--mut:#5a5f66;--line:#dcdfe3;--acc:#c4571a;--dark:#111827;--bg:#fff;--soft:#f5f6f7}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans",sans-serif;color:var(--ink);background:var(--bg)}
a{color:inherit;text-decoration:none}a:hover h2,a:hover h3,a:hover .t{text-decoration:underline}
img{max-width:100%;height:auto;display:block}
.skip{position:absolute;left:-999px}.skip:focus{left:8px;top:8px;background:#fff;padding:8px;z-index:99}
.wrap{max-width:1180px;margin:0 auto;padding:0 16px}
.top{background:var(--dark);color:#fff}.top .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:56px;flex-wrap:wrap}
.logo{display:flex;align-items:stretch;font-weight:800;font-size:26px;letter-spacing:-.5px;line-height:1}
.logo b{padding:8px 10px;color:#fff}.logo i{font-style:normal;background:var(--acc);padding:8px 10px;color:#fff}
.tr{display:flex;align-items:center;gap:16px;font-size:13px}
.date{color:#c8cdd5}
.lang{display:flex;gap:2px}.lang a{padding:4px 9px;border:1px solid #3b4556;font-weight:700;font-size:12px;letter-spacing:.5px}.lang a[aria-current=true]{background:#fff;color:var(--dark);border-color:#fff}.lang a:hover{background:#2a3446}.lang a[aria-current=true]:hover{background:#fff}
.tr .tg,.tr .threads{display:inline-flex;align-items:center;gap:6px;background:var(--acc);color:#fff;padding:5px 10px;font-weight:800;font-size:12px;letter-spacing:.4px}
.tr .tg:hover,.tr .threads:hover{background:#fff;color:var(--dark)}
.tr .tg svg,.tr .threads svg{display:block}
nav.cats{border-bottom:1px solid var(--line);background:#fff;position:sticky;top:0;z-index:20}
nav.cats ul{list-style:none;margin:0;padding:0;display:flex;overflow-x:auto;scrollbar-width:none}
nav.cats li a{display:block;padding:13px 14px;font-weight:700;font-size:15px;white-space:nowrap;border-bottom:4px solid transparent}
nav.cats li a:hover{border-color:var(--ink)}nav.cats li a[aria-current=page]{border-color:var(--acc)}
.subnav{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 18px}
.subnav a{display:inline-block;padding:6px 12px;border:1px solid var(--line);border-radius:999px;font-weight:700;font-size:14px;background:#fff}
.subnav a[aria-current=page]{background:var(--ink);color:#fff;border-color:var(--ink)}
.intro{max-width:760px;margin:0 0 8px}
.intro p{margin:0 0 12px;font-size:17px;line-height:1.55}
.tagline{font-size:13px;color:var(--mut);padding:10px 0 0}
h1.sec{font-size:28px;margin:18px 0 14px;border-top:4px solid var(--ink);padding-top:8px;letter-spacing:-.3px}
.lead{display:grid;grid-template-columns:1.9fr 1fr;gap:24px;margin:8px 0 28px}
.card .img{display:block;background:var(--soft);overflow:hidden}.card .img img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.grid .card{content-visibility:auto;contain-intrinsic-size:auto 360px}
.lead .big h2{font-size:34px;line-height:1.12;margin:12px 0 8px;letter-spacing:-.6px}
.lead .big p{font-size:18px;color:#2b2f35;margin:0 0 8px}
.cat{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:var(--acc)}
.meta{font-size:13px;color:var(--mut)}
.side{display:flex;flex-direction:column}
.side .card{display:grid;grid-template-columns:128px 1fr;gap:12px;padding:12px 0;border-bottom:1px solid var(--line)}.side .card:first-child{padding-top:0}.side .card:last-child{border:0}
.side h3{font-size:16px;line-height:1.25;margin:2px 0 4px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:22px}
.grid .card h3{font-size:18px;line-height:1.22;margin:10px 0 6px}.grid .card p{margin:0 0 6px;font-size:14.5px;color:#2b2f35}
.g3{grid-template-columns:repeat(3,1fr)}
.band{background:var(--soft);margin:30px 0;padding:6px 0 26px}
.cols{display:grid;grid-template-columns:3fr 1fr;gap:32px}
ol.latest{list-style:none;margin:0;padding:0}ol.latest li{padding:12px 0;border-bottom:1px solid var(--line)}ol.latest a{font-weight:700;font-size:15.5px;line-height:1.3;display:block}
.latest h2{font-size:20px;border-top:4px solid var(--ink);padding-top:8px;margin:0 0 6px}
.pick{background:var(--soft);border-left:4px solid var(--acc);padding:12px 14px;margin:16px 0 0}
.pick h3{font-size:15px;line-height:1.35;margin:0 0 8px}
.pick p{margin:0 0 12px;font-size:14.5px;line-height:1.45}
.pick a{display:inline-block;background:var(--dark);color:#fff;font-weight:800;padding:8px 12px;font-size:14px;max-width:100%}
.pick a:hover{background:var(--acc)}
.crumb{font-size:13px;color:var(--mut);margin:18px 0 8px}.crumb a{text-decoration:underline}
article.a{max-width:760px;margin:0 auto}
article.a h1{font-size:40px;line-height:1.1;letter-spacing:-.8px;margin:6px 0 12px}
.dek{font-size:20px;line-height:1.4;font-weight:600;color:#23272d;margin:0 0 14px}
.by{font-size:14px;color:var(--mut);border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:10px 0;margin-bottom:18px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.by .who{font-weight:700;color:var(--ink)}
.by .when{display:flex;flex-direction:column;align-items:flex-end;gap:2px;text-align:right}
.by time{display:block}
figure{margin:0 0 22px}figcaption{font-size:13px;color:var(--mut);padding-top:6px}figcaption a{color:#0b57b0;text-decoration:underline}
.body p{font-size:18px;line-height:1.65;margin:0 0 18px;overflow-wrap:anywhere}.body a{color:#0b57b0;text-decoration:underline}
.body h2{font-size:26px;line-height:1.25;letter-spacing:-.3px;margin:28px 0 12px;border-top:4px solid var(--ink);padding-top:8px}
.body h3{font-size:20px;line-height:1.3;margin:22px 0 8px}
.body ul{margin:0 0 18px;padding-left:1.25em}
.body li{font-size:18px;line-height:1.55;margin:0 0 8px}
.body .tablewrap{overflow-x:auto;margin:0 0 18px;-webkit-overflow-scrolling:touch}
.body table{width:100%;border-collapse:collapse;font-size:15px;line-height:1.45}
.body th,.body td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
.body th{background:var(--soft)}
.readalso{margin:8px 0 22px}
.readalso h2{font-size:22px;border-top:4px solid var(--ink);padding-top:8px;margin:0 0 8px}
.readalso ul{margin:0;padding-left:1.2em}
.readalso li{margin:6px 0;font-size:16.5px;line-height:1.4}
.readalso a{color:#0b57b0;text-decoration:underline}
figure.shot{margin:8px 0 22px}
.disclosure{font-size:14.5px;line-height:1.5;color:#33383f;background:var(--soft);border-left:4px solid var(--acc);padding:12px 14px;margin:0 0 18px}
.disclosure a{color:#0b57b0;text-decoration:underline}
.offer{background:var(--soft);border:1px solid var(--line);border-top:4px solid var(--acc);padding:14px 16px;margin:0 0 18px}
.offer p{font-size:16px;line-height:1.5;margin:0 0 12px}
.affbtns{display:flex;flex-wrap:wrap;gap:8px;margin:0}
.affbtn{display:inline-block;background:var(--acc);color:#fff;font-weight:800;padding:12px 16px;text-decoration:none;font-size:16px;line-height:1.25;text-align:center}
a.affbtn{color:#fff}
.affbtn:hover{background:var(--dark);color:#fff}
.partner{background:#fff;border:1px solid var(--line);border-left:4px solid var(--acc);padding:14px 16px;margin:8px 0 18px}
.partner .kicker{font-size:12px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;color:var(--acc);margin:0 0 4px}
.partner h2{font-size:18px;line-height:1.3;margin:0 0 8px}
.partner p{font-size:15px;line-height:1.45;margin:0 0 10px}
.partner .fine{font-size:13px;color:var(--mut);margin:8px 0 0}
.consult{max-width:760px;margin:28px auto 8px;background:#fff;border:1px solid var(--line);border-top:4px solid var(--acc);padding:16px 16px 18px}
.consult h2{font-size:22px;line-height:1.25;margin:0 0 8px}
.consult .leadin{font-size:15.5px;line-height:1.45;margin:0 0 12px;color:#23272d}
.consult .pair,.adform .pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.consult .adform{margin-top:0}
.consult .adform textarea{min-height:88px}
@media(max-width:600px){.consult .pair,.adform .pair{grid-template-columns:1fr}}
.faq{margin:8px 0 22px}
.faq h2{font-size:22px;border-top:4px solid var(--ink);padding-top:8px;margin:0 0 8px}
.faq details{border-bottom:1px solid var(--line);padding:12px 0}
.faq summary{font-weight:700;cursor:pointer;font-size:17px;line-height:1.35}
.faq details p{margin:8px 0 0;font-size:16.5px;line-height:1.55}
.src{background:var(--soft);border-left:4px solid var(--acc);padding:14px 16px;margin:28px 0;font-size:15px}.src h2{font-size:15px;margin:0 0 6px;text-transform:uppercase;letter-spacing:.5px}.src p{margin:0 0 8px;color:var(--mut)}.src ul{margin:0;padding-left:18px}.src a{text-decoration:underline;color:#0b57b0}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 28px;padding:0;list-style:none}.tags li{border:1px solid var(--line);border-radius:20px;padding:3px 12px;font-size:13px;color:#33383f}
.tgcta{margin:4px 0 28px}.tgcta a{display:flex;align-items:center;gap:12px;background:var(--dark);color:#fff;padding:14px 16px;font-weight:700;font-size:17px;line-height:1.35}
.tgcta a:hover{background:var(--acc)}.tgcta span{min-width:0}.tgcta svg{flex:none}
.sister{background:var(--soft);border-left:4px solid var(--acc);padding:14px 16px;margin:8px 0 18px}
.sister h2{font-size:16px;margin:0 0 8px}.sister ul{margin:0;padding-left:18px}.sister li{margin:4px 0}
.sister a,.sisterline a{color:#0b57b0;text-decoration:underline}
.sisterline{margin:0 0 16px;font-size:15px}
footer .projects{margin:12px 0 4px}footer .projects .plabel{font-weight:800;color:#fff;margin:0 0 2px}
.rel h2{font-size:22px;border-top:4px solid var(--ink);padding-top:8px}
.rel .grid{grid-template-columns:repeat(3,1fr)}
.langsw{display:flex;gap:10px;font-size:14px;margin:0 0 6px;flex-wrap:wrap}.langsw a{text-decoration:underline}
footer{background:var(--dark);color:#c8cdd5;margin-top:48px;padding:28px 0;font-size:14px}footer .logo{font-size:22px;margin-bottom:10px}footer a{text-decoration:underline;color:#fff}
footer p{max-width:820px;margin:8px 0}
footer .flinks{display:flex;flex-wrap:wrap;gap:6px 14px;margin:12px 0}
footer .social{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0 4px}
footer .social a{display:inline-flex;align-items:center;gap:8px;border:1px solid #3a4250;padding:6px 10px;text-decoration:none;font-weight:700}
footer .social a.tg{border-color:var(--acc)}footer .social a.tg:hover{background:var(--acc);border-color:var(--acc)}
.choose{min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--dark);color:#fff;text-align:center;padding:24px}
.choose .logo{font-size:44px;justify-content:center;margin-bottom:12px}.choose p{color:#c8cdd5;margin:6px 0 24px}
.choose .btns{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}.choose .btns a{background:#fff;color:var(--dark);font-weight:800;padding:14px 26px;font-size:18px}.choose .btns a:hover{background:var(--acc);color:#fff}
nav.cats li.promo a{color:var(--acc)}
.adpage{max-width:760px;margin:0 auto;padding-bottom:8px}
.adpage h1{font-size:40px;line-height:1.1;letter-spacing:-.8px;margin:22px 0 12px}
.adpage h2{font-size:22px;border-top:4px solid var(--ink);padding-top:8px;margin:28px 0 12px}
.adpage .leadin{font-size:18px;line-height:1.55;margin:0 0 12px}
.adpage a.mail{color:#0b57b0;text-decoration:underline}
.fmts{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.fmt{border:1px solid var(--line);border-top:4px solid var(--acc);padding:12px 14px;background:#fff}
.fmt h3{margin:0 0 6px;font-size:16px}
.fmt p{margin:0;color:#2b2f35;font-size:14.5px;line-height:1.45}
.adnote{background:var(--soft);border-left:4px solid var(--acc);padding:12px 14px;margin:16px 0;font-size:15px;line-height:1.5}
.adform{display:grid;gap:14px;margin-top:8px}
.adform .fld span,.checks legend{display:block;font-weight:700;font-size:14px;margin-bottom:4px}
.adform input[type=text],.adform input[type=email],.adform input[type=tel],.adform select,.adform textarea{width:100%;font:inherit;padding:10px 12px;border:1px solid #cfd3d8;background:#fff}
.adform textarea{min-height:140px;resize:vertical}
.adform input:focus,.adform select:focus,.adform textarea:focus{outline:2px solid var(--acc);outline-offset:1px}
.checks{border:0;margin:0;padding:0;display:grid;gap:8px}
.checks label,.consent{display:flex;gap:8px;align-items:flex-start;font-weight:500;font-size:15px;line-height:1.4}
.checks input,.consent input{width:18px;height:18px;margin-top:2px;flex:none}
.hint{font-weight:400;color:var(--mut);font-size:13px}
button.send{justify-self:start;background:var(--dark);color:#fff;font-weight:800;border:0;padding:12px 22px;font-size:16px;cursor:pointer}
button.send:hover{background:var(--acc)}
.hp{position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden}
.social{display:flex;gap:10px;flex-wrap:wrap}
.social a{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--line);padding:8px 12px;font-weight:700}
.social svg{display:block}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 18px}
.filters p{width:100%;margin:10px 0 0;font-size:12px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;color:var(--mut)}
.filters button{font:inherit;font-weight:700;font-size:14px;border:1px solid var(--line);background:#fff;padding:7px 12px;cursor:pointer}
.filters button.on{background:var(--dark);color:#fff;border-color:var(--dark)}
.weekband{background:var(--soft);margin:0 0 22px;padding:12px 16px 16px}
.weekband h2{font-size:22px;margin:0 0 10px;border-top:4px solid var(--acc);padding-top:8px}
.weekband ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:8px 20px}
.weekband li a{font-weight:700}
.weekband .meta{display:block;font-weight:400;color:var(--mut);font-size:13px}
.evgroup h2.sec{margin-top:8px}
.evlist{display:grid;gap:18px}
.ev{display:grid;grid-template-columns:240px 1fr;gap:16px;padding-bottom:16px;border-bottom:1px solid var(--line)}
.ev .pic{background:var(--soft);aspect-ratio:16/9;overflow:hidden}
.ev .pic img{width:100%;height:100%;object-fit:cover}
.ev .ico{display:flex;align-items:center;justify-content:center;background:var(--dark);color:#fff;aspect-ratio:16/9}
.ev h2{font-size:22px;line-height:1.2;margin:0 0 6px}
.ev .when{font-weight:700}
.ev .meta{font-size:14px;color:var(--mut);margin:0 0 8px}
.ev p{margin:0 0 8px}
.ev figcaption{font-size:12px}
.ev a{color:#0b57b0;text-decoration:underline}
.plistings{margin:4px 0 26px}.plistings h2,.pnews{font-size:22px;border-top:4px solid var(--acc);padding-top:8px;margin:8px 0 14px}
.pempty{background:var(--soft);border-left:4px solid var(--acc);padding:14px 16px;margin:0}
.pcard{border:1px solid var(--line);background:#fff;display:flex;flex-direction:column}
.pcard .img{background:var(--soft);aspect-ratio:16/9}
.pcard .pad{padding:12px 12px 14px;display:flex;flex-direction:column;gap:4px;flex:1}
.pcard h3{font-size:18px;line-height:1.25;margin:4px 0}
.pcard .price{font-weight:800;color:var(--acc);margin:0}
.pcard .facts{font-size:13px;color:var(--mut);margin:0}
.pstatus{display:inline-block;align-self:flex-start;font-size:12px;font-weight:800;letter-spacing:.4px;text-transform:uppercase;border:1px solid var(--line);padding:2px 8px}
.pcta{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}
.pcta a{display:inline-block;background:var(--dark);color:#fff;font-weight:800;padding:10px 14px;text-decoration:none}
.pcta a:hover{background:var(--acc)}
.req{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 16px}
.req a{flex:1 1 auto;display:inline-block;background:var(--acc);color:#fff;font-weight:800;padding:12px 18px;text-align:center;text-decoration:none;font-size:16px;line-height:1.2}
.req a:hover{background:var(--dark)}
.req a.wa{background:#128C7E}
.req a.wa:hover{background:#0b6b60}
.pcard .req{margin:auto 0 0}
.pcard .req a{flex:1 1 100%}
#lead{scroll-margin-top:72px}
.pgallery{display:grid;gap:12px;margin:0 0 18px}
.travelbox{background:var(--soft);border:1px solid var(--line);border-top:4px solid var(--acc);padding:14px 16px 12px;margin:8px 0 22px}
.travelbox h2{font-size:18px;line-height:1.3;margin:0 0 10px;letter-spacing:-.2px}
.travelcards{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.travelcards a{display:flex;align-items:center;gap:8px;min-height:44px;background:var(--bg);color:var(--ink);border:1px solid var(--line);padding:8px 10px;font-weight:700;font-size:14px;line-height:1.25}
.travelcards a:hover{border-color:var(--acc);color:var(--acc)}
.travelcards a:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.travelcards svg{flex:none;color:var(--acc)}
.travelbox .fine{font-size:13px;line-height:1.45;color:var(--mut);margin:10px 0 0}
.travelbox .fine a{color:#0b57b0;text-decoration:underline}
.cookiebanner{position:fixed;z-index:40;left:0;right:0;bottom:0;background:var(--dark);color:#fff;padding:14px 0 16px;box-shadow:0 -6px 20px rgba(0,0,0,.28)}
.cookiebanner[hidden]{display:none}
.cookiebanner p{margin:0 0 8px;max-width:760px;color:#e6e9ee}
.cookiebanner strong{color:#fff}
.cookiebanner a{color:#fff}
.cookie-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.cookie-actions button{font:inherit;font-weight:800;padding:8px 16px;cursor:pointer;border:1px solid #fff}
.cookie-actions button[data-consent="accepted"]{background:var(--acc);border-color:var(--acc);color:#fff}
.cookie-actions button[data-consent="rejected"]{background:transparent;color:#fff}
.cookie-actions button:hover{background:#fff;color:var(--dark)}
.cookie-actions button:focus{outline:2px solid #fff;outline-offset:2px}
@media(max-width:980px){.lead{grid-template-columns:1fr}.grid,.g3{grid-template-columns:repeat(2,1fr)}.cols{grid-template-columns:1fr}.rel .grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.lead .big h2{font-size:26px}article.a h1,.adpage h1{font-size:30px}.grid,.g3,.rel .grid,.fmts,.weekband ul{grid-template-columns:1fr}.travelcards{grid-template-columns:1fr 1fr}.side .card{grid-template-columns:110px 1fr}.ev{grid-template-columns:1fr}.date{display:none}.body p{font-size:17px}.body h2{font-size:22px}.body h3{font-size:18px}.body li{font-size:17px}h1.sec{font-size:24px}.by .when{align-items:flex-start;text-align:left}.req a,.affbtn{flex:1 1 100%;display:block;width:100%}}
"""

_GA_WARNED=False
def _ga():
    """Measurement ID when it is set and well formed. Empty means analytics stays off."""
    global _GA_WARNED
    v=(GA4_ID or "").strip()
    if not v: return ""
    if re.fullmatch(r"G-[A-Za-z0-9]+", v): return v
    if not _GA_WARNED:
        print(f"WARNING: GA4_ID {v!r} is not a measurement ID; analytics tag skipped")
        _GA_WARNED=True
    return ""
def indexnow_key():
    key=(INDEXNOW_KEY or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", key):
        raise SystemExit("INDEXNOW_KEY must be 32 hexadecimal characters")
    return key
def bing_meta():
    v=(BING_VERIFICATION or "").strip()
    if not v: return ""
    return f'<meta name="msvalidate.01" content="{e(v)}" />'
# Consent Mode v2 defaults. This script is emitted before adsbygoogle and before gtag.js.
CONSENT_BOOTSTRAP = """<script>
window.dataLayer=window.dataLayer||[];
function gtag(){dataLayer.push(arguments);}
gtag('consent','default',{
  'ad_storage':'denied',
  'ad_user_data':'denied',
  'ad_personalization':'denied',
  'analytics_storage':'denied',
  'wait_for_update':500
});
gtag('set','ads_data_redaction',true);
gtag('set','url_passthrough',true);
try{
  if(localStorage.getItem('cynews24-consent')==='accepted'){
    gtag('consent','update',{
      'ad_storage':'granted',
      'ad_user_data':'granted',
      'ad_personalization':'granted',
      'analytics_storage':'granted'
    });
  }
}catch(err){}
</script>"""
def ga4_snippet():
    gid=_ga()
    if not gid: return ""
    return (f'<script async src="https://www.googletagmanager.com/gtag/js?id={e(gid)}"></script>'
            f'<script>gtag("js",new Date());gtag("config","{e(gid)}");</script>')
def google_tags():
    """Consent default, then gtag.js when GA4_ID is set, then AdSense."""
    return CONSENT_BOOTSTRAP+ga4_snippet()+ADSENSE
COOKIE_BANNER_JS = """<script>
(function(){
  var KEY="cynews24-consent";
  var banner=document.getElementById("cookie-banner");
  if(!banner||typeof gtag!=="function") return;
  function show(){banner.hidden=false}
  function hide(){banner.hidden=true}
  function apply(value){
    var state=value==="accepted"?"granted":"denied";
    gtag("consent","update",{
      ad_storage:state,
      ad_user_data:state,
      ad_personalization:state,
      analytics_storage:state
    });
    try{localStorage.setItem(KEY,value)}catch(err){}
    hide();
  }
  var saved="";
  try{saved=localStorage.getItem(KEY)||""}catch(err){}
  if(saved!=="accepted"&&saved!=="rejected") show();
  banner.addEventListener("click",function(ev){
    var btn=ev.target.closest("[data-consent]");
    if(!btn) return;
    apply(btn.getAttribute("data-consent"));
  });
  document.querySelectorAll("[data-cookie-settings]").forEach(function(a){
    a.addEventListener("click",function(ev){
      ev.preventDefault();
      show();
      var first=banner.querySelector("[data-consent]");
      if(first) first.focus();
    });
  });
})();
</script>"""
def cookie_banner(l):
    u=UI[l]
    return (f'<div id="cookie-banner" class="cookiebanner" hidden role="dialog" aria-labelledby="cookie-title">'
      f'<div class="wrap"><p id="cookie-title"><strong>{e(u["cookie_title"])}</strong></p>'
      f'<p>{e(u["cookie_text"])} <a href="{href(f"/{l}/cookies/")}">{e(u["cookies"])}</a></p>'
      f'<div class="cookie-actions"><button type="button" data-consent="rejected">{e(u["cookie_reject"])}</button>'
      f'<button type="button" data-consent="accepted">{e(u["cookie_accept"])}</button></div></div></div>'
      +COOKIE_BANNER_JS)
_AH={"en":"Analytics","ru":"Аналитика","el":"Αναλυτικά"}
_CH={"en":"Cookies","ru":"Файлы cookie","el":"Cookies"}
def _replace_section(page, title, paras):
    sections=[(t, paras if t==title else ps) for t,ps in page["sections"]]
    return dict(t=page["t"], d=page["d"], sections=sections)
def _privacy_when_ga(l, gid):
    if l=="en":
        return (
          [f"The site uses Google Analytics 4 (measurement ID {gid}) to count visits. The tag loads only after Google Consent Mode has set analytics storage to denied, and Analytics stores cookies only if you accept. Until then, analytics storage stays denied. The site also loads Google AdSense (ca-pub-1547877294743851) so Google can show ads. Advertising storage stays denied until you accept. Cookie settings in the footer opens the choice again."],
          ["CyNews 24 does not set its own cookies. The accept or reject choice is stored in this browser's local storage under the name cynews24-consent, which is not a cookie. Google Consent Mode starts denied, before the AdSense script and before the Analytics tag. If you accept, Google Analytics and Google AdSense may set cookies. If you reject, advertising and analytics storage stay denied. The language chooser on the front page links to the Russian, English and Greek editions. It does not store a cookie. The cookie policy has the full account. If you follow a link to another site, that site has its own policy."])
    if l=="ru":
        return (
          [f"Сайт использует Google Analytics 4 (идентификатор {gid}), чтобы считать визиты. Тег подключается только после того, как Google Consent Mode запретил хранение для аналитики, и Analytics ставит cookie только если вы согласились. До согласия хранение для аналитики запрещено. Сайт также подключает Google AdSense (ca-pub-1547877294743851), чтобы Google мог показывать объявления. Хранение для рекламы запрещено, пока вы не примите cookie. «Настройки cookie» в подвале снова открывают выбор."],
          ["CyNews 24 не ставит собственные cookie. Выбор «принять» или «отклонить» хранится в local storage этого браузера под именем cynews24-consent — это не cookie. Google Consent Mode с самого начала запрещает хранение, ещё до скрипта AdSense и до тега Analytics. Если вы принимаете, Google Analytics и Google AdSense могут ставить cookie. Если вы отклоняете, хранение для рекламы и аналитики остаётся запрещённым. Выбор языка на первой странице ведёт на русскую, английскую и греческую версии. Cookie при этом не сохраняется. Подробности — в политике cookie. Если вы переходите по ссылке на другой сайт, у того сайта своя политика."])
    return (
      [f"Ο ιστότοπος χρησιμοποιεί το Google Analytics 4 (αναγνωριστικό {gid}) για να μετρά τις επισκέψεις. Η ετικέτα φορτώνει μόνο αφού το Google Consent Mode έχει θέσει την αποθήκευση αναλυτικών σε άρνηση, και το Analytics αποθηκεύει cookies μόνο αν αποδεχτείτε. Μέχρι τότε η αποθήκευση αναλυτικών μένει σε άρνηση. Ο ιστότοπος φορτώνει επίσης το Google AdSense (ca-pub-1547877294743851) ώστε η Google να εμφανίζει διαφημίσεις. Η αποθήκευση για διαφήμιση μένει σε άρνηση μέχρι να αποδεχτείτε. Οι «Ρυθμίσεις cookies» στο υποσέλιδο ανοίγουν ξανά την επιλογή."],
      ["Το CyNews 24 δεν τοποθετεί δικά του cookies. Η επιλογή αποδοχής ή απόρριψης αποθηκεύεται στο local storage αυτού του προγράμματος περιήγησης με το όνομα cynews24-consent και δεν είναι cookie. Το Google Consent Mode ξεκινά σε άρνηση, πριν από το script του AdSense και πριν από την ετικέτα του Analytics. Αν αποδεχτείτε, το Google Analytics και το Google AdSense μπορούν να τοποθετούν cookies. Αν απορρίψετε, η αποθήκευση για διαφήμιση και αναλυτικά μένει σε άρνηση. Η επιλογή γλώσσας στην πρώτη σελίδα οδηγεί στις ρωσικές, αγγλικές και ελληνικές εκδόσεις. Δεν αποθηκεύει cookie. Η πλήρης περιγραφή είναι στην πολιτική cookies. Αν ακολουθήσετε σύνδεσμο προς άλλον ιστότοπο, εκείνος έχει τη δική του πολιτική."])
def privacy_for(l):
    gid=_ga()
    if not gid: return PRIVACY[l]
    analytics, cookies=_privacy_when_ga(l, gid)
    return _replace_section(_replace_section(PRIVACY[l], _AH[l], analytics), _CH[l], cookies)
def _cookie_analytics_when_ga(l, gid):
    if l=="en":
        return [f"The site uses Google Analytics 4, measurement ID {gid}, to count visits. The tag is loaded only after the consent default. Analytics cookies are stored only if you accept. If you reject, analytics storage stays denied and those cookies are not set."]
    if l=="ru":
        return [f"Сайт использует Google Analytics 4, идентификатор {gid}, чтобы считать визиты. Тег подключается только после запрета по умолчанию. Аналитические cookie сохраняются только если вы согласились. Если вы отклоняете, хранение для аналитики остаётся запрещённым и такие cookie не ставятся."]
    return [f"Ο ιστότοπος χρησιμοποιεί το Google Analytics 4, αναγνωριστικό {gid}, για να μετρά τις επισκέψεις. Η ετικέτα φορτώνει μόνο μετά την προεπιλογή άρνησης. Τα αναλυτικά cookies αποθηκεύονται μόνο αν αποδεχτείτε. Αν απορρίψετε, η αποθήκευση αναλυτικών μένει σε άρνηση και αυτά τα cookies δεν τοποθετούνται."]
def cookies_for(l):
    gid=_ga()
    if not gid: return COOKIES[l]
    return _replace_section(COOKIES[l], _AH[l], _cookie_analytics_when_ga(l, gid))
# GitHub Pages serves /path/ and /path/index.html as the same file. Send the
# index.html address to the directory URL, which is the canonical.
PATH_CANON_JS = (
    "<script>(function(){var p=location.pathname;"
    "if(/\\/index\\.html$/i.test(p)){location.replace(p.replace(/index\\.html$/i,'')+location.search+location.hash);}"
    "})();</script>")
def indexed_langs(story=None):
    """Languages that have their own text. A missing translation is noindex and is not an alternate."""
    if not story:
        return list(LANGS)
    return [x for x in LANGS if x not in story.get("missing", ())]
def x_default_path(pathfn, langs):
    """The language chooser is x-default only for the three homepages.
    Every other page points x-default at its own English URL."""
    if len(langs) == len(LANGS) and all(pathfn(x) == f"/{x}/" for x in LANGS):
        return "/"
    pick = "en" if "en" in langs else ("ru" if "ru" in langs else langs[0])
    return pathfn(pick)
def alt_links(l, pathfn, langs=None):
    langs = list(langs or LANGS)
    out=[f'<link rel="alternate" hreflang="{x}" href="{abs_(pathfn(x))}">' for x in langs]
    out.append(f'<link rel="alternate" hreflang="x-default" href="{abs_(x_default_path(pathfn, langs))}">')
    return "\n".join(out)

def robots_content(value):
    """One robots meta. Indexable pages keep index,follow and gain a large image preview."""
    parts=[p.strip() for p in (value or "").split(",") if p.strip()]
    low=[p.lower() for p in parts]
    noindex=any(p=="noindex" or p.startswith("noindex") for p in low)
    # noindex pages stay out of Discover. Do not add a preview directive or flip them to index.
    if noindex:
        return ",".join(parts)
    if not any(p=="index" for p in low):
        parts.insert(0,"index"); low.insert(0,"index")
    if not any(p=="follow" for p in low):
        at=next(i for i,p in enumerate(low) if p=="index")+1
        parts.insert(at,"follow"); low.insert(at,"follow")
    if "max-image-preview:large" not in low:
        parts.append("max-image-preview:large")
    return ",".join(parts)
def head(l, title, desc, kws, path, pathfn, og_img, typ="website", extra="", jsonld=None, pub=None, mod=None, robots="index,follow,max-image-preview:large,max-snippet:-1", langs=None, og_w=1200, og_h=630):
    robots=robots_content(robots)
    h=[f'<!doctype html><html lang="{l}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
    PATH_CANON_JS, YANDEX_VERIFICATION, IMPACT_VERIFICATION]
    if bing_meta(): h.append(bing_meta())
    h+=[f'<title>{e(title)}</title><meta name="description" content="{e(desc)}">',
    f'<meta name="keywords" content="{e(", ".join(kws))}">',
    f'<meta name="robots" content="{e(robots)}">',
    f'<link rel="canonical" href="{abs_(path)}">',
    alt_links(l,pathfn,langs) if not robots.lower().startswith("noindex") else "",
    f'<meta property="og:site_name" content="{SITE}"><meta property="og:type" content="{typ}"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{abs_(path)}"><meta property="og:image" content="{abs_(og_img)}"><meta property="og:image:width" content="{int(og_w)}"><meta property="og:image:height" content="{int(og_h)}"><meta property="og:locale" content="{LOCALE[l]}">']
    for x in LANGS:
        if x!=l: h.append(f'<meta property="og:locale:alternate" content="{LOCALE[x]}">')
    if pub:
        h.append(f'<meta property="article:published_time" content="{pub}"><meta property="article:modified_time" content="{mod or pub}"><meta property="article:publisher" content="{SITE}">')
    h.append(f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title)}"><meta name="twitter:description" content="{e(desc)}"><meta name="twitter:image" content="{abs_(og_img)}">')
    h.append(f'<link rel="icon" href="{href("/favicon.svg")}" type="image/svg+xml"><link rel="apple-touch-icon" href="{href("/apple-touch-icon.png")}"><meta name="theme-color" content="#111827">')
    h.append(f'<link rel="stylesheet" href="{href("/assets/css/style.css")}">')
    h.append(f'<link rel="alternate" type="application/rss+xml" title="{SITE} ({l.upper()})" href="{href(f"/{l}/feed.xml")}">')
    if jsonld:
        for j in jsonld: h.append('<script type="application/ld+json">'+json.dumps(j,ensure_ascii=False).replace("</","<\\/")+'</script>')
    h.append(extra); h.append(google_tags()); h.append(TRAVELPAYOUTS_DRIVE); h.append('</head>')
    return "\n".join(h)

def telegram_for(l):
    """Channel for this page. Russian uses @cynews24; English and Greek use @cynews24en."""
    return (TELEGRAM.get("ru" if l=="ru" else "en") or "").strip()
def header(l, pathfn, active=None):
    u=UI[l]
    sw="".join(f'<a href="{href(pathfn(x))}" hreflang="{x}" lang="{x}" {"aria-current=\"true\"" if x==l else ""} title="{LANGNAME[x]}">{x.upper()}</a>' for x in LANGS)
    nav=f'<li><a href="{href(f"/{l}/")}" {"aria-current=\"page\"" if active=="home" else ""}>{u["home"]}</a></li>'+"".join(
      f'<li><a href="{href(f"/{l}/{c}/")}" {"aria-current=\"page\"" if active==c else ""}>{CATN[l][c]}</a></li>' for c in CATS)
    nav+=f'<li><a href="{href(f"/{l}/relocation/")}" {"aria-current=\"page\"" if active=="relocation" else ""}>{RELOCATION_MENU[l]}</a></li>'
    nav+=f'<li><a href="{href(f"/{l}/guides/")}" {"aria-current=\"page\"" if active=="guides" else ""}>{GUIDE_MENU[l]}</a></li>'
    nav+=f'<li><a href="{href(f"/{l}/travel/")}" {"aria-current=\"page\"" if active=="travel" else ""}>{TRAVEL_MENU[l]}</a></li>'
    nav+=f'<li><a href="{href(f"/{l}/events/")}" {"aria-current=\"page\"" if active=="events" else ""}>{u["events"]}</a></li>'
    nav+=f'<li class="promo"><a href="{href(f"/{l}/advertise/")}" {"aria-current=\"page\"" if active=="advertise" else ""}>{ADVERTISE[l]["menu"]}</a></li>'
    nav+=f'<li class="promo"><a href="{href(f"/{l}/advertising/")}" {"aria-current=\"page\"" if active=="advertising" else ""}>{u["ads"]}</a></li>'
    tg=telegram_for(l)
    tg_btn=f'<a class="tg" href="{e(tg)}" target="_blank" rel="noopener">{_icons()["telegram"]}<span>{e(u["tg"])}</span></a>' if tg else ""
    return (f'<body><a class="skip" href="#main">{u["skip"]}</a><header class="top"><div class="wrap"><a class="logo" href="{href(f"/{l}/")}" aria-label="{SITE}"><b>CyNews</b><i>24</i></a>'
      f'<div class="tr">{tg_btn}{threads_link("threads")}<span class="date">{fdate(TODAY,l,True)}</span><nav class="lang" aria-label="{u["lang"]}">{sw}</nav></div></div></header>'
      f'<nav class="cats" aria-label="{u["menu"]}"><div class="wrap"><ul>{nav}</ul></div></nav>')

def social_items():
    """Renderable social profiles. Empty URLs, including Facebook until one is set, stay hidden."""
    icons=_icons(); items=[]
    if TELEGRAM.get("ru"): items.append((TELEGRAM["ru"], "tg_ru", "telegram"))
    if TELEGRAM.get("en"): items.append((TELEGRAM["en"], "tg_en", "telegram"))
    for key,label in (("instagram","Instagram"),("threads","Threads"),("facebook","Facebook")):
        url=(SOCIAL.get(key) or "").strip()
        if url: items.append((url, label, key))
    return icons, items
def threads_link(css_class=""):
    """Threads profile. The icon is the Threads @ mark; the accessible name is Threads."""
    url=(SOCIAL.get("threads") or "").strip()
    if not url: return ""
    cls=f' class="{css_class}"' if css_class else ""
    return (f'<a{cls} href="{e(url)}" target="_blank" rel="noopener" aria-label="Threads">'
            f'{_icons()["threads"]}<span>Threads</span></a>')
def footer_social(l):
    """Page-language Telegram button, then any other configured profiles."""
    u=UI[l]; icons, items=social_items()
    bits=[]
    tg=telegram_for(l)
    if tg:
        bits.append(f'<a class="tg" href="{e(tg)}" target="_blank" rel="noopener">{icons["telegram"]}<span>{e(u["tg"])}</span></a>')
    for url,label,key in items:
        if key=="telegram": continue
        if key=="threads":
            bits.append(threads_link())
            continue
        name=u[label] if label in u else label
        bits.append(f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">{icons[key]}{e(name)}</a>')
    if not bits: return ""
    return f'<div class="social">{"".join(bits)}</div>'
def same_as():
    return [url for url,_label,_key in social_items()[1]]
def org_ld(l):
    return {"@type":["Organization","NewsMediaOrganization"],"@id":abs_("/")+"#org","name":SITE,"url":abs_("/"),
            "email":AD_EMAIL,"description":HOME_D[l],
            "logo":{"@type":"ImageObject","url":abs_("/assets/logo-512.png"),"width":512,"height":512},
            "address":{"@type":"PostalAddress","addressCountry":"CY"},
            "sameAs":same_as(),
            "publishingPrinciples":abs_(f"/{l}/editorial-policy/"),
            "correctionsPolicy":abs_(f"/{l}/editorial-policy/"),
            "actionableFeedbackPolicy":abs_(f"/{l}/editorial-policy/"),
            "ethicsPolicy":abs_(f"/{l}/editorial-policy/"),
            "masthead":abs_(f"/{l}/about/"),
            "contactPoint":[{"@type":"ContactPoint","contactType":"editorial","email":AD_EMAIL,"areaServed":"CY","availableLanguage":["Russian","English","Greek"]},
                            {"@type":"ContactPoint","contactType":"advertising","email":AD_EMAIL,"availableLanguage":["Russian","English","Greek"],"url":abs_(f"/{l}/advertising/")}]}
def website_ld(l, path, description=None):
    """WebSite node for a home page. SearchAction is omitted: there is no site search."""
    node={"@context":"https://schema.org","@type":"WebSite","@id":abs_(path)+"#website",
          "name":SITE,"url":abs_(path),"inLanguage":l,
          "publisher":{"@id":abs_("/")+"#org"}}
    if description:
        node["description"]=description
    return node
def publisher_ld():
    return {"@type":"Organization","@id":abs_("/")+"#org","name":SITE,"url":abs_("/"),
            "logo":{"@type":"ImageObject","url":abs_("/assets/logo-512.png"),"width":512,"height":512}}
def author_ld():
    """The newsroom is the author. Stories do not carry an individual reporter name."""
    return {"@type":"Organization","@id":abs_("/")+"#org","name":SITE,"url":abs_("/")}
def breadcrumb_ld(trail):
    """trail is (name, site path) pairs. Google requires at least two ListItems."""
    if len(trail) < 2:
        raise SystemExit("BreadcrumbList needs at least two items")
    return {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
        {"@type":"ListItem","position":i+1,"name":name,"item":abs_(path)}
        for i,(name,path) in enumerate(trail)]}
def footer(l):
    u=UI[l]
    links=[(f"/{l}/world/",CATN[l]["world"]),(f"/{l}/relocation/",RELOCATION_MENU[l]),(f"/{l}/tourism/",CATN[l]["tourism"]),(f"/{l}/economy/",CATN[l]["economy"]),(f"/{l}/real-estate/",CATN[l]["real-estate"]),(f"/{l}/events/",u["events"]),(f"/{l}/guides/",GUIDE_MENU[l]),(f"/{l}/about/",u["about"]),(f"/{l}/editorial-policy/",u["policy"]),(f"/{l}/affiliate-disclosure/",u["disclosure"]),(f"/{l}/privacy/",u["privacy"]),(f"/{l}/cookies/",u["cookies"]),(f"/{l}/advertise/",ADVERTISE[l]["menu"]),(f"/{l}/property-consultation/",CONSULT[l]["menu"]),(f"/{l}/advertising/",u["ads"])]
    fl="".join(f'<a href="{href(p)}">{e(n)}</a>' for p,n in links)
    fl+=f'<a href="{href(f"/{l}/cookies/")}" data-cookie-settings>{e(u["cookie_settings"])}</a>'
    langs=" · ".join(f'<a href="{href(f"/{x}/")}" hreflang="{x}" lang="{x}">{LANGNAME[x]}</a>' for x in LANGS)
    return (f'<footer><div class="wrap"><div class="logo"><b>CyNews</b><i>24</i></div><p>{u["footer"]}</p>'
      f'<nav class="flinks" aria-label="footer">{fl}</nav>{footer_social(l)}'
      f'{mycytax.projects_html(l, mycytax_catalog())}'
      f'<p>{langs}</p><p>© 2026 {SITE}. {u["copy"]}</p></div>{cookie_banner(l)}</footer></body></html>')

def S_(s,key,l): return s[key][l]
def img_srcset(s):
    """Srcset widths are the files' real widths, so a small photo is not advertised as 1200."""
    n=s["img"]; geo=lead_geometry(s)
    lw,lh=geo["lead"]; sw,sh=geo["small"]
    large=href(f"/assets/img/{n}-1200.webp"); small=href(f"/assets/img/{n}-600.webp")
    if (sw,sh)==(lw,lh):
        return large, lw, lh, f"{large} {lw}w"
    return large, lw, lh, f"{small} {sw}w, {large} {lw}w"
def img_tag(s,l,w,lazy=True,prio=False,sizes="100%"):
    n=s["img"]; alt=e(s["alt"][l])
    geo=lead_geometry(s)
    lw,lh=geo["lead"]; sw,sh=geo["small"]
    large,_,_,srcset=img_srcset(s)
    small=href(f"/assets/img/{n}-600.webp")
    if w==600 and (sw,sh)!=(lw,lh): src,W,H=small,sw,sh
    else: src,W,H=large,lw,lh
    ex = ' fetchpriority="high"' if prio else (' loading="lazy"' if lazy else '')
    return f'<img src="{src}" srcset="{srcset}" sizes="{sizes}" width="{W}" height="{H}" alt="{alt}" decoding="async"{ex}>'

def card(s,l,kind="grid",lazy=True):
    u=UI[l]; link=href(f'/{l}/{s["slug"]}/')
    if kind=="side":
        return (f'<article class="card"><a href="{link}" class="img">{img_tag(s,l,600,lazy,sizes="128px")}</a><div><span class="cat">{CATN[l][s["cat"]]}</span><a href="{link}"><h3>{e(s["title"][l])}</h3></a><div class="meta"><time datetime="{s["date"]}">{fdate(s["date"],l)}</time></div></div></article>')
    return (f'<article class="card"><a href="{link}" class="img" tabindex="-1">{img_tag(s,l,600,lazy,sizes="(max-width:600px) 100vw,(max-width:980px) 50vw,280px")}</a><span class="cat" style="display:block;margin-top:10px">{CATN[l][s["cat"]]}</span><a href="{link}"><h3 style="margin-top:4px">{e(s["title"][l])}</h3></a><p>{e(trunc(s["lede"][l],150))}</p><div class="meta"><time datetime="{s["date"]}">{fdate(s["date"],l)}</time></div></article>')

BYSLUG={s["slug"]:s for s in STORIES}
BYFILE={s["file"]:s["slug"] for s in STORIES}
def sorted_all():
    return sorted(STORIES,key=lambda s:(s["date"],STORIES.index(s)),reverse=True)
def news_sorted():
    """Homepage, the news feed and related news skip practical guides."""
    return [s for s in sorted_all() if not s.get("guide")]
def home_order():
    """Lead story and four side stories from content/home.json. Slugs that no longer exist are
    skipped and empty places are filled with the newest stories."""
    try:
        with open(os.path.join(CONTENT,"home.json"),encoding="utf8") as f: cfg=json.load(f)
    except FileNotFoundError:
        cfg={}
    want=[cfg.get("lead")]+list(cfg.get("side") or [])
    out=[]
    for x in want:
        x=(x or "").strip() if isinstance(x,str) else ""
        x=x if x in BYSLUG else BYFILE.get(x,x)
        if x in BYSLUG and x not in out: out.append(x)
    for s in news_sorted():
        if len(out)>=5: break
        if s["slug"] not in out: out.append(s["slug"])
    return out[:5]
ORDER_LEAD=home_order()

PEACHICK_URL="https://www.youtube.com/@thepeachickclub"
PEACHICK={
 "en":dict(title="Editor's pick: cartoons for kids, made in Cyprus",
           text="Real peachicks from Cyprus star in a children's cartoon, The Peachick Club.",
           btn="Watch on YouTube"),
 "ru":dict(title="От редакции: мультики для детей, снятые на Кипре",
           text="Настоящие павлинята с Кипра снимаются в детском мультике The Peachick Club.",
           btn="Смотреть на YouTube"),
 "el":dict(title="Επιλογή σύνταξης: κινούμενα για παιδιά, γυρισμένα στην Κύπρο",
           text="Αληθινά παγονόπουλα από την Κύπρο πρωταγωνιστούν σε παιδικά κινούμενα, το The Peachick Club.",
           btn="Δείτε στο YouTube"),
}
def peachick_promo(l):
    """Homepage recommendation. Not a social profile of the newsroom."""
    p=PEACHICK[l]
    return (f'<section class="pick" aria-label="{e(p["title"])}"><h3>{e(p["title"])}</h3>'
            f'<p>{e(p["text"])}</p>'
            f'<a href="{PEACHICK_URL}" target="_blank" rel="noopener">{e(p["btn"])}</a></section>')

def page_home(l):
    u=UI[l]; pathfn=lambda x:f"/{x}/"
    lead=BYSLUG[ORDER_LEAD[0]]; side=[BYSLUG[x] for x in ORDER_LEAD[1:]]
    # Real-estate band: articles added after the migration first (newest first), then the original ones in order.
    re_=[s for s in news_sorted() if s["cat"]=="real-estate" and s["seq"] is None]+[s for s in STORIES if s["cat"]=="real-estate" and s["seq"] is not None and not s.get("guide")]
    world_news=[s for s in news_sorted() if s["cat"]=="world"]
    cyprus=[s for s in news_sorted() if s["cat"]!="world"]
    used=set(ORDER_LEAD)|{s["slug"] for s in re_}
    rest=[s for s in cyprus if s["slug"] not in used]
    latest=cyprus[:8]
    if len(latest)<8:
        for s in world_news:
            if len(latest)>=8: break
            if s not in latest: latest.append(s)
    world_show=[s for s in world_news if s["slug"] not in set(ORDER_LEAD)][:4]
    kws=GKW[l]
    org=org_ld(l)
    # ItemList covers the lead, the side stories and the latest column, not the whole archive.
    # A list of every story was a second copy of the page and did not help the reader.
    shown=[]
    for s in [lead]+side+latest+world_show:
        if s["slug"] not in {x["slug"] for x in shown}: shown.append(s)
    # No SearchAction: the site has no search box, so a query URL would be false.
    ld=[website_ld(l, f"/{l}/", HOME_D[l]),
        {"@context":"https://schema.org",**org},
        {"@context":"https://schema.org","@type":"ItemList","itemListElement":[{"@type":"ListItem","position":i+1,"url":abs_(f"/{l}/{s['slug']}/"),"name":s["title"][l]} for i,s in enumerate(shown)]}]
    h=head(l,HOME_T[l],HOME_D[l],kws,f"/{l}/",pathfn,"/assets/og-default.jpg",jsonld=ld)
    h+=header(l,pathfn,"home")
    h+=f'<main id="main" class="wrap"><p class="tagline">{u["tagline"]}</p><h1 class="sec">{u["home_h"]}</h1>'
    h+=week_home(l)
    h+=f'<section class="lead" aria-label="{u["toplines"]}"><article class="card big"><a href="{href(f"/{l}/{lead["slug"]}/")}" class="img">{img_tag(lead,l,1200,False,True,"(max-width:980px) 100vw,760px")}</a><span class="cat" style="display:block;margin-top:12px">{CATN[l][lead["cat"]]}</span><a href="{href(f"/{l}/{lead["slug"]}/")}"><h2>{e(lead["title"][l])}</h2></a><p>{e(lead["lede"][l])}</p><div class="meta"><time datetime="{lead["date"]}">{fdate(lead["date"],l)}</time></div></article>'
    h+='<div class="side">'+"".join(card(s,l,"side",False) for s in side)+'</div></section>'
    h+=f'</main><div class="band"><div class="wrap"><h2 style="font-size:24px;border-top:4px solid var(--acc);padding-top:8px;margin:18px 0 16px"><a href="{href(f"/{l}/real-estate/")}">{u["realestate_h"]}</a></h2><div class="grid">'+"".join(card(s,l) for s in re_[:4])+'</div></div></div>'
    if world_show:
        h+=f'<div class="wrap"><h2 style="font-size:24px;border-top:4px solid var(--ink);padding-top:8px;margin:18px 0 16px"><a href="{href(f"/{l}/world/")}">{e(CATN[l]["world"])}</a></h2><div class="grid">'+"".join(card(s,l) for s in world_show)+'</div></div>'
    h+=f'<div class="wrap"><div class="cols"><section><h2 style="font-size:24px;border-top:4px solid var(--ink);padding-top:8px;margin:0 0 16px">{u["more"]}</h2><div class="grid g3">'+"".join(card(s,l) for s in rest)+'</div></section>'
    h+=f'<aside class="latest" aria-label="{u["latest"]}"><h2>{u["latest"]}</h2><ol class="latest">'+"".join(f'<li><span class="cat">{CATN[l][s["cat"]]}</span><a href="{href(f"/{l}/{s["slug"]}/")}">{e(s["title"][l])}</a><span class="meta"><time datetime="{s["date"]}">{fdate(s["date"],l)}</time></span></li>' for s in latest)+'</ol>'+peachick_promo(l)+'</aside></div></div>'
    h+=footer(l)
    # grid override for tablet/mobile handled by CSS? add class
    return h

PROP_FILE=os.path.join(os.path.dirname(HERE),"data","properties.json")
PROP_TYPES={
 "en":{"project":"Development","apartment":"Apartment","villa":"Villa","house":"House","land":"Land","office":"Office"},
 "ru":{"project":"Проект","apartment":"Квартира","villa":"Вилла","house":"Дом","land":"Участок","office":"Офис"},
 "el":{"project":"Έργο","apartment":"Διαμέρισμα","villa":"Βίλα","house":"Οικία","land":"Οικόπεδο","office":"Γραφείο"},
}
PROP_STATUS={
 "en":{"available":"Available","sold":"Sold","under construction":"Under construction","example":"Example"},
 "ru":{"available":"Свободно","sold":"Продано","under construction":"Строится","example":"Пример"},
 "el":{"available":"Διαθέσιμο","sold":"Πωλήθηκε","under construction":"Υπό κατασκευή","example":"Παράδειγμα"},
}
LISTING_UI={
 "en":dict(h="Property listings",news="Property news",empty="No property listings are published yet. New developments and homes for sale will appear here.",
           beds="bedrooms",area="m²",from_="from",on_request="Price on request",vat="+ VAT",contact="Contact",email="Email",whatsapp="WhatsApp",page="Advertising and contact",
           request="Request info",lead_name="Name",lead_phone="Phone / WhatsApp",lead_email="Email",optional="optional",lead_message="Message",
           interest="I'm interested in {title}",consent="I agree to be contacted about this listing.",send="Send request",honey="Leave this field empty",
           thanks_t="Thank you",thanks="Your request has been sent. We will contact you about this property.",back="Back to property listings"),
 "ru":dict(h="Объявления",news="Новости недвижимости",empty="Опубликованных объявлений пока нет. Новые проекты и объекты на продажу появятся здесь.",
           beds="спален",area="м²",from_="от",on_request="Цена по запросу",vat="без НДС",contact="Связаться",email="Эл. почта",whatsapp="WhatsApp",page="Реклама и контакты",
           request="Оставить заявку",lead_name="Имя",lead_phone="Телефон / WhatsApp",lead_email="Эл. почта",optional="необязательно",lead_message="Сообщение",
           interest="Меня интересует {title}",consent="Я согласен, чтобы со мной связались по этому объявлению.",send="Отправить заявку",honey="Оставьте это поле пустым",
           thanks_t="Спасибо",thanks="Заявка отправлена. Мы свяжемся с вами по этому объекту.",back="К объявлениям"),
 "el":dict(h="Αγγελίες",news="Ειδήσεις ακινήτων",empty="Δεν υπάρχουν δημοσιευμένες αγγελίες ακόμη. Νέα έργα και ακίνητα προς πώληση θα εμφανίζονται εδώ.",
           beds="υπνοδωμάτια",area="τ.μ.",from_="από",on_request="Τιμή κατόπιν αιτήματος",vat="πλέον ΦΠΑ",contact="Επικοινωνία",email="Email",whatsapp="WhatsApp",page="Διαφήμιση και επικοινωνία",
           request="Ζητήστε πληροφορίες",lead_name="Όνομα",lead_phone="Τηλέφωνο / WhatsApp",lead_email="Email",optional="προαιρετικό",lead_message="Μήνυμα",
           interest="Ενδιαφέρομαι για {title}",consent="Συμφωνώ να επικοινωνήσετε μαζί μου για αυτή την αγγελία.",send="Αποστολή αιτήματος",honey="Αφήστε κενό αυτό το πεδίο",
           thanks_t="Ευχαριστούμε",thanks="Το αίτημά σας στάλθηκε. Θα επικοινωνήσουμε μαζί σας για αυτό το ακίνητο.",back="Πίσω στις αγγελίες"),
}
# Every lead, property, advertise and contact form. Editorial mail stays on AD_EMAIL.
LEADS_EMAIL="2877novosti@gmail.com"
LEADS_FORM_ACTION="https://formsubmit.co/"+LEADS_EMAIL
LEAD_FORM_ACTION=LEADS_FORM_ACTION
def _loc(v,l):
    if isinstance(v, dict):
        return _clean(v.get(l) or v.get("en") or "")
    return _clean("" if v is None else str(v))
def load_property_file():
    if not os.path.exists(PROP_FILE):
        return {"contact":{},"listings":[]}
    with open(PROP_FILE,encoding="utf8") as f:
        data=json.load(f)
    if isinstance(data, list):
        data={"contact":{},"listings":data}
    if not isinstance(data, dict):
        raise SystemExit("data/properties.json must be an object")
    data.setdefault("contact",{})
    listings=data.get("listings") or []
    if not isinstance(listings, list):
        raise SystemExit("data/properties.json listings must be a list")
    seen=set()
    for p in listings:
        pid=_clean(p.get("id"))
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", pid or ""):
            raise SystemExit(f"property id {pid!r} must be lowercase letters, digits and hyphens")
        if pid in seen:
            raise SystemExit(f"duplicate property id {pid}")
        seen.add(pid)
        for key in ("title","description","city"):
            if not isinstance(p.get(key), dict) or not _clean(p[key].get("en")):
                raise SystemExit(f"property {pid}: {key} needs at least an English value")
    data["listings"]=listings
    return data
_PROPS=None
def property_data():
    global _PROPS
    if _PROPS is None:
        _PROPS=load_property_file()
    return _PROPS
def listing_is_live(p):
    """The sample record stays off the site. A listing is live only when published and not marked example."""
    if not p.get("published"):
        return False
    return str(p.get("status") or "").strip().lower()!="example"
def published_listings():
    return [p for p in property_data()["listings"] if listing_is_live(p)]
def _prop_label(table, l, key):
    return table[l].get(key) or table["en"].get(key) or str(key)
def _prop_price(p, l):
    """A missing price is 'on request'. vat_excluded adds the local VAT note after the figure."""
    raw=p.get("price")
    if raw is None or raw=="":
        return LISTING_UI[l]["on_request"]
    try:
        num=int(raw)
    except (TypeError, ValueError):
        raise SystemExit(f"property {p.get('id')}: price must be a number of euros or null")
    text="€"+f"{num:,}"
    if p.get("price_from"):
        text=LISTING_UI[l]["from_"]+" "+text
    if p.get("vat_excluded"):
        text=text+" "+LISTING_UI[l]["vat"]
    return text
def _title_opens_with(title, label):
    """True when the title already begins with the type, so a second label would repeat it."""
    title=(title or "").casefold().strip()
    label=(label or "").casefold().strip()
    if not label or not title.startswith(label):
        return False
    rest=title[len(label):]
    return rest=="" or not rest[0].isalnum()
def _bedroom_phrase(n, l):
    """Russian bedroom counts: 1 спальня, 2–4 спальни, 5+ спален, with 11–14 on спален."""
    if l!="ru":
        return f'{n} {LISTING_UI[l]["beds"]}'
    try:
        num=int(n)
    except (TypeError, ValueError):
        return f'{n} {LISTING_UI["ru"]["beds"]}'
    if isinstance(n, float) and not n.is_integer():
        return f'{n} {LISTING_UI["ru"]["beds"]}'
    if isinstance(n, str) and n.strip()!=str(num):
        return f'{n} {LISTING_UI["ru"]["beds"]}'
    mod10, mod100 = abs(num)%10, abs(num)%100
    if mod10==1 and mod100!=11:
        word="спальня"
    elif mod10 in (2, 3, 4) and mod100 not in (12, 13, 14):
        word="спальни"
    else:
        word="спален"
    return f"{num} {word}"
def _prop_facts(p, l):
    u=LISTING_UI[l]
    bits=[]
    city=_loc(p.get("city"), l)
    area=_loc(p.get("area"), l)
    place=", ".join(x for x in (city, area) if x)
    if place:
        bits.append(place)
    if p.get("bedrooms") not in (None, ""):
        bits.append(_bedroom_phrase(p["bedrooms"], l))
    if p.get("area_m2") not in (None, ""):
        bits.append(f'{p["area_m2"]} {u["area"]}')
    return " · ".join(bits)
def listing_photo_file(rel):
    rel=(rel or "").lstrip("/")
    if not rel.startswith("images/properties/"):
        return ""
    path=os.path.normpath(os.path.join(os.path.dirname(HERE), rel))
    root=os.path.normpath(os.path.join(os.path.dirname(HERE), "images", "properties"))
    if not path.startswith(root+os.sep) or not os.path.isfile(path):
        return ""
    return path
def build_listing_photos():
    d=os.path.join(OUT,"assets","img","properties")
    os.makedirs(d, exist_ok=True)
    for p in published_listings():
        for i, rel in enumerate(p.get("photos") or []):
            src=listing_photo_file(rel)
            if not src:
                print(f"WARNING: listing photo missing for {p['id']}: {rel}")
                continue
            im=Image.open(src)
            plain=cover_crop(im,1200,675,(0.5,0.45))
            plain.save(f"{d}/{p['id']}-{i}-1200.webp","WEBP",quality=78,method=6)
            plain.resize((600,338),Image.LANCZOS).save(f"{d}/{p['id']}-{i}-600.webp","WEBP",quality=76,method=6)
def _listing_img(p, i, l, lazy=True):
    rel=(p.get("photos") or [None])[i] if i < len(p.get("photos") or []) else None
    if not listing_photo_file(rel or ""):
        return ""
    alt=e(_loc(p.get("title"), l))
    src=href(f"/assets/img/properties/{p['id']}-{i}-1200.webp")
    small=href(f"/assets/img/properties/{p['id']}-{i}-600.webp")
    ex=' loading="lazy"' if lazy else ""
    return f'<img src="{src}" srcset="{small} 600w, {src} 1200w" sizes="(max-width:600px) 100vw, 360px" width="1200" height="675" alt="{alt}" decoding="async"{ex}>'
def listing_card(p, l):
    u=LISTING_UI[l]
    link=href(f"/{l}/real-estate/{p['id']}/")
    img=_listing_img(p, 0, l)
    media=f'<a class="img" href="{link}" tabindex="-1">{img}</a>' if img else ""
    kind=_prop_label(PROP_TYPES, l, p.get("type"))
    title=_loc(p["title"], l)
    cat="" if _title_opens_with(title, kind) else f'<span class="cat">{e(kind)}</span>'
    status=_prop_label(PROP_STATUS, l, p.get("status"))
    price=_prop_price(p, l)
    return (f'<article class="pcard">{media}<div class="pad"><span class="pstatus">{e(status)}</span>'
            f'{cat}<a href="{link}"><h3>{e(title)}</h3></a>'
            f'<p class="price">{e(price)}</p><p class="facts">{e(_prop_facts(p, l))}</p>'
            f'{listing_request_links(p, l, link+"#lead")}</div></article>')
# Editorial cards under the ATEX listings. Not inventory, and not links to the developer.
BBF_COPY = {
 "en": dict(h="Notes on other new projects",
            note="These are not our listings. The prices are the developer’s or an agent’s and can change.",
            cta="Get independent advice",
            similar="Similar new projects",
            advice="Get independent advice, compare this with other new projects, and check the full costs and taxes. This form comes to CyNews 24, not to a developer.",
            send="Get independent advice"),
 "ru": dict(h="Заметки о других новых проектах",
            note="Это не наши объявления. Цены принадлежат застройщику или агентству и могут измениться.",
            cta="Независимая консультация",
            similar="Похожие новые проекты",
            advice="Независимая консультация: сравнить с другими новыми проектами и проверить полные расходы и налоги. Форма приходит в CyNews 24, не застройщику.",
            send="Независимая консультация"),
 "el": dict(h="Σημειώσεις για άλλα νέα έργα",
            note="Δεν είναι δικές μας αγγελίες. Οι τιμές είναι του κατασκευαστή ή ενός μεσίτη και μπορεί να αλλάξουν.",
            cta="Ανεξάρτητη συμβουλή",
            similar="Παρόμοια νέα έργα",
            advice="Ανεξάρτητη συμβουλή: σύγκριση με άλλα νέα έργα και έλεγχος πλήρους κόστους και φόρων. Η φόρμα έρχεται στο CyNews 24, όχι σε κατασκευαστή.",
            send="Ανεξάρτητη συμβουλή"),
}
BBF_REVIEWS = (
 dict(slug="eden-coast-paphos-review", img="vrysoudia-beach", project="Eden Coast",
      place={"en":"Geroskipou, Paphos","ru":"Героскипу, Пафос","el":"Γεροσκήπου, Πάφος"},
      price={"en":"From €940,000 on the developer page","ru":"От €940 000 на странице застройщика","el":"Από €940.000 στη σελίδα του κατασκευαστή"},
      line={"en":"16 homes in the developer’s summary. Agents publish other prices and a 2029 date.","ru":"16 объектов в сводке застройщика. Агенты публикуют другие цены и дату в 2029 году.","el":"16 κατοικίες στη σύνοψη του κατασκευαστή. Οι μεσίτες δημοσιεύουν άλλες τιμές και ημερομηνία το 2029."},
      alt={"en":"Vrysoudia II beach in Paphos, not the project site","ru":"Пляж Врисудия II в Пафосе, не площадка проекта","el":"Παραλία Βρυσούδια II στην Πάφο, όχι το οικόπεδο του έργου"}),
 dict(slug="dream-tower-limassol-review", img="agios-tychonas-view", project="Dream Tower",
      place={"en":"Agios Tychonas, Limassol","ru":"Агиос Тихонас, Лимассол","el":"Άγιος Τύχωνας, Λεμεσός"},
      price={"en":"From €890,000 on the developer page","ru":"От €890 000 на странице застройщика","el":"Από €890.000 στη σελίδα του κατασκευαστή"},
      line={"en":"A 27-storey tower. Agents disagree with the developer’s starting price and with each other on size.","ru":"Башня в 27 этажей. Агенты расходятся и со стартовой ценой застройщика, и между собой по метражу.","el":"Πύργος 27 ορόφων. Οι μεσίτες διαφωνούν με την τιμή εκκίνησης του κατασκευαστή και μεταξύ τους στο εμβαδόν."},
      alt={"en":"Limassol from Agios Tychonas in 2014, not the tower","ru":"Лимассол с Агиос Тихонаса в 2014 году, не башня","el":"Η Λεμεσός από τον Άγιο Τύχωνα το 2014, όχι ο πύργος"}),
 dict(slug="kean-limassol-review", img="limassol-skyline", project="KEAN",
      place={"en":"Limassol","ru":"Лимассол","el":"Λεμεσός"},
      price={"en":"Price on request","ru":"Цена по запросу","el":"Τιμή κατόπιν αιτήματος"},
      line={"en":"Four towers in a January 2026 Cyprus Mail article. That article states no sale price.","ru":"Четыре башни в статье Cyprus Mail за январь 2026 года. Продажной цены там нет.","el":"Τέσσερις πύργοι σε άρθρο της Cyprus Mail τον Ιανουάριο 2026. Το άρθρο δεν δίνει τιμή πώλησης."},
      alt={"en":"Limassol skyline in 2022, not the KEAN site","ru":"Панораμα Лимассола в 2022 году, не площадка KEAN","el":"Ορίζοντας της Λεμεσού το 2022, όχι το οικόπεδο KEAN"}),
 dict(slug="yoo-limassol-review", img="pyrgos-limassol", project="YOO Limassol",
      place={"en":"Pyrgos, Limassol","ru":"Пиргос, Лимассол","el":"Πύργος, Λεμεσός"},
      price={"en":"From 2,965,000 on the sales page; VAT not stated","ru":"От 2 965 000 на странице продаж; про НДС не сказано","el":"Από 2.965.000 στη σελίδα πωλήσεων· ο ΦΠΑ δεν αναφέρεται"},
      line={"en":"81 villas and 84 apartments on the project site. The sales page says 80 villas.","ru":"81 вилла и 84 квартиры на сайте проекта. Страница продаж пишет 80 вилл.","el":"81 βίλες και 84 διαμερίσματα στον ιστότοπο. Η σελίδα πωλήσεων γράφει 80 βίλες."},
      alt={"en":"Pyrgos, Limassol, in 2012, not the YOO site","ru":"Пиргос в районе Лимассола в 2012 году, не площадка YOO","el":"Ο Πύργος Λεμεσού το 2012, όχι το οικόπεδο YOO"}),
 dict(slug="limassol-blu-marine-review", img="limassol-promenade-2012", project="Limassol Blu Marine",
      place={"en":"Limassol seafront","ru":"Набережная Лимассола","el":"Θαλάσσιο μέτωπο Λεμεσού"},
      price={"en":"From €658,000 + VAT on a listed studio","ru":"От €658 000 плюс НДС у студии в списке","el":"Από €658.000 συν ΦΠΑ σε στούντιο του καταλόγου"},
      line={"en":"Four towers in a company text. Listed Cavalli prices are not the June 2026 “from €845,000”.","ru":"Четыре башни в тексте компании. Цены Cavalli в списке — не «от €845 000» июня 2026 года.","el":"Τέσσερις πύργοι σε κείμενο της εταιρείας. Οι τιμές Cavalli δεν είναι το «από €845.000» του Ιουνίου 2026."},
      alt={"en":"Limassol promenade in 2012, not Blu Marine","ru":"Набережная Лимассола в 2012 году, не Blu Marine","el":"Παραλιακός περίπατος Λεμεσού το 2012, όχι το Blu Marine"}),
 dict(slug="one-limassol-review", img="limassol-molos", project="ONE Limassol",
      place={"en":"28th October Avenue, Limassol","ru":"Проспект 28 Октября, Лимассол","el":"Λεωφόρος 28ης Οκτωβρίου, Λεμεσός"},
      price={"en":"From €1,700,000 + VAT in Pafilia’s 2026 guide","ru":"От €1 700 000 плюс НДС в гиде Pafilia за 2026 год","el":"Από €1.700.000 συν ΦΠΑ στον οδηγό της Pafilia του 2026"},
      line={"en":"37 storeys and 83 homes on Pafilia’s pages. The 2026 guide still lists homes for sale.","ru":"37 этажей и 83 дома на страницах Pafilia. В гиде 2026 года дома ещё продаются.","el":"37 όροφοι και 83 κατοικίες στις σελίδες της Pafilia. Ο οδηγός του 2026 ακόμη πουλά κατοικίες."},
      alt={"en":"Limassol Molos in 2021, not the ONE tower","ru":"Молос Лимассола в 2021 году, не башня ONE","el":"Ο Μόλος Λεμεσού το 2021, όχι ο πύργος ONE"}),
 dict(slug="minthis-residences-review", img="tsada-village", project="Minthis Residences",
      place={"en":"Tsada, Paphos","ru":"Цада, Пафос","el":"Τσάδα, Πάφος"},
      price={"en":"Price on request","ru":"Цена по запросу","el":"Τιμή κατόπιν αιτήματος"},
      line={"en":"Homes of 220–333 m² on the Pafilia page. That page states no sale price.","ru":"Дома 220–333 м² на странице Pafilia. Продажной цены там нет.","el":"Κατοικίες 220–333 τ.μ. στη σελίδα της Pafilia. Η σελίδα δεν δίνει τιμή πώλησης."},
      alt={"en":"Tsada in 2014, not a Minthis house","ru":"Цада в 2014 году, не дом Minthis","el":"Η Τσάδα το 2014, όχι κατοικία Minthis"}),
)
BBF_BY_SLUG = {item["slug"]: item for item in BBF_REVIEWS}
ATEX_COMPARE = ("bellissimo", "olivia", "the-city-home-2")
def bbf_review_cards(l):
    copy=BBF_COPY[l]
    cards=[]
    for item in BBF_REVIEWS:
        stub={"img": item["img"], "alt": item["alt"]}
        review=href(f"/{l}/{item['slug']}/")
        advice=href(f"/{l}/{item['slug']}/#consult")
        cards.append(
            f'<article class="pcard"><a class="img" href="{review}">{img_tag(stub, l, 600, True, sizes="(max-width:600px) 100vw, 360px")}</a>'
            f'<div class="pad"><a href="{review}"><h3>{e(item["project"])}</h3></a>'
            f'<p class="facts">{e(item["place"][l])}</p><p>{e(item["price"][l])}</p>'
            f'<p class="facts">{e(item["line"][l])}</p>'
            f'<p class="req"><a href="{advice}">{e(copy["cta"])}</a></p></div></article>')
    return (f'<h2 class="pnews">{e(copy["h"])}</h2><p class="meta">{e(copy["note"])}</p>'
            f'<div class="grid g3">{"".join(cards)}</div>')
def similar_atex(l):
    order={pid: i for i, pid in enumerate(ATEX_COMPARE)}
    rows=[p for p in published_listings() if p["id"] in order]
    rows.sort(key=lambda p: order[p["id"]])
    if not rows:
        return ""
    items="".join(
        f'<li><a href="{href(f"/{l}/real-estate/{p["id"]}/")}">{e(_loc(p["title"], l))}</a>'
        f' — {e(_prop_facts(p, l))}</li>' for p in rows)
    return f'<section class="src"><h2>{e(BBF_COPY[l]["similar"])}</h2><ul>{items}</ul></section>'
def listings_block(l):
    u=LISTING_UI[l]
    rows=published_listings()
    if rows:
        body='<div class="grid g3">'+"".join(listing_card(p, l) for p in rows)+'</div>'
    else:
        body=f'<p class="pempty">{e(u["empty"])}</p>'
    body+=bbf_review_cards(l)
    return f'<section class="plistings" aria-label="{e(u["h"])}"><h2>{e(u["h"])}</h2>{body}</section>'
def listing_contact(p):
    base=dict(property_data().get("contact") or {})
    over=p.get("contact") or {}
    if isinstance(over, dict):
        for k,v in over.items():
            if _clean(v if isinstance(v, str) else ""):
                base[k]=v
    return base
def _wa_href(raw):
    digits=re.sub(r"\D","", raw or "")
    if len(digits)<8:
        return ""
    return "https://wa.me/"+digits
def listing_cta(p, l):
    u=LISTING_UI[l]
    c=listing_contact(p)
    bits=[]
    path=_clean(c.get("path") or "/advertising/")
    if not path.startswith("/"):
        path="/"+path
    if not path.endswith("/"):
        path=path+"/"
    bits.append(f'<a href="{href("/"+l+path)}">{e(u["page"])}</a>')
    email=_clean(c.get("email"))
    if email:
        bits.append(f'<a href="mailto:{e(email)}">{e(u["email"])}: {e(email)}</a>')
    wa=_wa_href(c.get("whatsapp"))
    if wa:
        bits.append(f'<a href="{e(wa)}" target="_blank" rel="noopener">{e(u["whatsapp"])}</a>')
    return f'<div class="pcta">{"".join(bits)}</div>'
def listing_request_links(p, l, target):
    """Request button, plus a WhatsApp button only when the listing already has a number."""
    u=LISTING_UI[l]
    bits=[f'<a href="{e(target)}">{e(u["request"])}</a>']
    wa=_wa_href(listing_contact(p).get("whatsapp"))
    if wa:
        bits.append(f'<a class="wa" href="{e(wa)}" target="_blank" rel="noopener">{e(u["whatsapp"])}</a>')
    return f'<p class="req">{"".join(bits)}</p>'
def listing_form(l, p):
    """Static lead form. FormSubmit emails 2877novosti@gmail.com. No script."""
    u=LISTING_UI[l]
    title=_loc(p["title"], l)
    path=f"/{l}/real-estate/{p['id']}/"
    interest=u["interest"].format(title=title)
    subject=e("CyNews24 lead: "+title)
    return f'''<form id="lead" class="adform" action="{LEAD_FORM_ACTION}" method="POST">
<input type="hidden" name="_subject" value="{subject}">
<input type="hidden" name="listing" value="{e(title)}">
<input type="hidden" name="page" value="{e(abs_(path))}">
<input type="hidden" name="_template" value="table">
<input type="hidden" name="_captcha" value="false">
<input type="hidden" name="_next" value="{e(abs_(f"/{l}/thanks/"))}">
<p class="hp" aria-hidden="true"><label>{e(u["honey"])}<input type="text" name="_honey" tabindex="-1" autocomplete="off"></label></p>
<label class="fld"><span>{e(u["lead_name"])}</span><input type="text" name="name" required autocomplete="name"></label>
<label class="fld"><span>{e(u["lead_phone"])}</span><input type="tel" name="phone" required autocomplete="tel"></label>
<label class="fld"><span>{e(u["lead_email"])} <span class="hint">({e(u["optional"])})</span></span><input type="email" name="email" autocomplete="email"></label>
<label class="fld"><span>{e(u["lead_message"])} <span class="hint">({e(u["optional"])})</span></span><textarea name="message">{e(interest)}</textarea></label>
<label class="consent"><input type="checkbox" name="consent" value="yes" required> <span>{e(u["consent"])}</span></label>
<button class="send" type="submit">{e(u["send"])}</button>
</form>'''
def page_lead_thanks(l):
    u=LISTING_UI[l]
    pathfn=lambda x: f"/{x}/thanks/"
    h=head(l, f'{u["thanks_t"]} | {SITE}', u["thanks"], [SITE], f"/{l}/thanks/", pathfn, "/assets/og-default.jpg", robots="noindex,follow")
    h+=header(l, pathfn, "real-estate")
    h+=(f'<main id="main" class="wrap"><article class="adpage"><h1>{e(u["thanks_t"])}</h1>'
        f'<p class="leadin">{e(u["thanks"])}</p>'
        f'<p><a class="mail" href="{href(f"/{l}/real-estate/")}">{e(u["back"])}</a></p></article></main>'+footer(l))
    return h
def page_listing(l, p):
    u=LISTING_UI[l]
    pid=p["id"]
    path=f"/{l}/real-estate/{pid}/"
    pathfn=lambda x, pid=pid: f"/{x}/real-estate/{pid}/"
    title=_loc(p["title"], l)
    desc=trunc(_loc(p["description"], l).replace("\n"," "), 158)
    price=_prop_price(p, l)
    photos=[]
    for i in range(len(p.get("photos") or [])):
        tag=_listing_img(p, i, l, lazy=(i>0))
        if tag:
            photos.append(f'<figure>{tag}</figure>')
    gallery=f'<div class="pgallery">{"".join(photos)}</div>' if photos else ""
    paras="".join(f"<p>{e(x)}</p>" for x in _paras(_loc(p["description"], l)))
    offer={"@type":"Offer","priceCurrency":"EUR","availability":"https://schema.org/InStock"}
    if p.get("price") not in (None,""):
        offer["price"]=str(int(p["price"]))
    ld=[{"@context":"https://schema.org","@type":"RealEstateListing","name":title,"description":_loc(p["description"], l),
        "url":abs_(path),"inLanguage":l,"address":{"@type":"PostalAddress","addressLocality":_loc(p.get("city"), l),"addressCountry":"CY"},
        "offers":offer},
        breadcrumb_ld([(UI[l]["crumb_home"], f"/{l}/"), (CATN[l]["real-estate"], f"/{l}/real-estate/"), (title, path)])]
    h=head(l, f"{title} | {CATN[l]['real-estate']} | {SITE}", desc or title, [title, CATN[l]["real-estate"], SITE], path, pathfn, "/assets/og-default.jpg", jsonld=ld)
    h+=header(l, pathfn, "real-estate")
    h+=f'<main id="main" class="wrap"><nav class="crumb" aria-label="breadcrumb"><a href="{href(f"/{l}/")}">{UI[l]["crumb_home"]}</a> › <a href="{href(f"/{l}/real-estate/")}">{CATN[l]["real-estate"]}</a></nav>'
    kind=_prop_label(PROP_TYPES, l, p.get("type"))
    cat="" if _title_opens_with(title, kind) else f'<p class="cat">{e(kind)}</p>'
    h+=f'<article class="adpage">{cat}<h1>{e(title)}</h1>'
    h+=f'<p class="leadin">{e(price)}</p>{listing_request_links(p, l, "#lead")}'
    h+=f'<p class="meta">{e(_prop_facts(p, l))} · {e(_prop_label(PROP_STATUS, l, p.get("status")))}</p>'
    h+=gallery+f'<div class="body">{paras}</div><h2>{e(u["contact"])}</h2>{listing_cta(p, l)}{listing_form(l, p)}</article></main>'+footer(l)
    return h
def region_nav(l, current=""):
    bits=[]
    cur=' aria-current="page"' if current=="" else ""
    bits.append(f'<a href="{href(f"/{l}/world/")}"{cur}>{e(CATN[l]["world"])}</a>')
    for r in REGIONS:
        on=' aria-current="page"' if r==current else ""
        bits.append(f'<a href="{href(f"/{l}/world/{r}/")}"{on}>{e(REGION_N[l][r])}</a>')
    return f'<nav class="subnav" aria-label="{e(REGION_MENU[l])}">{"".join(bits)}</nav>'
def intro_html(paras):
    return f'<div class="intro">{"".join("<p>"+render_inline(p)+"</p>" for p in paras)}</div>'
CAT_BODY = {
 "en":{
  "tourism":[
   "Tourism news from Cyprus: who is visiting, how they get here, and what beaches, holidays and town centres are making the headlines.",
   "For a trip rather than the news, use the [travel guides](/en/travel/) and the diary of [events in Cyprus](/en/events/).",
   "Readers who are staying longer can start with [relocation and expat life](/en/relocation/) and the [economy](/en/economy/) pages on prices, tax and work."],
  "economy":[
   "The economy section follows prices, tax, energy, jobs, pensions and public money in Cyprus. Each story is a rewrite and links to the outlet it came from.",
   "Housing costs are collected under [real estate](/en/real-estate/). People moving for work can also read [relocation and expat life](/en/relocation/) and [tourism](/en/tourism/) when the story is about visitors' spending."],
  "real-estate":[
   "Real estate in Cyprus: planning law, new homes, rents and the resale market. Listings from advertisers, when any are published, sit above the news.",
   "Practical pages for buyers and tenants are in the [guides](/en/guides/). The wider cost of living is in the [economy](/en/economy/) section, and [relocation](/en/relocation/) is the starting point for a move."],
  "world":[
   "World news is grouped by region: Europe, the Middle East, Russia and the CIS, Asia, the Americas and Africa. Each story is rewritten in our own words and links to the original report.",
   "Cyprus politics, the [economy](/en/economy/) and [tourism](/en/tourism/) stay in their own sections. A story filed here is about the wider world."]},
 "ru":{
  "tourism":[
   "Новости туризма Кипра: кто приезжает, как добирается и что происходит с пляжами, отпусками и курортными городами.",
   "Если нужен не обзор новостей, а план поездки, откройте [путеводители](/ru/travel/) и [мероприятия на Кипре](/ru/events/).",
   "Тем, кто остаётся дольше отпуска, подойдут страницы [переезда и жизни экспатов](/ru/relocation/) и раздел [экономики](/ru/economy/) — цены, налоги и работа."],
  "economy":[
   "В экономике — цены, налоги, энергия, работа, пенсии и государственные деньги Кипра. Каждый материал — пересказ со ссылкой на исходную публикацию.",
   "Жильё собрано в разделе [недвижимости](/ru/real-estate/). Тем, кто переезжает ради работы, пригодятся страницы [переезда](/ru/relocation/), а траты туристов — в [туризме](/ru/tourism/)."],
  "real-estate":[
   "Недвижимость Кипра: градостроительные правила, новостройки, аренда и вторичный рынок. Объявления рекламодателей, если они опубликованы, стоят выше новостей.",
   "Практические страницы для покупателей и арендаторов — в [гидах](/ru/guides/). Стоимость жизни — в [экономике](/ru/economy/), а начало переезда — в разделе [переезда](/ru/relocation/)."],
  "world":[
   "Мировые новости разложены по регионам: Европа, Ближний Восток, Россия и СНГ, Азия, Америка и Африка. Каждый текст написан своими словами и ссылается на исходный материал.",
   "Политика Кипра, [экономика](/ru/economy/) и [туризм](/ru/tourism/) остаются в своих разделах. Здесь — новости остального мира."]},
 "el":{
  "tourism":[
   "Ειδήσεις τουρισμού από την Κύπρο: ποιοι έρχονται, πώς ταξιδεύουν και τι αλλάζει σε παραλίες, διακοπές και πόλεις που ζουν από επισκέπτες.",
   "Για ένα ταξίδι και όχι για την είδηση, δείτε τους [οδηγούς ταξιδιού](/el/travel/) και τις [εκδηλώσεις στην Κύπρο](/el/events/).",
   "Όσοι μένουν περισσότερο μπορούν να ξεκινήσουν από τη [μετακόμιση και τη ζωή στην Κύπρο](/el/relocation/) και από την [οικονομία](/el/economy/) για τιμές, φόρους και δουλειά."],
  "economy":[
   "Η οικονομία ακολουθεί τιμές, φόρους, ενέργεια, δουλειά, συντάξεις και δημόσιο χρήμα στην Κύπρο. Κάθε κείμενο είναι αναδιατύπωση και συνδέεται με την πηγή του.",
   "Το κόστος στέγασης είναι στα [ακίνητα](/el/real-estate/). Όσοι έρχονται για δουλειά διαβάζουν και τη [μετακόμιση](/el/relocation/), και οι δαπάνες επισκεπτών τον [τουρισμό](/el/tourism/)."],
  "real-estate":[
   "Ακίνητα στην Κύπρο: πολεοδομία, νεόδμητα, ενοίκια και μεταπωλήσεις. Οι αγγελίες διαφημιζόμενων, όταν υπάρχουν, μπαίνουν πάνω από τις ειδήσεις.",
   "Πρακτικές σελίδες για αγορά και ενοίκιο είναι στους [οδηγούς](/el/guides/). Το κόστος ζωής είναι στην [οικονομία](/el/economy/) και η αρχή μιας μετακόμισης στη [μετακόμιση](/el/relocation/)."],
  "world":[
   "Τα διεθνή νέα χωρίζονται σε περιοχές: Ευρώπη, Μέση Ανατολή, Ρωσία και ΚΑΚ, Ασία, Αμερική και Αφρική. Κάθε κείμενο είναι δική μας διατύπωση και συνδέεται με το αρχικό ρεπορτάζ.",
   "Η πολιτική της Κύπρου, η [οικονομία](/el/economy/) και ο [τουρισμός](/el/tourism/) μένουν στις δικές τους ενότητες. Εδώ είναι ο υπόλοιπος κόσμος."]}}
REGION_D = {
 "en":{
  "europe":"Europe news: the EU, Britain and the Mediterranean, rewritten from the linked reports.","middle-east":"Middle East news from the Gulf, Israel, Iraq and the wider region, with sources linked.","russia-cis":"News from Russia, Ukraine and the CIS, rewritten from the linked reports.","asia":"Asia news from East, South and Southeast Asia, with sources linked.","americas":"News from the Americas, rewritten from the linked reports.","africa":"Africa news, rewritten from the linked reports."},
 "ru":{
  "europe":"Новости Европы: ЕС, Британия и Средиземноморье, пересказ со ссылками на источники.","middle-east":"Новости Ближнего Востока: Залив, Израиль, Ирак и соседние страны, со ссылками на источники.","russia-cis":"Новости России, Украины и СНГ, пересказ со ссылками на источники.","asia":"Новости Азии — Восточной, Южной и Юго-Восточной — со ссылками на источники.","americas":"Новости Северной и Южной Америки, пересказ со ссылками на источники.","africa":"Новости Африки, пересказ со ссылками на источники."},
 "el":{
  "europe":"Ειδήσεις Ευρώπης: ΕΕ, Βρετανία και Μεσόγειος, με συνδέσμους στις πηγές.","middle-east":"Ειδήσεις Μέσης Ανατολής από τον Κόλπο, το Ισραήλ, το Ιράκ και τη γύρω περιοχή, με πηγές.","russia-cis":"Ειδήσεις από Ρωσία, Ουκρανία και ΚΑΚ, με συνδέσμους στις πηγές.","asia":"Ειδήσεις Ασίας από την ανατολική, νότια και νοτιοανατολική Ασία, με πηγές.","americas":"Ειδήσεις από την Αμερική, με συνδέσμους στις πηγές.","africa":"Ειδήσεις Αφρικής, με συνδέσμους στις πηγές."}}
def collection_ld(l, name, path, desc, stories):
    page={"@context":"https://schema.org","@type":"CollectionPage","name":name,"url":abs_(path),"inLanguage":l,"description":desc,"isPartOf":{"@type":"WebSite","name":SITE,"url":abs_(f"/{l}/")}}
    if stories:
        page["mainEntity"]={"@type":"ItemList","itemListElement":[{"@type":"ListItem","position":i+1,"url":abs_(f"/{l}/{s['slug']}/"),"name":s["title"][l]} for i,s in enumerate(stories[:30])]}
    return page
def page_cat(l,c):
    u=UI[l]; pathfn=lambda x:f"/{x}/{c}/"
    items=[s for s in sorted_all() if s["cat"]==c]
    news_items=[s for s in items if not s.get("guide")]
    guide_items=[s for s in items if s.get("guide") and l not in s.get("missing",())]
    title=CAT_TITLE[l][c]
    desc=CAT_D[l][c]
    kws=[CATN[l][c]]+GKW[l][:6]
    path=f"/{l}/{c}/"
    ld=[collection_ld(l, CATN[l][c], path, desc, news_items),
        breadcrumb_ld([(u["crumb_home"], f"/{l}/"), (CATN[l][c], path)])]
    og_story=news_items[0] if news_items else items[0]
    og,og_w,og_h=og_image(og_story)
    h=head(l,title,desc,kws,path,pathfn,og,jsonld=ld,og_w=og_w,og_h=og_h)+header(l,pathfn,c)
    block=listings_block(l) if c=="real-estate" else ""
    news=f'<h2 class="pnews">{e(LISTING_UI[l]["news"])}</h2>' if c=="real-estate" else ""
    grid="".join(card(s,l,lazy=(i>2)) for i,s in enumerate(news_items))
    extra=""
    if guide_items:
        extra=(f'<h2 class="sec"><a href="{href(f"/{l}/guides/")}">{e(GUIDE_MENU[l])}</a></h2>'
               f'<div class="grid g3">'+"".join(card(s,l) for s in guide_items)+'</div>')
    regions=region_nav(l) if c=="world" else ""
    paras=CAT_BODY.get(l,{}).get(c)
    lead=intro_html(paras) if paras else f'<p class="meta" style="margin-top:-6px">{e(desc)}</p>'
    trezor=trezor_box(l) if c=="economy" else ""
    crumb=f'<nav class="crumb" aria-label="breadcrumb"><a href="{href(f"/{l}/")}">{e(u["crumb_home"])}</a> › <span>{e(CATN[l][c])}</span></nav>'
    h+=f'<main id="main" class="wrap">{crumb}<h1 class="sec">{e(CATN[l][c])}</h1>{lead}{trezor}{regions}{block}{news}<div class="grid g3" style="margin-top:18px">{grid}</div>{extra}</main>'+footer(l)
    if trezor:
        h=h.replace("</body></html>", affiliate_boot()+"</body></html>", 1)
    return h
def page_region(l, r):
    if r not in REGIONS:
        raise SystemExit(f"unknown region {r}")
    u=UI[l]
    path=f"/{l}/world/{r}/"
    pathfn=lambda x, r=r: f"/{x}/world/{r}/"
    items=[s for s in sorted_all() if s.get("region")==r and not s.get("guide")]
    name=REGION_N[l][r]
    title=f'{name} — {CAT_TITLE[l]["world"]}'
    desc=REGION_D[l][r]
    ld=[collection_ld(l, name, path, desc, items),
        breadcrumb_ld([(u["crumb_home"], f"/{l}/"), (CATN[l]["world"], f"/{l}/world/"), (name, path)])]
    if items:
        og,og_w,og_h=og_image(items[0])
    else:
        og,og_w,og_h="/assets/og-default.jpg",1200,630
    h=head(l, title, desc, [name, CATN[l]["world"], SITE], path, pathfn, og, jsonld=ld, og_w=og_w, og_h=og_h)+header(l, pathfn, "world")
    grid="".join(card(s,l,lazy=(i>2)) for i,s in enumerate(items))
    empty={"en":"No stories in this region yet.","ru":"В этом регионе пока нет материалов.","el":"Δεν υπάρχουν ακόμη θέματα σε αυτή την περιοχή."}[l]
    h+=f'<main id="main" class="wrap"><nav class="crumb" aria-label="breadcrumb"><a href="{href(f"/{l}/")}">{e(u["crumb_home"])}</a> › <a href="{href(f"/{l}/world/")}">{e(CATN[l]["world"])}</a> › <span>{e(name)}</span></nav>'
    h+=f'<h1 class="sec">{e(name)}</h1><div class="intro"><p>{e(desc)}</p></div>{region_nav(l, r)}'
    h+=f'<div class="grid g3" style="margin-top:18px">{grid or "<p>"+e(empty)+"</p>"}</div></main>'+footer(l)
    return h

def article_times(s):
    """Stable published time. Updated time stays equal unless the story records a later update."""
    pub=f'{s["date"]}T09:00:00+02:00'
    raw=(s.get("updated") or "").strip()
    if not raw:
        return pub, pub
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raw=raw+"T09:00:00+02:00"
    published=datetime.datetime.fromisoformat(pub)
    modified=datetime.datetime.fromisoformat(raw)
    if modified < published:
        return pub, pub
    return pub, raw
def fdt(iso,l):
    dt=datetime.datetime.fromisoformat(iso)
    return f'{fdate(dt.date().isoformat(),l)}, {dt.strftime("%H:%M")} (EET)'
_URL_RE = re.compile(r"https?://[^\s<]+")
_MD_LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+|/[^)\s]+)\)")
_OFFER_RE = re.compile(r"^\{\{offer:([a-z0-9]+)\}\}$")
_TRAVEL_RE = re.compile(r"^\{\{travel:([A-Z0-9_]+)\|([^\n}]+)\}\}$")
_FIGURE_RE = re.compile(r"^\{\{figure:([a-z0-9-]+)\}\}$")
def _ext_rel(url):
    """Temu and Travelpayouts links are sponsored. Other outbound links stay ordinary."""
    if "temu.to/" in url or "://temu.to" in url or "tpx.lt" in url:
        return "sponsored nofollow noopener"
    return "noopener"
def linkify(text):
    """Article text stays plain. A bare URL becomes a link after it is escaped."""
    def repl(m):
        url = m.group(0)
        tail = ""
        while url and url[-1] in ".,;:)":
            tail = url[-1] + tail
            url = url[:-1]
        if not url:
            return m.group(0)
        return f'<a href="{url}" target="_blank" rel="{_ext_rel(url)}">{url}</a>{tail}'
    return _URL_RE.sub(repl, e(text))
def render_inline(text):
    """Bare URLs stay links. A [label](url) or [label](/path/) is a labelled link."""
    parts = []; pos = 0
    for m in _MD_LINK.finditer(text):
        parts.append(linkify(text[pos:m.start()]))
        label, url = m.group(1), m.group(2)
        if url.startswith("/"):
            parts.append(f'<a href="{e(href(url))}">{e(label)}</a>')
        else:
            parts.append(f'<a href="{e(url)}" target="_blank" rel="{_ext_rel(url)}">{e(label)}</a>')
        pos = m.end()
    parts.append(linkify(text[pos:]))
    return "".join(parts)
def plain_body(paras):
    out = []
    for p in paras:
        raw = p.strip()
        if _OFFER_RE.match(raw) or _TRAVEL_RE.match(raw) or _FIGURE_RE.match(raw): continue
        if raw.startswith("### "):
            out.append(raw[4:].strip()); continue
        if raw.startswith("## "):
            out.append(raw[3:].strip()); continue
        lines = raw.split("\n")
        if len(lines) >= 1 and all(x.startswith(("- ", "* ")) for x in lines):
            out.append(" ".join(x[2:].strip() for x in lines)); continue
        if raw.startswith("|"):
            bits = []
            for line in lines:
                if re.match(r"^\|?\s*:?-{3,}", line.replace("|", "").strip()) or set(line) <= set("|-: "):
                    continue
                bits.append(re.sub(r"\s+", " ", line.replace("|", " ")).strip())
            out.append(" ".join(x for x in bits if x)); continue
        out.append(raw)
    return " ".join(out)
def load_affiliates():
    path = os.path.join(HERE, "affiliates.json")
    with open(path, encoding="utf8") as f: data = json.load(f)
    if not isinstance(data, dict) or not data:
        raise SystemExit("source/affiliates.json must map partner keys to URLs")
    urls, search = {}, {}
    for key, value in data.items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9]+", key):
            raise SystemExit(f"source/affiliates.json: bad partner key {key!r}")
        if isinstance(value, str) and value.strip():
            urls[key] = value.strip()
            continue
        if isinstance(value, dict):
            url = _clean(value.get("url"))
            pattern = _clean(value.get("search"))
            if not url:
                raise SystemExit(f"source/affiliates.json: {key} needs a url")
            urls[key] = url
            if pattern:
                if "{query}" not in pattern:
                    raise SystemExit(f"source/affiliates.json: {key} search pattern needs {{query}}")
                search[key] = pattern
            continue
        raise SystemExit(f"source/affiliates.json: {key} needs a URL")
    return urls, search
AFFILIATES, AFFILIATE_SEARCH = load_affiliates()
TRAVEL_LINK_KEYS = ("BOOKING_URL","GETYOURGUIDE_URL","DISCOVERCARS_URL","AIRALO_URL","YESIM_URL","KLOOK_URL","KIWITAXI_URL","WELCOME_PICKUPS_URL","AVIASALES_URL","SAFETYWING_URL")
def load_travel_links():
    path = os.path.join(HERE, "travel_affiliates.json")
    with open(path, encoding="utf8") as f: data = json.load(f)
    if not isinstance(data, dict):
        raise SystemExit("source/travel_affiliates.json must be an object")
    missing = [k for k in TRAVEL_LINK_KEYS if not isinstance(data.get(k), str) or not data[k].strip()]
    if missing:
        raise SystemExit(f"source/travel_affiliates.json missing {missing}")
    extra = [k for k in data if k not in TRAVEL_LINK_KEYS]
    if extra:
        raise SystemExit(f"source/travel_affiliates.json unexpected keys {extra}")
    return {k: data[k].strip() for k in TRAVEL_LINK_KEYS}
TRAVEL_LINKS = load_travel_links()
# Compact row for relevant stories. Marker 808586, short links only.
# Guide buttons above keep source/travel_affiliates.json (marker 603740).
_ACCENT = str.maketrans({"ά":"α","έ":"ε","ή":"η","ί":"ι","ό":"ο","ύ":"υ","ώ":"ω","ϊ":"ι","ϋ":"υ","ΐ":"ι","ΰ":"υ","ё":"е","’":"'","ʼ":"'","`":"'"})
def _fold(text):
    return (text or "").casefold().translate(_ACCENT)
_TRAVEL_SKIP = re.compile(r"страхов|insurance|ασφαλ")
_TRAVEL_TOPIC = re.compile(
    r"\b(tourists?|tourism|holidays?|vacations?|excursions?|sightseeing|travel)\b"
    r"|туризм\w*|туристы\b|туристов\b|туриста\b|туристом\b|туристами\b|туристическ\w*"
    r"|отпуск\w*|каникул\w*"
    r"|τουρισμ\w*|τουριστ\w*|διακοπε\w*|διακοπων|εκδρομ\w*")
_AIRPORT_TOPIC = re.compile(
    r"\b(larnaca|paphos|cyprus)\b.{0,48}\b(airport|airports|flight|flights|airline)s?\b"
    r"|\b(airport|airports|flight|flights|airline)s?\b.{0,48}\b(larnaca|paphos|cyprus)\b"
    r"|ларнак\w*.{0,48}(аэропорт\w*|авиабилет\w*|авиарейс\w*|рейс\w*)"
    r"|(аэропорт\w*|авиабилет\w*|авиарейс\w*|рейс\w*).{0,48}ларнак\w*"
    r"|пафос\w*.{0,48}(аэропорт\w*|авиабилет\w*|авиарейс\w*|рейс\w*)"
    r"|(аэропорт\w*|авиабилет\w*|авиарейс\w*|рейс\w*).{0,48}пафос\w*"
    r"|(аэропорт\w*|авиабилет\w*|авиарейс\w*|рейс\w*).{0,48}кипр\w*"
    r"|кипр\w*.{0,48}(аэропорт\w*|авиабилет\w*|авиарейс\w*|рейс\w*)"
    r"|λαρνακ\w*.{0,48}(αεροδρομ\w*|αεροπορ\w*|πτησ\w*)"
    r"|(αεροδρομ\w*|αεροπορ\w*|πτησ\w*).{0,48}λαρνακ\w*"
    r"|\bπαφ\w*.{0,48}(αεροδρομ\w*|αεροπορ\w*|πτησ\w*)"
    r"|(αεροδρομ\w*|αεροπορ\w*|πτησ\w*).{0,48}\bπαφ\w*"
    r"|(αεροδρομ\w*|αεροπορ\w*|πτησ\w*).{0,48}κυπρ\w*"
    r"|κυπρ\w*.{0,48}(αεροδρομ\w*|αεροπορ\w*|πτησ\w*)")
_BEACH_TOPIC = re.compile(
    r"\bbeaches?\b|\bgovernor'?s beach\b|\bsea temperature\b|\bweather\b"
    r"|пляж\w*|погод\w*|температур\w* моря"
    r"|\bπαραλι\w*|\bκαιρ\w*")
_CAR_TOPIC = re.compile(
    r"\b(car hire|car rental|hire car|renting a car|rent a car)\b"
    r"|аренд\w* (?:авто|машин\w*)|прокат\w* (?:авто|машин\w*)"
    r"|ενοικιασ\w* αυτοκιν\w*")
_STAY_TOPIC = re.compile(
    r"\b(hotels?|resorts?|where to stay)\b"
    r"|отел\w*|гостиниц\w*|где остановиться"
    r"|ξενοδοχ\w*|που να μεινετε")
_ESIM_TOPIC = re.compile(r"\be-?sim\b")
_EVENT_TOPIC = re.compile(
    r"\b(festivals?|christmas|xmas|carnival|things to do|public holiday|bank holiday)\b"
    r"|фестивал\w*|рождеств\w*|карнавал\w*|чем заняться|что делать на кипре|празднич\w*|праздник\w*"
    r"|φεστιβαλ|χριστουγεν\w*|καρναβαλ\w*|τι να κανω|τι να κανετε|αξιοθεατ\w*|εκδηλωσ\w*")
_TRANSPORT_TOPIC = re.compile(
    r"\b(taxis?|airport transfer|public transport)\b"
    r"|такси|трансфер\w*"
    r"|\bταξι\b")
# A beach word inside a property listing, or "space weather", is not a trip.
_NOT_A_BEACH = re.compile(
    r"space weather|космическ\w* погод|διαστημικ\w* καιρ"
    r"|διαμερισμ|ακινητ|квартир|апартамент|\bapartments?\b")
# Politics, the economy and world news need the travel words in the title.
# A tag such as "tourism revenue" on an investment story is not enough.
_TITLE_ONLY_CATS = {"politics", "economy", "world"}
_CRIME_TOPIC = re.compile(
    r"\b(murder(?:ed)?|arrest(?:ed)?|crime|police|eviction|stabbing|stabbed|suspect|killed|homicide|fraud|dies|died|death|dead|cannabis|seized|seizure|narcotics|drugs)\b"
    r"|убийств\w*|арест\w*|задержан\w*|полици\w*|выселен\w*|ножев\w*|подозрева\w*|умер\w*|смерт\w*|погиб\w*"
    r"|каннабис\w*|изъял\w*|наркотик\w*"
    r"|δολοφον\w*|συλληψ\w*|συνεληφθ\w*|αστυνομ\w*|εξωσ\w*|μαχαιρ\w*|θανατ\w*"
    r"|κανναβ\w*|κατασχε\w*|ναρκωτικ\w*")
def _travel_fields(s, titles_only=False):
    fields=[]
    for l in LANGS:
        fields.append(_fold(s["title"][l]))
        if not titles_only:
            fields.extend(_fold(k) for k in s["kw"][l])
    return [f for f in fields if f]
def _topic_hit(fields, rx, skip_insurance=False):
    for field in fields:
        if skip_insurance and _TRAVEL_SKIP.search(field):
            continue
        if rx.search(field):
            return True
    return False
def _beach_hit(fields):
    for field in fields:
        if _NOT_A_BEACH.search(field):
            continue
        if _BEACH_TOPIC.search(field):
            return True
    return False
def _travel_topic(fields):
    return (_topic_hit(fields, _TRAVEL_TOPIC, skip_insurance=True) or _topic_hit(fields, _AIRPORT_TOPIC)
            or _beach_hit(fields) or _topic_hit(fields, _CAR_TOPIC) or _topic_hit(fields, _STAY_TOPIC)
            or _topic_hit(fields, _ESIM_TOPIC) or _topic_hit(fields, _EVENT_TOPIC) or _topic_hit(fields, _TRANSPORT_TOPIC))
def travel_relevant(s):
    """Tourism always. Elsewhere, title or tags in any language.
    Politics, economy and world news match on the title only, so a finance tag does not qualify.
    A crime story that merely names an airport or a beach stays clear."""
    if s.get("cat")=="tourism":
        return True
    fields=_travel_fields(s)
    scope=_travel_fields(s, titles_only=True) if s.get("cat") in _TITLE_ONLY_CATS else fields
    if not _travel_topic(scope) or _topic_hit(fields, _CRIME_TOPIC):
        return False
    return True
def travel_context(s):
    """Card order. Airport and beach are the explicit cases; car, stay and events are cheap to detect."""
    fields=_travel_fields(s)
    titles=_travel_fields(s, titles_only=True)
    if _topic_hit(titles, _ESIM_TOPIC): return "esim"
    if _topic_hit(titles, _CAR_TOPIC): return "car"
    if _topic_hit(titles, _STAY_TOPIC): return "stay"
    if _topic_hit(fields, _AIRPORT_TOPIC): return "airport"
    if _beach_hit(fields): return "beach"
    if _topic_hit(titles, _TRANSPORT_TOPIC): return "transfer"
    if _topic_hit(fields, _EVENT_TOPIC): return "event"
    return "default"
_TICO = {
 "car":'<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M4 15h16M6.2 15 8 9.6A1.6 1.6 0 0 1 9.5 8.4h5a1.6 1.6 0 0 1 1.5 1.2L17.8 15"/><circle cx="8" cy="16.6" r="1.5" fill="currentColor" stroke="none"/><circle cx="16" cy="16.6" r="1.5" fill="currentColor" stroke="none"/></svg>',
 "plane":'<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="m21.2 13.1-7.6-2.1-.3-6.2a1.15 1.15 0 0 0-2.3 0l-.2 6.2-7.8 2.1v1.7l7.6-1.3v4.4l-2.1 1.5v1.5l3.7-1.1 3.7 1.1v-1.5l-2.1-1.5v-4.4l7.4 1.3z"/></svg>',
 "taxi":'<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="M9 5h6v2.4H9z"/><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M4 15h16M6.2 15 8 10h8l1.8 5"/><circle cx="8" cy="16.7" r="1.5" fill="currentColor" stroke="none"/><circle cx="16" cy="16.7" r="1.5" fill="currentColor" stroke="none"/></svg>',
 "pin":'<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" d="M12 21s6-5.1 6-10a6 6 0 1 0-12 0c0 4.9 6 10 6 10z"/><circle cx="12" cy="11" r="2.1" fill="currentColor" stroke="none"/></svg>',
 "ticket":'<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M4 8.5A2 2 0 0 0 6 7h12a2 2 0 0 0 2 1.5 2 2 0 0 1 0 4A2 2 0 0 0 18 17H6a2 2 0 0 0-2-1.5 2 2 0 0 1 0-4z"/><path stroke="currentColor" stroke-width="1.8" stroke-dasharray="1.5 2.2" d="M12 7.5v9"/></svg>',
 "sim":'<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" d="M7 3.5h6.2L18.5 8.8V20.5H7z"/><rect x="9.2" y="11" width="5.6" height="5.2" rx="1" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
}
# Six cards. The seventh offer is dropped when it is the least useful for that story.
TRAVEL_OFFERS = (
 ("localrent","https://localrent.tpx.lt/XVEtrVFd","car",{"en":"Car rental","ru":"Аренда авто","el":"Αυτοκίνητο"}),
 ("welcome","https://tpx.lt/HeqeBOtK","plane",{"en":"Larnaca transfer","ru":"Трансфер из Ларнаки","el":"Μεταφορά Λάρνακας"}),
 ("kiwitaxi","https://kiwitaxi.tpx.lt/TTuXoyTH","taxi",{"en":"Cyprus transfers","ru":"Трансферы","el":"Μεταφορές"}),
 ("klook","https://klook.tpx.lt/xtutlwca","pin",{"en":"Tours","ru":"Экскурсии","el":"Εκδρομές"}),
 ("tiqets","https://tiqets.tpx.lt/PUqK4uu8","ticket",{"en":"Tickets","ru":"Билеты","el":"Εισιτήρια"}),
 ("airalo","https://airalo.tpx.lt/Z3nl2F1z","sim",{"en":"eSIM","ru":"eSIM","el":"eSIM"}),
 ("aviasales","https://aviasales.tpx.lt/45iBpc4b","plane",{"en":"Flights","ru":"Авиабилеты","el":"Πτήσεις"}),
)
TRAVEL_OFFER = {item[0]: item for item in TRAVEL_OFFERS}
TRAVEL_ORDER = {
 "airport": ("welcome","aviasales","airalo","kiwitaxi","localrent","klook"),
 "beach": ("klook","localrent","tiqets","aviasales","airalo","kiwitaxi"),
 "car": ("localrent","klook","kiwitaxi","welcome","aviasales","airalo"),
 "stay": ("localrent","klook","aviasales","welcome","airalo","tiqets"),
 "esim": ("airalo","aviasales","welcome","kiwitaxi","klook","localrent"),
 "transfer": ("kiwitaxi","welcome","localrent","aviasales","airalo","klook"),
 "event": ("tiqets","klook","localrent","kiwitaxi","aviasales","airalo"),
 "default": ("klook","tiqets","localrent","aviasales","airalo","kiwitaxi"),
}
TRAVEL_BOX = {
 "en": ("Travel in Cyprus", "Affiliate links", ": we may earn a commission at no extra cost to you."),
 "ru": ("Путешествие по Кипру", "Партнёрские ссылки", ": мы можем получить комиссию без доплаты для вас."),
 "el": ("Ταξίδι στην Κύπρο", "Σύνδεσμοι συνεργατών", ": ενδέχεται να λάβουμε προμήθεια χωρίς επιπλέον χρέωση για εσάς."),
}
def travel_box_html(l, context):
    title, lead, rest = TRAVEL_BOX[l]
    keys = TRAVEL_ORDER[context]
    if len(keys) < 4 or len(keys) > 6:
        raise SystemExit(f"travel block context {context} needs 4 to 6 cards")
    cards=[]
    for key in keys:
        _id, url, icon, labels = TRAVEL_OFFER[key]
        cards.append(
            f'<li><a href="{e(url)}" target="_blank" rel="sponsored nofollow noopener">'
            f'{_TICO[icon]}<span>{e(labels[l])}</span></a></li>')
    disc=href(f"/{l}/affiliate-disclosure/")
    return (f'<aside class="travelbox" data-travel="{e(context)}" aria-label="{e(title)}">'
            f'<h2>{e(title)}</h2><ul class="travelcards">{"".join(cards)}</ul>'
            f'<p class="fine"><a href="{disc}">{e(lead)}</a>{e(rest)}</p></aside>')
def travel_box(l, s):
    if not travel_relevant(s): return ""
    return travel_box_html(l, travel_context(s))
def affiliate_href(key, query=None):
    """Partner URL from the config. A query fills that partner's {query} search pattern."""
    if key not in AFFILIATES:
        raise SystemExit(f"unknown partner {key}; add it to source/affiliates.json")
    if not query:
        return AFFILIATES[key]
    pattern = AFFILIATE_SEARCH.get(key)
    if not pattern:
        raise SystemExit(f"source/affiliates.json: {key} has no search pattern")
    return pattern.replace("{query}", quote_plus(query))
def affiliates_js():
    comment = ("/* Generated from source/affiliates.json. Edit that file.\n"
               "   A site rebuild overwrites this script. Every partner button reads\n"
               "   window.CYNEWS_AFFILIATES. A button with data-affiliate-query fills\n"
               "   {query} in window.CYNEWS_AFFILIATE_SEARCH. Replace a #AFFILIATE_…\n"
               "   value with the real URL. */\n")
    return (comment
            + "window.CYNEWS_AFFILIATES = " + json.dumps(AFFILIATES, ensure_ascii=False, indent=2) + ";\n"
            + "window.CYNEWS_AFFILIATE_SEARCH = " + json.dumps(AFFILIATE_SEARCH, ensure_ascii=False, indent=2) + ";\n")
def affiliate_boot():
    return (f'<script src="{href("/assets/js/affiliates.js")}"></script><script>'
            '(function(){var map=window.CYNEWS_AFFILIATES||{};'
            'var search=window.CYNEWS_AFFILIATE_SEARCH||{};'
            'document.querySelectorAll("[data-affiliate]").forEach(function(a){'
            'var k=a.getAttribute("data-affiliate");'
            'var q=a.getAttribute("data-affiliate-query");'
            'if(q&&search[k])a.setAttribute("href",search[k].replace("{query}",encodeURIComponent(q).replace(/%20/g,"+")));'
            'else if(Object.prototype.hasOwnProperty.call(map,k)&&typeof map[k]==="string"&&map[k])a.setAttribute("href",map[k]);'
            'if(!a.getAttribute("rel"))a.setAttribute("rel","nofollow sponsored noopener");'
            'a.setAttribute("target","_blank");'
            '});})();</script>')
def offer_html(offer):
    partner = offer["partner"]
    if partner not in AFFILIATES:
        raise SystemExit(f"unknown partner {partner}; add it to source/affiliates.json")
    note = f'<p>{render_inline(offer["note"])}</p>' if offer.get("note") else ""
    return (f'<aside class="offer">{note}<div class="affbtns">'
            f'<a class="affbtn" data-affiliate="{e(partner)}" href="{e(AFFILIATES[partner])}" '
            f'rel="nofollow sponsored noopener" target="_blank">{e(offer["label"])}</a></div></aside>')
def render_table(text):
    rows = []
    for line in text.split("\n"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue
        rows.append(cells)
    if len(rows) < 2:
        raise SystemExit("a table needs a header and at least one row")
    width = len(rows[0])
    head = "".join(f"<th>{render_inline(c)}</th>" for c in rows[0])
    body = []
    for row in rows[1:]:
        padded = row + [""] * (width - len(row))
        body.append("<tr>" + "".join(f"<td>{render_inline(c)}</td>" for c in padded[:width]) + "</tr>")
    return f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
def figure_block(l, key):
    """An extra photograph already credited and used as some story's lead, so the file is built."""
    story = next((item for item in STORIES if item.get("img") == key and "upload" not in item), None)
    if story is None or key not in CREDITS:
        raise SystemExit(f"unknown figure {key}")
    alt = CREDITS[key].get("depicts") or story["alt"].get(l) or story["title"][l]
    stub = dict(story)
    stub["alt"] = {x: alt for x in LANGS}
    cap = photo_caption(stub, l)
    return (f'<figure class="shot">{img_tag(stub, l, 1200, True, False, "(max-width:800px) 100vw,760px")}'
            f'{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>')
def render_body(l, s):
    offers = s["offers"][l]
    parts = []
    seen = set()
    for p in s["body"][l]:
        raw = p.strip()
        m = _OFFER_RE.match(raw)
        if m:
            key = m.group(1)
            if key not in offers:
                raise SystemExit(f'{s["slug"]}: {l} uses {{{{offer:{key}}}}} without an offer label')
            parts.append(offer_html(offers[key]))
            seen.add(key)
            continue
        tm = _TRAVEL_RE.match(raw)
        if tm:
            key, label = tm.group(1), tm.group(2).strip()
            url = TRAVEL_LINKS.get(key)
            if not url:
                raise SystemExit(f'{s["slug"]}: unknown travel link {key}')
            parts.append(f'<p class="affbtns"><a class="affbtn" href="{e(url)}" rel="sponsored nofollow noopener" target="_blank">{e(label)}</a></p>')
            continue
        fm = _FIGURE_RE.match(raw)
        if fm:
            parts.append(figure_block(l, fm.group(1)))
            continue
        if raw.startswith("### "):
            parts.append(f'<h3>{render_inline(raw[4:].strip())}</h3>')
            continue
        if raw.startswith("## "):
            parts.append(f'<h2>{render_inline(raw[3:].strip())}</h2>')
            continue
        lines = raw.split("\n")
        if all(x.startswith(("- ", "* ")) for x in lines):
            items = "".join(f"<li>{render_inline(x[2:].strip())}</li>" for x in lines)
            parts.append(f"<ul>{items}</ul>")
            continue
        if raw.startswith("|"):
            parts.append(render_table(raw))
            continue
        lone = _MD_LINK.fullmatch(raw)
        if lone and "tpx.lt" in lone.group(2):
            parts.append(f'<p class="affbtns"><a class="affbtn" href="{e(lone.group(2))}" rel="sponsored nofollow noopener" target="_blank">{e(lone.group(1))}</a></p>')
            continue
        parts.append(f'<p>{render_inline(p)}</p>')
    missing = [key for key in offers if key not in seen]
    if missing:
        raise SystemExit(f'{s["slug"]}: {l} offers not placed in the text: {missing}')
    return "".join(parts)
def faq_html(l, s):
    items = s["faq"][l]
    if not items: return ""
    blocks = []
    for item in items:
        blocks.append(f'<details><summary>{e(item["q"])}</summary><p>{render_inline(item["a"])}</p></details>')
    return f'<section class="faq" aria-label="{e(UI[l]["faq"])}"><h2>{e(UI[l]["faq"])}</h2>{"".join(blocks)}</section>'
def faq_ld(items):
    if not items: return None
    return {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
        {"@type":"Question","name":item["q"],"acceptedAnswer":{"@type":"Answer","text":item["a"]}} for item in items]}
def howto_ld(l, s):
    """HowTo only when the story supplies at least two steps that are on the page."""
    steps=s["steps"][l]
    if len(steps) < 2: return None
    return {"@context":"https://schema.org","@type":"HowTo","name":s["title"][l],
            "description":s["desc"][l] or s["lede"][l],"inLanguage":l,"image":[image_ld(s)],
            "step":[{"@type":"HowToStep","position":i+1,"name":step["name"],"text":step["text"]}
                    for i,step in enumerate(steps)]}
# Small partner box on practical pages only. News stories are left alone.
PARTNER_WIDGETS = {
 "relocating-to-cyprus": "insurance",
 "cyprus-resident-handbook": "security",
 "mortgage-cyprus-germany-greece-spain": "security",
 "fintech-jobs-not-registrations": "security",
}
WIDGET_COPY = {
 "insurance": {
  "en": dict(kicker="Partner offers", title="Health cover while you settle",
    text="A residence file does not include a health policy. Travel medical cover and a longer-stay plan are different products, and GeSY enrolment has its own rules.",
    link="International health insurance: an honest breakdown", slug="international-health-insurance",
    buttons=[("genki","See Genki plans")]),
  "ru": dict(kicker="Партнёрские предложения", title="Медицинская страховка на время переезда",
    text="Документы на проживание не включают медицинский полис. Туристическая страховка и полис для долгой жизни за границей — разные продукты, а запись в ГЕСИ идёт по своим правилам.",
    link="Международная медицинская страховка: честный разбор", slug="international-health-insurance",
    buttons=[("genki","Смотреть планы Genki")]),
  "el": dict(kicker="Προσφορές συνεργατών", title="Κάλυψη υγείας όσο τακτοποιείστε",
    text="Ο φάκελος διαμονής δεν περιλαμβάνει ασφαλιστήριο υγείας. Η ταξιδιωτική κάλυψη και ένα πρόγραμμα μακράς διαμονής είναι διαφορετικά προϊόντα, και η εγγραφή στο ΓεΣΥ έχει δικούς της κανόνες.",
    link="Διεθνής ασφάλιση υγείας: μια ειλικρινής ανάλυση", slug="international-health-insurance",
    buttons=[("genki","Δείτε τα προγράμματα Genki")]),
 },
 "security": {
  "en": dict(kicker="Partner offers", title="Accounts you open from abroad",
    text="A bank login, a tax portal and the email that can reset both are worth protecting before you rely on a café network or a new SIM.",
    link="How to protect data and accounts abroad", slug="protect-data-foreign-banks",
    buttons=[("nordvpn","See NordVPN"),("onepassword","See 1Password")]),
  "ru": dict(kicker="Партнёрские предложения", title="Счета, которые открывают из-за границы",
    text="Банковский вход, налоговый портал и почту, с которой оба можно сбросить, стоит защитить до того, как вы начнёте пользоваться сетью кафе или новой SIM.",
    link="Как защитить данные и счета за границей", slug="protect-data-foreign-banks",
    buttons=[("nordvpn","Смотреть NordVPN"),("onepassword","Смотреть 1Password")]),
  "el": dict(kicker="Προσφορές συνεργατών", title="Λογαριασμοί που ανοίγετε από το εξωτερικό",
    text="Μια τραπεζική είσοδος, μια φορολογική πύλη και το email που μπορεί να τα επαναφέρει και τα δύο αξίζει να προστατευτούν πριν βασιστείτε σε δίκτυο καφέ ή σε νέα SIM.",
    link="Πώς να προστατεύσετε δεδομένα και λογαριασμούς στο εξωτερικό", slug="protect-data-foreign-banks",
    buttons=[("nordvpn","Δείτε το NordVPN"),("onepassword","Δείτε το 1Password")]),
 },
}
_CRYPTO_RX = re.compile(
    r"\bcrypto(?:currency|currencies)?\b|\bbitcoin\b"
    r"|криптовалют\w*|криптоуслуг\w*|крипторежим\w*|\bкрипто\b"
    r"|κρυπτονομ\w*|κρυπτοϋπ\w*",
    re.I)
_CRYPTO_LINK = re.compile(r"\[[^\]]+\]\([^)]*cysec-forex-crypto[^)]*\)")
def crypto_story(s):
    """True when the article is about crypto, not when it only links to the CySEC guide."""
    chunks = []
    for lang in LANGS:
        chunks.append(s["title"][lang])
        chunks.append(s["lede"][lang])
        chunks.extend(s["kw"][lang])
        chunks.extend(s["body"][lang])
    text = _CRYPTO_LINK.sub(" ", "\n".join(chunks))
    return bool(_CRYPTO_RX.search(text))
TREZOR_BOX = {
 "en": dict(kicker="Affiliate", title="Trezor Safe 7",
    text="A hardware wallet keeps the keys on a device you hold, rather than only on an exchange account. This is an affiliate link. If you buy, CyNews 24 may earn a commission. Trezor sets the price. This is not investment advice.",
    button="Trezor Safe 7"),
 "ru": dict(kicker="Партнёрская ссылка", title="Trezor Safe 7",
    text="Аппаратный кошелёк хранит ключи на устройстве у вас, а не только на счёте биржи. Это партнёрская ссылка. Если вы купите, CyNews 24 может получить комиссию. Цену назначает Trezor. Это не инвестиционный совет.",
    button="Trezor Safe 7"),
 "el": dict(kicker="Σύνδεσμος συνεργάτη", title="Trezor Safe 7",
    text="Ένα hardware wallet κρατά τα κλειδιά σε συσκευή που έχετε εσείς, και όχι μόνο σε λογαριασμό ανταλλακτηρίου. Αυτός είναι σύνδεσμος συνεργάτη. Αν αγοράσετε, το CyNews 24 μπορεί να λάβει προμήθεια. Την τιμή την ορίζει η Trezor. Δεν είναι επενδυτική συμβουλή.",
    button="Trezor Safe 7"),
}
def trezor_box(l):
    copy = TREZOR_BOX[l]
    url = AFFILIATES["trezor"]
    disc = href(f"/{l}/affiliate-disclosure/")
    return (f'<aside class="partner trezor" aria-label="{e(copy["title"])}">'
            f'<p class="kicker">{e(copy["kicker"])}</p><h2>{e(copy["title"])}</h2>'
            f'<p>{e(copy["text"])}</p>'
            f'<div class="affbtns"><a class="affbtn" data-affiliate="trezor" href="{e(url)}" '
            f'rel="sponsored nofollow noopener" target="_blank">{e(copy["button"])}</a></div>'
            f'<p class="fine"><a href="{disc}">{e(UI[l]["disclosure"])}</a></p></aside>')
def partner_widget(l, s):
    kind = PARTNER_WIDGETS.get(s["slug"])
    # A named practical page keeps its partner box, including when the page is a guide.
    if not kind: return ""
    copy = WIDGET_COPY[kind][l]
    buttons = []
    for key, label in copy["buttons"]:
        if key not in AFFILIATES:
            raise SystemExit(f"widget partner {key} is missing from source/affiliates.json")
        buttons.append(f'<a class="affbtn" data-affiliate="{e(key)}" href="{e(AFFILIATES[key])}" rel="nofollow sponsored noopener" target="_blank">{e(label)}</a>')
    guide = href(f'/{l}/{copy["slug"]}/')
    disc = href(f'/{l}/affiliate-disclosure/')
    return (f'<aside class="partner" aria-label="{e(copy["title"])}">'
            f'<p class="kicker">{e(copy["kicker"])}</p><h2>{e(copy["title"])}</h2>'
            f'<p>{e(copy["text"])} <a href="{guide}">{e(copy["link"])}</a></p>'
            f'<div class="affbtns">{"".join(buttons)}</div>'
            f'<p class="fine"><a href="{disc}">{e(UI[l]["disclosure"])}</a></p></aside>')
# Search links only. Queries stay in the config's {query} pattern. No product codes.
AMAZON_NOTE = {
 "en": "As an Amazon Associate I earn from qualifying purchases.",
 "ru": "Как участник партнёрской программы Amazon я зарабатываю на соответствующих покупках.",
 "el": "Ως συνεργάτης της Amazon, κερδίζω από αγορές που πληρούν τις προϋποθέσεις.",
}
AMAZON_BLOCKS = {
 "relocating-to-cyprus": {
  "en": dict(title="A few things people pack",
    text="Cyprus uses the UK square-pin socket, so a European two-pin plug needs an adapter. A power bank and a luggage scale are ordinary packing, not part of the residence file. These open Amazon.de searches. They are not a review, and the results and prices change.",
    links=[("UK plug adapter (Type G)","UK plug adapter Type G"),("Power bank","power bank"),("Luggage scale","luggage scale")]),
  "ru": dict(title="Что часто кладут в чемодан",
    text="На Кипре розетки британского типа, с тремя прямоугольными штырями, поэтому европейская вилка с двумя штырями просит переходник. Пауэрбанк и весы для багажа — обычные дорожные вещи, к документам на проживание они не относятся. Ссылки открывают поиск на Amazon.de. Это не обзор, а выдача и цены меняются.",
    links=[("Переходник на британскую розетку","UK plug adapter Type G"),("Пауэрбанк","power bank"),("Весы для багажа","luggage scale")]),
  "el": dict(title="Τι βάζουν συχνά στη βαλίτσα",
    text="Η Κύπρος χρησιμοποιεί τη βρετανική πρίζα, με τρεις ορθογώνιες ακίδες, οπότε ένα ευρωπαϊκό διπολικό φις θέλει αντάπτορα. Ένα power bank και μια ζυγαριά αποσκευών είναι συνηθισμένα ταξιδιωτικά είδη και δεν ανήκουν στον φάκελο διαμονής. Οι σύνδεσμοι ανοίγουν αναζήτηση στο Amazon.de. Δεν είναι κριτική, και τα αποτελέσματα και οι τιμές αλλάζουν.",
    links=[("Αντάπτορας βρετανικής πρίζας","UK plug adapter Type G"),("Power bank","power bank"),("Ζυγαριά αποσκευών","luggage scale")]),
 },
 "international-health-insurance": {
  "en": dict(title="Packing is not a policy",
    text="A health policy does not put a plaster or a thermometer in the bag. A basic kit is ordinary travel packing. It is not treatment, and it does not replace a doctor or GeSY. These open Amazon.de searches, and prices change.",
    links=[("Travel first-aid kit","travel first aid kit"),("Digital thermometer","digital thermometer"),("UK plug adapter (Type G)","UK plug adapter Type G")]),
  "ru": dict(title="Аптечка — это не полис",
    text="Медицинский полис не кладёт пластырь и градусник в сумку. Простая аптечка — обычные дорожные вещи. Это не лечение и не замена врачу или ГЕСИ. Ссылки открывают поиск на Amazon.de, а цены меняются.",
    links=[("Дорожная аптечка","travel first aid kit"),("Электронный градусник","digital thermometer"),("Переходник на британскую розетку","UK plug adapter Type G")]),
  "el": dict(title="Το φαρμακείο δεν είναι συμβόλαιο",
    text="Ένα ασφαλιστήριο υγείας δεν βάζει τσιρότο ή θερμόμετρο στην τσάντα. Ένα βασικό κιτ είναι συνηθισμένη ταξιδιωτική προετοιμασία. Δεν είναι θεραπεία και δεν αντικαθιστά γιατρό ή το ΓεΣΥ. Οι σύνδεσμοι ανοίγουν αναζήτηση στο Amazon.de, και οι τιμές αλλάζουν.",
    links=[("Ταξιδιωτικό φαρμακείο","travel first aid kit"),("Ψηφιακό θερμόμετρο","digital thermometer"),("Αντάπτορας βρετανικής πρίζας","UK plug adapter Type G")]),
 },
 "protect-data-foreign-banks": {
  "en": dict(title="A hardware key, if the bank allows one",
    text="A hardware key survives a new SIM better than a text message, where the bank allows it. A USB data blocker is for charging from a socket you do not trust. A hardware wallet matters only if you hold crypto. These are Amazon.de searches, not a test of one model, and prices change.",
    links=[("Security key (YubiKey)","YubiKey"),("USB data blocker","USB data blocker"),("Hardware wallet","hardware wallet")]),
  "ru": dict(title="Аппаратный ключ, если банк его принимает",
    text="Аппаратный ключ переживает смену SIM лучше, чем код в SMS, если банк это разрешает. Блокиратор данных на USB нужен, когда заряжаешься от чужой розетки. Аппаратный кошелёк имеет смысл, только если у вас есть криптовалюта. Это поиск на Amazon.de, а не проверка одной модели, и цены меняются.",
    links=[("Ключ безопасности (YubiKey)","YubiKey"),("USB-блокиратор данных","USB data blocker"),("Аппаратный кошелёк","hardware wallet")]),
  "el": dict(title="Κλειδί υλικού, αν η τράπεζα το δέχεται",
    text="Ένα κλειδί υλικού αντέχει μια νέα SIM καλύτερα από ένα μήνυμα, όπου η τράπεζα το επιτρέπει. Ένας αποκλειστής δεδομένων USB είναι για φόρτιση από πρίζα που δεν εμπιστεύεστε. Ένα πορτοφόλι υλικού αφορά μόνο όποιον κρατά κρυπτονόμισμα. Αυτές είναι αναζητήσεις στο Amazon.de, όχι δοκιμή ενός μοντέλου, και οι τιμές αλλάζουν.",
    links=[("Κλειδί ασφαλείας (YubiKey)","YubiKey"),("Αποκλειστής δεδομένων USB","USB data blocker"),("Πορτοφόλι υλικού","hardware wallet")]),
 },
 "flights-to-cyprus": {
  "en": dict(title="What the cabin bag often needs",
    text="Cyprus uses the UK square-pin socket, so a European two-pin plug needs an adapter. A power bank and a luggage scale are ordinary packing, not a visa. These open Amazon.de searches. They are not a review, and the results and prices change.",
    links=[("UK plug adapter (Type G)","UK plug adapter Type G"),("Power bank","power bank"),("Luggage scale","luggage scale")]),
  "ru": dict(title="Что часто нужно в ручной клади",
    text="На Кипре розетки британского типа, с тремя прямоугольными штырями, поэтому европейская вилка с двумя штырями просит переходник. Пауэрбанк и весы для багажа — обычные дорожные вещи, не виза. Ссылки открывают поиск на Amazon.de. Это не обзор, а выдача и цены меняются.",
    links=[("Переходник на британскую розетку","UK plug adapter Type G"),("Пауэрбанк","power bank"),("Весы для багажа","luggage scale")]),
  "el": dict(title="Τι χρειάζεται συχνά η χειραποσκευή",
    text="Η Κύπρος χρησιμοποιεί τη βρετανική πρίζα, με τρεις ορθογώνιες ακίδες, οπότε ένα ευρωπαϊκό διπολικό φις θέλει αντάπτορα. Ένα power bank και μια ζυγαριά αποσκευών είναι συνηθισμένα ταξιδιωτικά είδη, όχι βίζα. Οι σύνδεσμοι ανοίγουν αναζήτηση στο Amazon.de. Δεν είναι κριτική, και τα αποτελέσματα και οι τιμές αλλάζουν.",
    links=[("Αντάπτορας βρετανικής πρίζας","UK plug adapter Type G"),("Power bank","power bank"),("Ζυγαριά αποσκευών","luggage scale")]),
 },
 "cyprus-resident-handbook": {
  "en": dict(title="Once you have the keys",
    text="A lease does not, by itself, let you change the lock. Ask the landlord before you fit one. An indoor camera covers your own rooms, not a neighbour’s. These are Amazon.de searches for setting up a home, not a security survey, and prices change.",
    links=[("Smart lock","smart lock"),("Home security camera","home security camera"),("Video doorbell","video doorbell")]),
  "ru": dict(title="Когда ключи уже у вас",
    text="Договор аренды сам по себе не разрешает менять замок. Спросите хозяина, прежде чем ставить свой. Камера внутри снимает ваши комнаты, а не соседа. Это поиск на Amazon.de для обустройства жилья, а не обследование охраны, и цены меняются.",
    links=[("Умный замок","smart lock"),("Камера для дома","home security camera"),("Видеозвонок","video doorbell")]),
  "el": dict(title="Όταν έχετε τα κλειδιά",
    text="Μια μίσθωση από μόνη της δεν επιτρέπει να αλλάξετε την κλειδαριά. Ρωτήστε τον ιδιοκτήτη πριν τοποθετήσετε μία. Μια κάμερα μέσα καλύπτει τα δικά σας δωμάτια, όχι τον γείτονα. Αυτές είναι αναζητήσεις στο Amazon.de για ένα σπίτι που στήνετε, όχι έλεγχος ασφάλειας, και οι τιμές αλλάζουν.",
    links=[("Έξυπνη κλειδαριά","smart lock"),("Κάμερα σπιτιού","home security camera"),("Θυροτηλέφωνο με κάμερα","video doorbell")]),
 },
}
def amazon_block(l, s):
    copy = (AMAZON_BLOCKS.get(s["slug"]) or {}).get(l)
    if not copy: return ""
    links = copy["links"]
    if not 2 <= len(links) <= 4:
        raise SystemExit(f'{s["slug"]}: Amazon block needs 2 to 4 links')
    buttons = []
    for label, query in links:
        if re.search(r"/dp/|B0[A-Z0-9]{8}", query):
            raise SystemExit(f'{s["slug"]}: Amazon links are searches, not product codes')
        buttons.append(
            f'<a class="affbtn" data-affiliate="amazon" data-affiliate-query="{e(query)}" '
            f'href="{e(affiliate_href("amazon", query))}" rel="sponsored nofollow noopener" target="_blank">{e(label)}</a>')
    disc = href(f'/{l}/affiliate-disclosure/')
    return (f'<aside class="partner amazon" aria-label="{e(copy["title"])}">'
            f'<p class="kicker">Amazon.de</p><h2>{e(copy["title"])}</h2>'
            f'<p>{e(copy["text"])}</p>'
            f'<div class="affbtns">{"".join(buttons)}</div>'
            f'<p class="fine">{e(AMAZON_NOTE[l])} <a href="{disc}">{e(UI[l]["disclosure"])}</a></p></aside>')
def page_moved(l, s):
    """Browser redirect from the CMS file name to the public address.

    GitHub Pages has no server redirects. The alias is noindex and its
    canonical points at the real article, so it is not a second copy.
    """
    target = abs_(f"/{l}/{s['slug']}/")
    title = s["title"][l]
    return (f'<!doctype html><html lang="{l}"><head><meta charset="utf-8">'
            f'<meta name="robots" content="noindex">'
            f'<link rel="canonical" href="{e(target)}">'
            f'<meta http-equiv="refresh" content="0;url={e(target)}">'
            f'<script>location.replace({json.dumps(target)});</script>'
            f'<title>{e(title)}</title></head>'
            f'<body><p><a href="{e(target)}">{e(title)}</a></p></body></html>')
# English settling guides. Each page links the others. A language without its own text is skipped.
SETTLING_GUIDES = (
 "relocating-to-cyprus",
 "buying-property-cyprus",
 "renting-apartment-cyprus",
 "cyprus-permanent-residency-300k",
 "best-areas-to-live-cyprus",
 "cyprus-pink-slip-visitor-visa",
 "digital-nomad-visa-cyprus",
 "moving-to-cyprus-with-pets",
 "cyprus-taxes-for-individuals",
 "cost-of-living-cyprus",
 "opening-bank-account-cyprus",
 "gesy-healthcare-cyprus",
 "schools-kindergartens-cyprus",
 "driving-license-car-cyprus",
)
READ_ALSO = {"en": "Read also", "ru": "Читайте также", "el": "Διαβάστε επίσης"}
def read_also_html(l, s):
    if s["slug"] not in SETTLING_GUIDES:
        return ""
    items = []
    for slug in SETTLING_GUIDES:
        if slug == s["slug"]:
            continue
        other = BYSLUG.get(slug)
        if not other or l in other.get("missing", ()):
            continue
        items.append(f'<li><a href="{href(f"/{l}/{slug}/")}">{e(other["title"][l])}</a></li>')
    if not items:
        return ""
    return (f'<section class="readalso" aria-label="{e(READ_ALSO[l])}">'
            f'<h2>{e(READ_ALSO[l])}</h2><ul>{"".join(items)}</ul></section>')
def page_article(l,s):
    u=UI[l]; path=f"/{l}/{s['slug']}/"; pathfn=lambda x:f"/{x}/{s['slug']}/"
    title=s["title"][l]
    # A guide can carry its own meta description. News keeps the full lede in
    # the article schema and the shortened lede in the meta description.
    desc=s["desc"][l] or trunc(s["lede"][l],158)
    schema_desc=s["desc"][l] or s["lede"][l]
    kws=s["kw"][l]+GKW[l][:4]
    pub,mod=article_times(s)
    og,og_w,og_h=og_image(s)
    # News stays NewsArticle. A practical guide is an Article: it is not a news report,
    # and it does not belong in the Google News sitemap.
    kind="Article" if s.get("guide") else "NewsArticle"
    trail=[(u["crumb_home"], f"/{l}/")]
    if s.get("guide"):
        section=GUIDE_MENU[l]
        trail.append((section, f"/{l}/guides/"))
        active="guides"
    elif s.get("region"):
        section=REGION_N[l][s["region"]]
        trail.append((CATN[l]["world"], f"/{l}/world/"))
        trail.append((section, f"/{l}/world/{s['region']}/"))
        active="world"
    else:
        section=CATN[l][s["cat"]]
        trail.append((section, f"/{l}/{s['cat']}/"))
        active=s["cat"]
    trail.append((title, path))
    about_place=REGION_N[l][s["region"]] if s.get("region") else "Cyprus"
    ld=[{"@context":"https://schema.org","@type":kind,"mainEntityOfPage":{"@type":"WebPage","@id":abs_(path)},"headline":title,"description":schema_desc,"image":[image_ld(s)],"datePublished":pub,"dateModified":mod,"inLanguage":l,"articleSection":section,"keywords":", ".join(s["kw"][l]),
        "author":author_ld(),"publisher":publisher_ld(),
        "isBasedOn":[x[1] for x in s["sources"]],"citation":[{"@type":"CreativeWork","name":x[0],"url":x[1]} for x in s["sources"]],"articleBody":plain_body(s["body"][l]),"url":abs_(path),
        "locationCreated":{"@type":"Place","name":"Cyprus"},"about":{"@type":"Place","name":about_place}},
      breadcrumb_ld(trail)]
    faq=faq_ld(s["faq"][l])
    if faq: ld.append(faq)
    howto=howto_ld(l, s)
    if howto: ld.append(howto)
    large,_,_,srcset=img_srcset(s)
    preload=f'<link rel="preload" as="image" href="{large}" imagesrcset="{srcset}" imagesizes="(max-width:800px) 100vw,760px">'
    # A missing translation repeats the Russian text, so it stays out of the index,
    # the sitemap and the hreflang cluster. robots_content adds the large image preview.
    robots = "noindex,follow" if l in s.get("missing", ()) else "index,follow,max-image-preview:large,max-snippet:-1"
    html_title=title if SITE in title else f"{title} | {SITE}"
    h=head(l,html_title,desc,kws,path,pathfn,og,"article",preload,ld,pub,mod,robots=robots,langs=indexed_langs(s),og_w=og_w,og_h=og_h)+header(l,pathfn,active)
    crumbs=" › ".join(f'<a href="{href(p)}">{e(n)}</a>' for n,p in trail[:-1])
    h+=f'<main id="main" class="wrap"><nav class="crumb" aria-label="breadcrumb">{crumbs}</nav>'
    h+=f'<article class="a"><span class="cat">{e(section)}</span><h1>{e(title)}</h1><p class="dek">{e(s["lede"][l])}</p>'
    h+=f'<div class="by"><span class="who">{e(u["byline"])}</span><span class="when"><time datetime="{pub}">{e(u["published"])}: {fdt(pub,l)}</time><time datetime="{mod}">{e(u["updated"])}: {fdt(mod,l)}</time></span></div>'
    h+=f'<figure>{img_tag(s,l,1200,False,True,"(max-width:800px) 100vw,760px")}{f"<figcaption>{photo_caption(s,l)}</figcaption>" if photo_caption(s,l) else ""}</figure>'
    notice=f'<p class="disclosure">{e(u["disclosure_text"])} <a href="{href(f"/{l}/affiliate-disclosure/")}">{e(u["disclosure"])}</a></p>' if s["offers"][l] else ""
    h+=f'<div class="body">{notice}{render_body(l,s)}</div>'
    h+=faq_html(l,s)
    h+=read_also_html(l,s)
    if s["sources"]:
        note=u["sources_note_guide"] if s.get("guide") else u["sources_note"]
        h+=f'<section class="src" aria-label="{u["sources"]}"><h2>{u["sources"]}</h2><p>{note}</p><ul>'+"".join(f'<li><a href="{e(x[1])}" target="_blank" rel="noopener nofollow">{e(x[0])}</a></li>' for x in s["sources"])+'</ul></section>'
    if s["kw"][l]:
        h+=f'<h2 style="font-size:16px;margin:0 0 8px">{u["tags"]}</h2><ul class="tags">'+"".join(f'<li>{e(k)}</li>' for k in s["kw"][l])+'</ul>'
    h+=f'<p class="langsw">'+" ".join(f'<a href="{href(pathfn(x))}" hreflang="{x}" lang="{x}">{LANGNAME[x]}</a>' for x in LANGS if x!=l)+'</p>'
    h+=travel_box(l, s)
    widget=partner_widget(l,s)
    amazon=amazon_block(l,s)
    h+=widget
    h+=amazon
    trezor=trezor_box(l) if crypto_story(s) else ""
    h+=trezor
    # Page language, immediately before the Telegram subscribe line.
    plain=[(p[3:].strip() if p.startswith("## ") else p) for p in s["body"][l] if not _OFFER_RE.match(p.strip())]
    h+=mycytax.article_crosslink(l, s["title"][l], plain, s["kw"][l], mycytax_catalog())
    cta=telegram_for(l)
    if cta:
        h+=f'<p class="tgcta"><a href="{e(cta)}" target="_blank" rel="noopener">{_icons()["telegram"]}<span>{e(u["tg_cta"])}</span></a></p>'
    h+='</article>'
    if s["slug"] in BBF_BY_SLUG:
        h+=similar_atex(l)
    h+=property_consult(l, abs_(path), BBF_BY_SLUG[s["slug"]]["project"] if s["slug"] in BBF_BY_SLUG else "")
    if s.get("guide"):
        others=[x for x in sorted_all() if x.get("guide") and x["slug"]!=s["slug"] and l not in x.get("missing",())]
        # Same section first, then newer guides.
        dated=sorted(others, key=lambda x:(x["cat"]!=s["cat"], x["date"]), reverse=True)
        dated.sort(key=lambda x:x["cat"]!=s["cat"])
        if dated:
            h+=f'<section class="rel"><h2><a href="{href(f"/{l}/guides/")}">{e(GUIDE_MENU[l])}</a></h2><div class="grid">'+"".join(card(x,l) for x in dated[:4])+'</div></section>'
    rel=[x for x in news_sorted() if x["slug"]!=s["slug"]]
    rel.sort(key=lambda x:((not s.get("region")) or x.get("region")!=s.get("region"), x["cat"]!=s["cat"]))
    region_more=""
    if s.get("region"):
        region_more=(f'<p class="meta"><a href="{href(f"/{l}/world/{s["region"]}/")}">{e(REGION_N[l][s["region"]])}</a>'
                     f' · <a href="{href(f"/{l}/world/")}">{e(CATN[l]["world"])}</a></p>')
    h+=f'<section class="rel"><h2>{u["related"]}</h2>{region_more}<div class="grid">'+"".join(card(x,l) for x in rel[:3])+'</div></section></main>'+footer(l)
    if s["offers"][l] or widget or amazon or trezor:
        h=h.replace("</body></html>", affiliate_boot()+"</body></html>", 1)
    return h

def info_body(l, page, kind):
    """Static info page. The contact section of About links to advertising, policy and privacy."""
    u=UI[l]
    parts=[]
    for i,(h2,paras) in enumerate(page["sections"]):
        parts.append(f'<h2>{e(h2)}</h2>')
        parts.append("".join(f"<p>{e(p)}</p>" for p in paras))
        if kind=="about" and i==len(page["sections"])-1:
            parts.append(f'<p><a href="{href(f"/{l}/advertising/")}">{e(u["ads"])}</a> · <a href="{href(f"/{l}/editorial-policy/")}">{e(u["policy"])}</a> · <a href="{href(f"/{l}/privacy/")}">{e(u["privacy"])}</a></p>')
        if kind=="policy" and i==len(page["sections"])-2:
            parts.append(f'<p><a href="{href(f"/{l}/affiliate-disclosure/")}">{e(u["disclosure"])}</a></p>')
        if kind=="policy" and i==len(page["sections"])-1:
            parts.append(f'<p><a class="mail" href="mailto:{AD_EMAIL}">{AD_EMAIL}</a> · <a href="{href(f"/{l}/advertising/")}">{e(u["ads"])}</a></p>')
        if kind=="affiliate" and i==len(page["sections"])-1:
            parts.append(f'<p><a href="{href(f"/{l}/editorial-policy/")}">{e(u["policy"])}</a> · <a href="{href(f"/{l}/advertising/")}">{e(u["ads"])}</a></p>')
        if kind=="privacy" and i==len(page["sections"])-1:
            parts.append(f'<p><a href="{href(f"/{l}/cookies/")}">{e(u["cookies"])}</a></p>')
        if kind=="cookies" and i==len(page["sections"])-1:
            parts.append(f'<p><a href="{href(f"/{l}/privacy/")}">{e(u["privacy"])}</a> · <a href="https://policies.google.com/technologies/cookies">Google</a> · <a href="https://www.dataprotection.gov.cy/">dataprotection.gov.cy</a></p>')
            parts.append(f'<p><a href="{href(f"/{l}/cookies/")}" data-cookie-settings>{e(u["cookie_settings"])}</a></p>')
    return "".join(parts)
def page_info(l, slug, page, schema_type):
    u=UI[l]; pathfn=lambda x,slug=slug:f"/{x}/{slug}/"
    path=f"/{l}/{slug}/"
    ld=[{"@context":"https://schema.org","@type":schema_type,"name":page["t"],"url":abs_(path),"inLanguage":l,"description":page["d"],
         "publisher":{"@id":abs_("/")+"#org"},"about":{"@id":abs_("/")+"#org"}},
        breadcrumb_ld([(u["crumb_home"], f"/{l}/"), (page["t"], path)])]
    h=head(l,f'{page["t"]} | {SITE}',page["d"],[page["t"],SITE],f"/{l}/{slug}/",pathfn,"/assets/og-default.jpg",jsonld=ld)+header(l,pathfn)
    kind={"about":"about","editorial-policy":"policy","privacy":"privacy","cookies":"cookies","affiliate-disclosure":"affiliate"}[slug]
    h+=f'<main id="main" class="wrap"><article class="adpage"><h1>{e(page["t"])}</h1><div class="body">{info_body(l,page,kind)}</div></article></main>'+footer(l)
    return h
def page_about(l):
    return page_info(l,"about",ABOUT[l],"AboutPage")

AD={
 "en":dict(
  title="Advertise & Contact",
  desc="Advertise on CyNews 24, the Cyprus news site in Russian, English and Greek. Rates and a media kit are available on request.",
  pitch="CyNews 24 publishes Cyprus news in Russian, English and Greek. Readers include residents, expats, investors and people buying property. Every story is available in all three languages.",
  rates="Rates are available on request. A media kit is also available on request.",
  formats_h="Formats",
  formats=[
   ("Display banners","Leaderboard 728×90, MPU 300×250 and mobile 320×100, in the header or the sidebar."),
   ("Sponsored articles","A story published with a clear “Sponsored” label."),
   ("Category sponsorship","Your brand alongside a section, for example Real Estate."),
   ("Native placements","A labelled item in the news feed."),
   ("Social media posts","A post on CyNews 24’s Facebook, Instagram or Telegram."),
   ("Newsletter and Telegram","A mention in the newsletter or the Telegram channel."),
   ("Three languages","One campaign prepared for Russian, English and Greek.")],
  standards="Sponsored content is labelled in line with advertising standards and is kept separate from newsroom reporting.",
  contact_h="Contact", email_l="Email",
  name="Name", company="Company", email="Email", phone="Phone", optional="optional",
  formats_l="Formats you are interested in",
  budget_l="Your budget", budget_hint="Our rates are on request. This only tells us the scale you have in mind.",
  budgets=[("","Prefer not to say"),("discuss","To be discussed"),("smaller","A smaller campaign"),("larger","A larger campaign")],
  message="Message",
  consent="I agree that CyNews 24 may use these details only to reply to this advertising enquiry.",
  send="Send request", honey="Leave this field empty", follow="Follow us",
  thanks_t="Thank you",
  thanks="Your advertising enquiry has been sent. We will reply to the email address you provided.",
  back="Back to advertising"),
 "ru":dict(
  title="Реклама и контакты",
  desc="Реклама на CyNews 24 — новости Кипра на русском, английском и греческом. Стоимость и медиакит предоставляются по запросу.",
  pitch="CyNews 24 публикует новости Кипра на русском, английском и греческом языках. Среди читателей — жители острова, экспаты, инвесторы и покупатели недвижимости. Каждый материал доступен на всех трёх языках.",
  rates="Стоимость — по запросу. Медиакит тоже отправим по запросу.",
  formats_h="Форматы",
  formats=[
   ("Баннеры","Лидерборд 728×90, MPU 300×250 и мобильный баннер 320×100 — в шапке или в боковой колонке."),
   ("Спонсорские статьи","Материал публикуется с явной пометкой «Реклама»."),
   ("Спонсорство раздела","Бренд рядом с рубрикой, например «Недвижимость»."),
   ("Нативные размещения","Помеченный материал в ленте новостей."),
   ("Посты в соцсетях","Публикация на страницах CyNews 24 в Facebook, Instagram или Telegram."),
   ("Рассылка и Telegram","Упоминание в рассылке или в Telegram-канале."),
   ("Три языка","Одна кампания сразу на русском, английском и греческом.")],
  standards="Рекламные материалы помечаются по стандартам рекламы и отделены от редакционных новостей.",
  contact_h="Контакты", email_l="Эл. почта",
  name="Имя", company="Компания", email="Эл. почта", phone="Телефон", optional="необязательно",
  formats_l="Интересующие форматы",
  budget_l="Ваш бюджет", budget_hint="Наши расценки — по запросу. Здесь только масштаб, который вы имеете в виду.",
  budgets=[("","Не указывать"),("discuss","Обсудим"),("smaller","Небольшая кампания"),("larger","Крупная кампания")],
  message="Сообщение",
  consent="Я согласен, что CyNews 24 использует эти данные только чтобы ответить на запрос о рекламе.",
  send="Отправить запрос", honey="Оставьте это поле пустым", follow="Мы в соцсетях",
  thanks_t="Спасибо",
  thanks="Запрос о рекламе отправлен. Мы ответим на указанный адрес электронной почты.",
  back="К странице рекламы"),
 "el":dict(
  title="Διαφήμιση & Επικοινωνία",
  desc="Διαφήμιση στο CyNews 24, ειδήσεις Κύπρου στα ρωσικά, αγγλικά και ελληνικά. Τιμές και media kit κατόπιν αιτήματος.",
  pitch="Το CyNews 24 δημοσιεύει ειδήσεις Κύπρου στα ρωσικά, αγγλικά και ελληνικά. Το κοινό περιλαμβάνει κατοίκους, expats, επενδυτές και αγοραστές ακινήτων. Κάθε θέμα υπάρχει και στις τρεις γλώσσες.",
  rates="Οι τιμές δίνονται κατόπιν αιτήματος. Το media kit αποστέλλεται επίσης κατόπιν αιτήματος.",
  formats_h="Μορφές",
  formats=[
   ("Banners","Leaderboard 728×90, MPU 300×250 και mobile 320×100, στην κεφαλίδα ή στην πλαϊνή στήλη."),
   ("Χορηγούμενα άρθρα","Άρθρο που δημοσιεύεται με σαφή ένδειξη «Χορηγούμενο»."),
   ("Χορηγία ενότητας","Η επωνυμία δίπλα σε μια ενότητα, για παράδειγμα Ακίνητα."),
   ("Native τοποθετήσεις","Επισημασμένο στοιχείο στη ροή ειδήσεων."),
   ("Αναρτήσεις στα social","Ανάρτηση στο Facebook, το Instagram ή το Telegram του CyNews 24."),
   ("Newsletter και Telegram","Αναφορά στο newsletter ή στο κανάλι Telegram."),
   ("Τρεις γλώσσες","Μία καμπάνια στα ρωσικά, αγγλικά και ελληνικά.")],
  standards="Το χορηγούμενο περιεχόμενο επισημαίνεται σύμφωνα με τα πρότυπα διαφήμισης και διαχωρίζεται από το ρεπορτάζ της σύνταξης.",
  contact_h="Επικοινωνία", email_l="Email",
  name="Όνομα", company="Εταιρεία", email="Email", phone="Τηλέφωνο", optional="προαιρετικό",
  formats_l="Μορφές που σας ενδιαφέρουν",
  budget_l="Ο προϋπολογισμός σας", budget_hint="Οι τιμές μας δίνονται κατόπιν αιτήματος. Εδώ δηλώνετε μόνο την κλίμακα που έχετε κατά νου.",
  budgets=[("","Χωρίς ένδειξη"),("discuss","Προς συζήτηση"),("smaller","Μικρότερη καμπάνια"),("larger","Μεγαλύτερη καμπάνια")],
  message="Μήνυμα",
  consent="Συμφωνώ ότι το CyNews 24 θα χρησιμοποιήσει αυτά τα στοιχεία μόνο για να απαντήσει σε αυτό το αίτημα διαφήμισης.",
  send="Αποστολή αιτήματος", honey="Αφήστε κενό αυτό το πεδίο", follow="Ακολουθήστε μας",
  thanks_t="Ευχαριστούμε",
  thanks="Το αίτημα διαφήμισης στάλθηκε. Θα απαντήσουμε στη διεύθυνση email που δώσατε.",
  back="Πίσω στη διαφήμιση"),
}
def _icons():
    return {
     "facebook":'<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M14 8h3V4h-3c-2.8 0-5 2.2-5 5v2H7v4h2v7h4v-7h3l1-4h-4V9c0-.6.4-1 1-1z"/></svg>',
     "instagram":'<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M8 3h8a5 5 0 0 1 5 5v8a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5V8a5 5 0 0 1 5-5zm8 2H8a3 3 0 0 0-3 3v8a3 3 0 0 0 3 3h8a3 3 0 0 0 3-3V8a3 3 0 0 0-3-3zm-4 3.2A3.8 3.8 0 1 1 8.2 12 3.8 3.8 0 0 1 12 8.2zm0 2A1.8 1.8 0 1 0 13.8 12 1.8 1.8 0 0 0 12 10.2zM17.4 6.6a1 1 0 1 1-1 1 1 1 0 0 1 1-1z"/></svg>',
     "threads":'<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M18.263 11.097c-.03-3.486-1.92-5.586-5.111-5.586-2.13 0-3.922.963-4.863 2.499l2.062 1.438c.535-.843 1.272-1.543 2.628-1.543 1.528 0 2.318.85 2.544 2.431a15 15 0 0 0-2.236-.173c-4.125 0-6.068 1.867-6.068 4.336s1.943 3.99 4.804 3.99c3.139 0 5.013-2.115 5.781-4.735.798.361 1.348 1.204 1.348 2.47 0 3.387-3.907 5.232-7.22 5.232-4.885 0-8.077-3.207-8.077-8.424 0-6.392 4.223-10.487 9.9-10.487 3.808 0 5.69 1.671 6.97 3.914l2.108-1.475C21.44 2.078 18.331 0 13.663 0 6.227 0 1.168 5.277 1.168 12.934c0 7 4.953 11.066 10.856 11.066 4.878 0 9.809-2.846 9.809-7.716 0-2.545-1.46-4.231-3.569-5.187m-6.33 4.855c-1.077 0-2.026-.512-2.026-1.453 0-1.483 1.822-1.934 3.606-1.934.678 0 1.34.045 1.927.173-.422 1.927-1.671 3.215-3.508 3.214Z"/></svg>',
     "telegram":'<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>',
    }
def social_block(l):
    a=AD[l]; block=footer_social(l)
    if not block: return ""
    return f'<h2>{e(a["follow"])}</h2>{block}'
def contact_point(l):
    return {"@type":"ContactPoint","contactType":"advertising","email":AD_EMAIL,"availableLanguage":["Russian","English","Greek"],"url":abs_(f"/{l}/advertising/")}
def ad_form(l):
    a=AD[l]
    checks="".join(f'<label><input type="checkbox" name="formats" value="{e(name)}"> <span>{e(name)}</span></label>' for name,_desc in a["formats"])
    opts="".join(f'<option value="{e(v)}">{e(lab)}</option>' for v,lab in a["budgets"])
    return f'''<form class="adform" action="{e(LEADS_FORM_ACTION)}" method="POST">
<input type="hidden" name="_subject" value="CyNews 24 advertising request">
<input type="hidden" name="_template" value="table">
<input type="hidden" name="_captcha" value="true">
<input type="hidden" name="_next" value="{e(abs_(f"/{l}/advertising/thanks/"))}">
<p class="hp" aria-hidden="true"><label>{e(a["honey"])}<input type="text" name="_honey" tabindex="-1" autocomplete="off"></label></p>
<label class="fld"><span>{e(a["name"])}</span><input type="text" name="name" required autocomplete="name"></label>
<label class="fld"><span>{e(a["company"])}</span><input type="text" name="company" required autocomplete="organization"></label>
<label class="fld"><span>{e(a["email"])}</span><input type="email" name="email" required autocomplete="email"></label>
<label class="fld"><span>{e(a["phone"])} <span class="hint">({e(a["optional"])})</span></span><input type="tel" name="phone" autocomplete="tel"></label>
<fieldset class="checks"><legend>{e(a["formats_l"])}</legend>{checks}</fieldset>
<label class="fld"><span>{e(a["budget_l"])} <span class="hint">({e(a["optional"])})</span></span><select name="budget">{opts}</select><span class="hint">{e(a["budget_hint"])}</span></label>
<label class="fld"><span>{e(a["message"])}</span><textarea name="message" required></textarea></label>
<label class="consent"><input type="checkbox" name="consent" value="yes" required> <span>{e(a["consent"])}</span></label>
<button class="send" type="submit">{e(a["send"])}</button>
</form>'''
def page_advertising(l):
    a=AD[l]; pathfn=lambda x:f"/{x}/advertising/"
    ld=[{"@context":"https://schema.org","@type":"ContactPage","name":a["title"],"url":abs_(f"/{l}/advertising/"),"inLanguage":l,"description":a["desc"],
         "mainEntity":{"@type":"Organization","@id":abs_("/")+"#org","name":SITE,"url":abs_("/"),"email":AD_EMAIL,"sameAs":same_as(),"contactPoint":contact_point(l)}},
        breadcrumb_ld([(UI[l]["crumb_home"], f"/{l}/"), (a["title"], f"/{l}/advertising/")])]
    cards="".join(f'<article class="fmt"><h3>{e(n)}</h3><p>{e(d)}</p></article>' for n,d in a["formats"])
    h=head(l,f'{a["title"]} | {SITE}',a["desc"],[a["title"],SITE,"Cyprus"],f"/{l}/advertising/",pathfn,"/assets/og-default.jpg",jsonld=ld)
    h+=header(l,pathfn,"advertising")
    h+=f'<main id="main" class="wrap"><article class="adpage"><h1>{e(a["title"])}</h1><p class="leadin">{e(a["pitch"])}</p><p class="adnote">{e(a["rates"])}</p>'
    h+=f'<h2>{e(a["formats_h"])}</h2><div class="fmts">{cards}</div><p class="adnote">{e(a["standards"])}</p>'
    h+=f'<h2>{e(a["contact_h"])}</h2><p>{e(a["email_l"])}: <a class="mail" href="mailto:{AD_EMAIL}">{AD_EMAIL}</a></p>'
    h+=ad_form(l)+social_block(l)+'</article></main>'+footer(l)
    return h
CONSULT={
 "en":dict(menu="Property advice",
  title="Buying, renting or selling property in Cyprus? Get a free consultation",
  desc="A free consultation on buying, long-term rent, selling, investment or tax on a sale in Cyprus. Limassol, Paphos, Larnaca, Nicosia, Famagusta or another area.",
  lead="Tell us what you are considering. We reply to the details you send. This is not a valuation and not tax advice.",
  name="Name", email="Email", phone="Phone / WhatsApp",
  interest="I am interested in", interests=[("buy","Buy"),("rent","Rent long-term"),("sell","Sell"),("investment","Investment"),("tax","Tax on sale")],
  area="Area", areas=[("limassol","Limassol"),("paphos","Paphos"),("larnaca","Larnaca"),("nicosia","Nicosia"),("famagusta","Famagusta"),("other","Other")],
  budget="Budget", budget_hint="optional", message="Message", message_hint="optional",
  choose="Choose",
  consent="I agree that CyNews 24 may use these details only to reply to this enquiry.",
  privacy="Privacy policy", send="Request a consultation",
  thanks_t="Thank you", thanks="Your consultation request has been sent. We will reply to the email address you provided.",
  back="Back to the consultation form"),
 "ru":dict(menu="Консультация по жилью",
  title="Покупаете, снимаете или продаёте жильё на Кипре? Бесплатная консультация",
  desc="Бесплатная консультация по покупке, долгой аренде, продаже, инвестиции или налогу с продажи на Кипре. Лимассол, Пафос, Ларнака, Никосия, Фамагуста или другой район.",
  lead="Напишите, что вы рассматриваете. Мы ответим на то, что вы отправите. Это не оценка и не налоговая консультация.",
  name="Имя", email="Эл. почта", phone="Телефон / WhatsApp",
  interest="Меня интересует", interests=[("buy","Покупка"),("rent","Долгая аренда"),("sell","Продажа"),("investment","Инвестиция"),("tax","Налог с продажи")],
  area="Район", areas=[("limassol","Лимассол"),("paphos","Пафос"),("larnaca","Ларнака"),("nicosia","Никосия"),("famagusta","Фамагуста"),("other","Другой")],
  budget="Бюджет", budget_hint="необязательно", message="Сообщение", message_hint="необязательно",
  choose="Выберите",
  consent="Я согласен, что CyNews 24 использует эти данные только чтобы ответить на это обращение.",
  privacy="Политика конфиденциальности", send="Запросить консультацию",
  thanks_t="Спасибо", thanks="Запрос на консультацию отправлен. Мы ответим на указанный адрес электронной почты.",
  back="К форме консультации"),
 "el":dict(menu="Συμβουλή για ακίνητο",
  title="Αγοράζετε, ενοικιάζετε ή πουλάτε ακίνητο στην Κύπρο; Δωρεάν συμβουλευτική",
  desc="Δωρεάν συμβουλευτική για αγορά, μακροχρόνια ενοικίαση, πώληση, επένδυση ή φόρο πώλησης στην Κύπρο. Λεμεσός, Πάφος, Λάρνακα, Λευκωσία, Αμμόχωστος ή άλλη περιοχή.",
  lead="Πείτε μας τι εξετάζετε. Απαντάμε σε όσα στέλνετε. Δεν είναι εκτίμηση και δεν είναι φορολογική συμβουλή.",
  name="Όνομα", email="Email", phone="Τηλέφωνο / WhatsApp",
  interest="Με ενδιαφέρει", interests=[("buy","Αγορά"),("rent","Μακροχρόνια ενοικίαση"),("sell","Πώληση"),("investment","Επένδυση"),("tax","Φόρος πώλησης")],
  area="Περιοχή", areas=[("limassol","Λεμεσός"),("paphos","Πάφος"),("larnaca","Λάρνακα"),("nicosia","Λευκωσία"),("famagusta","Αμμόχωστος"),("other","Άλλη")],
  budget="Προϋπολογισμός", budget_hint="προαιρετικό", message="Μήνυμα", message_hint="προαιρετικό",
  choose="Επιλέξτε",
  consent="Συμφωνώ ότι το CyNews 24 θα χρησιμοποιήσει αυτά τα στοιχεία μόνο για να απαντήσει σε αυτό το αίτημα.",
  privacy="Πολιτική απορρήτου", send="Ζητήστε συμβουλευτική",
  thanks_t="Ευχαριστούμε", thanks="Το αίτημα συμβουλευτικής στάλθηκε. Θα απαντήσουμε στη διεύθυνση email που δώσατε.",
  back="Πίσω στη φόρμα"),
}
ADVERTISE={
 "en":dict(menu="Advertise",
  title="Advertise with us",
  desc="Advertise on CyNews 24 to Cyprus residents and expats, in English, Russian and Greek, and on Telegram, Facebook and Instagram. Contact us for current stats. Packages have no listed prices.",
  lead="CyNews 24 is read by Cyprus residents and expats. Every story is in English, Russian and Greek. The same news goes to Telegram @cynews24 and @cynews24en, the CyNews 24 Facebook page, and Instagram @cynews24. Contact us for current stats.",
  packages_h="Packages",
  packages=[
   ("Sponsored article","A labelled story on the site, kept separate from news."),
   ("Banner","A display placement on the site."),
   ("Telegram post","A post on @cynews24, @cynews24en, or both."),
   ("Social bundle","A sponsored article plus Telegram and a post on the channels you choose.")],
  note="Prices are not listed here. Contact us and we will reply with what is available.",
  name="Name", company="Company", email="Email", phone="Phone", optional="optional",
  package="Package", packages_opts=[("sponsored-article","Sponsored article"),("banner","Banner"),("telegram-post","Telegram post"),("social-bundle","Social bundle")],
  message="Message",
  consent="I agree that CyNews 24 may use these details only to reply to this advertising enquiry.",
  privacy="Privacy policy", send="Send enquiry",
  thanks_t="Thank you", thanks="Your advertising enquiry has been sent. We will reply to the email address you provided.",
  back="Back to Advertise"),
 "ru":dict(menu="Реклама",
  title="Реклама у нас",
  desc="Реклама на CyNews 24 для жителей Кипра и экспатов, на английском, русском и греческом, и в Telegram, Facebook и Instagram. Актуальные цифры — по запросу. У пакетов нет цен на странице.",
  lead="CyNews 24 читают жители Кипра и экспаты. Каждый материал выходит на английском, русском и греческом. Те же новости идут в Telegram @cynews24 и @cynews24en, на страницу CyNews 24 в Facebook и в Instagram @cynews24. Актуальные цифры аудитории — по запросу.",
  packages_h="Пакеты",
  packages=[
   ("Спонсорская статья","Помеченный материал на сайте, отдельно от новостей."),
   ("Баннер","Показ на сайте."),
   ("Пост в Telegram","Публикация в @cynews24, @cynews24en или в обоих."),
   ("Соцсети вместе","Спонсорская статья плюс Telegram и пост в выбранных каналах.")],
  note="Цен на этой странице нет. Напишите, и мы ответим, что сейчас доступно.",
  name="Имя", company="Компания", email="Эл. почта", phone="Телефон", optional="необязательно",
  package="Пакет", packages_opts=[("sponsored-article","Спонсорская статья"),("banner","Баннер"),("telegram-post","Пост в Telegram"),("social-bundle","Соцсети вместе")],
  message="Сообщение",
  consent="Я согласен, что CyNews 24 использует эти данные только чтобы ответить на запрос о рекламе.",
  privacy="Политика конфиденциальности", send="Отправить запрос",
  thanks_t="Спасибо", thanks="Запрос о рекламе отправлен. Мы ответим на указанный адрес электронной почты.",
  back="К странице «Реклама»"),
 "el":dict(menu="Διαφήμιση",
  title="Διαφημιστείτε σε εμάς",
  desc="Διαφήμιση στο CyNews 24 για κατοίκους Κύπρου και expats, στα αγγλικά, ρωσικά και ελληνικά, και σε Telegram, Facebook και Instagram. Τρέχοντα στατιστικά κατόπιν επικοινωνίας. Τα πακέτα δεν έχουν τιμές.",
  lead="Το CyNews 24 το διαβάζουν κάτοικοι Κύπρου και expats. Κάθε θέμα βγαίνει στα αγγλικά, ρωσικά και ελληνικά. Οι ίδιες ειδήσεις πηγαίνουν στο Telegram @cynews24 και @cynews24en, στη σελίδα του CyNews 24 στο Facebook και στο Instagram @cynews24. Για τρέχοντα στατιστικά, επικοινωνήστε μαζί μας.",
  packages_h="Πακέτα",
  packages=[
   ("Χορηγούμενο άρθρο","Επισημασμένο θέμα στον ιστότοπο, χωριστά από τις ειδήσεις."),
   ("Banner","Προβολή στον ιστότοπο."),
   ("Ανάρτηση στο Telegram","Ανάρτηση στο @cynews24, στο @cynews24en ή και στα δύο."),
   ("Πακέτο social","Χορηγούμενο άρθρο συν Telegram και ανάρτηση στα κανάλια που διαλέγετε.")],
  note="Οι τιμές δεν αναγράφονται εδώ. Στείλτε μήνυμα και θα απαντήσουμε τι είναι διαθέσιμο.",
  name="Όνομα", company="Εταιρεία", email="Email", phone="Τηλέφωνο", optional="προαιρετικό",
  package="Πακέτο", packages_opts=[("sponsored-article","Χορηγούμενο άρθρο"),("banner","Banner"),("telegram-post","Ανάρτηση στο Telegram"),("social-bundle","Πακέτο social")],
  message="Μήνυμα",
  consent="Συμφωνώ ότι το CyNews 24 θα χρησιμοποιήσει αυτά τα στοιχεία μόνο για να απαντήσει σε αυτό το αίτημα διαφήμισης.",
  privacy="Πολιτική απορρήτου", send="Αποστολή αιτήματος",
  thanks_t="Ευχαριστούμε", thanks="Το αίτημα διαφήμισης στάλθηκε. Θα απαντήσουμε στη διεύθυνση email που δώσατε.",
  back="Πίσω στη Διαφήμιση"),
}
def _opts(pairs, choose):
    return f'<option value="">{e(choose)}</option>'+"".join(f'<option value="{e(v)}">{e(lab)}</option>' for v,lab in pairs)
def _consent(l, text, privacy):
    return (f'<label class="consent"><input type="checkbox" name="consent" value="yes" required> '
            f'<span>{e(text)} <a href="{href(f"/{l}/privacy/")}">{e(privacy)}</a></span></label>')
def property_consult_form(l, page_url, next_path, project=""):
    c=CONSULT[l]
    subject="cynews24 property lead" + (f": {project}" if project else "")
    send=BBF_COPY[l]["send"] if project else c["send"]
    named=f'<input type="hidden" name="project" value="{e(project)}">' if project else ""
    return f'''<form class="adform" action="{e(LEADS_FORM_ACTION)}" method="POST">
<input type="hidden" name="_subject" value="{e(subject)}">
<input type="hidden" name="_template" value="table">
<input type="hidden" name="_captcha" value="true">
<input type="hidden" name="_next" value="{e(abs_(next_path))}">
<input type="hidden" name="page" value="{e(page_url)}">
{named}
<p class="hp" aria-hidden="true"><label>Leave this field empty<input type="text" name="_honey" tabindex="-1" autocomplete="off"></label></p>
<div class="pair"><label class="fld"><span>{e(c["name"])}</span><input type="text" name="name" required autocomplete="name"></label>
<label class="fld"><span>{e(c["email"])}</span><input type="email" name="email" required autocomplete="email"></label></div>
<label class="fld"><span>{e(c["phone"])}</span><input type="tel" name="phone" autocomplete="tel"></label>
<div class="pair"><label class="fld"><span>{e(c["interest"])}</span><select name="interest" required>{_opts(c["interests"], c["choose"])}</select></label>
<label class="fld"><span>{e(c["area"])}</span><select name="area" required>{_opts(c["areas"], c["choose"])}</select></label></div>
<label class="fld"><span>{e(c["budget"])} <span class="hint">({e(c["budget_hint"])})</span></span><input type="text" name="budget" autocomplete="off"></label>
<label class="fld"><span>{e(c["message"])} <span class="hint">({e(c["message_hint"])})</span></span><textarea name="message"></textarea></label>
{_consent(l, c["consent"], c["privacy"])}
<button class="send" type="submit">{e(send)}</button>
</form>'''
def property_consult(l, page_url, project=""):
    c=CONSULT[l]
    if project:
        lead=e(BBF_COPY[l]["advice"])
    else:
        lead=f'{e(c["lead"])} <a href="{href(f"/{l}/property-consultation/")}">{e(c["menu"])}</a>'
    return (f'<section class="consult" id="consult" aria-label="{e(c["title"])}"><h2>{e(c["title"])}</h2>'
            f'<p class="leadin">{lead}</p>'
            f'{property_consult_form(l, page_url, f"/{l}/property-consultation/thanks/", project)}</section>')
def page_property_consultation(l):
    c=CONSULT[l]; path=f"/{l}/property-consultation/"; pathfn=lambda x:f"/{x}/property-consultation/"
    ld=[{"@context":"https://schema.org","@type":"WebPage","name":c["title"],"url":abs_(path),"inLanguage":l,"description":c["desc"],
         "isPartOf":{"@type":"WebSite","name":SITE,"url":abs_(f"/{l}/")}},
        breadcrumb_ld([(UI[l]["crumb_home"], f"/{l}/"), (c["menu"], path)])]
    h=head(l, f'{c["title"]} | {SITE}', c["desc"], [c["title"], SITE, "Cyprus"], path, pathfn, "/assets/og-default.jpg", jsonld=ld)
    h+=header(l, pathfn)
    h+=f'<main id="main" class="wrap"><article class="adpage"><h1>{e(c["title"])}</h1><p class="leadin">{e(c["lead"])}</p>'
    h+=property_consult_form(l, abs_(path), f"/{l}/property-consultation/thanks/")
    h+='</article></main>'+footer(l)
    return h
def page_property_consult_thanks(l):
    c=CONSULT[l]; pathfn=lambda x:f"/{x}/property-consultation/thanks/"
    h=head(l, f'{c["thanks_t"]} | {SITE}', c["thanks"], [SITE], f"/{l}/property-consultation/thanks/", pathfn, "/assets/og-default.jpg", robots="noindex,follow")
    h+=header(l, pathfn)
    h+=f'<main id="main" class="wrap"><article class="adpage"><h1>{e(c["thanks_t"])}</h1><p class="leadin">{e(c["thanks"])}</p><p><a href="{href(f"/{l}/property-consultation/")}">{e(c["back"])}</a></p></article></main>'+footer(l)
    return h
def advertise_form(l):
    a=ADVERTISE[l]
    return f'''<form class="adform" action="{e(LEADS_FORM_ACTION)}" method="POST">
<input type="hidden" name="_subject" value="cynews24 advertising enquiry">
<input type="hidden" name="_template" value="table">
<input type="hidden" name="_captcha" value="true">
<input type="hidden" name="_next" value="{e(abs_(f"/{l}/advertise/thanks/"))}">
<input type="hidden" name="page" value="{e(abs_(f"/{l}/advertise/"))}">
<p class="hp" aria-hidden="true"><label>Leave this field empty<input type="text" name="_honey" tabindex="-1" autocomplete="off"></label></p>
<div class="pair"><label class="fld"><span>{e(a["name"])}</span><input type="text" name="name" required autocomplete="name"></label>
<label class="fld"><span>{e(a["email"])}</span><input type="email" name="email" required autocomplete="email"></label></div>
<label class="fld"><span>{e(a["company"])} <span class="hint">({e(a["optional"])})</span></span><input type="text" name="company" autocomplete="organization"></label>
<label class="fld"><span>{e(a["phone"])} <span class="hint">({e(a["optional"])})</span></span><input type="tel" name="phone" autocomplete="tel"></label>
<label class="fld"><span>{e(a["package"])}</span><select name="package">{_opts(a["packages_opts"], CONSULT[l]["choose"])}</select></label>
<label class="fld"><span>{e(a["message"])}</span><textarea name="message" required></textarea></label>
{_consent(l, a["consent"], a["privacy"])}
<button class="send" type="submit">{e(a["send"])}</button>
</form>'''
def page_advertise(l):
    a=ADVERTISE[l]; path=f"/{l}/advertise/"; pathfn=lambda x:f"/{x}/advertise/"
    cards="".join(f'<article class="fmt"><h3>{e(n)}</h3><p>{e(d)}</p></article>' for n,d in a["packages"])
    ld=[{"@context":"https://schema.org","@type":"WebPage","name":a["title"],"url":abs_(path),"inLanguage":l,"description":a["desc"],
         "isPartOf":{"@type":"WebSite","name":SITE,"url":abs_(f"/{l}/")}},
        breadcrumb_ld([(UI[l]["crumb_home"], f"/{l}/"), (a["menu"], path)])]
    h=head(l, f'{a["title"]} | {SITE}', a["desc"], [a["title"], SITE, "Cyprus"], path, pathfn, "/assets/og-default.jpg", jsonld=ld)
    h+=header(l, pathfn, "advertise")
    h+=f'<main id="main" class="wrap"><article class="adpage"><h1>{e(a["title"])}</h1><p class="leadin">{e(a["lead"])}</p>'
    h+=f'<p><a href="{e(TELEGRAM["ru"])}" target="_blank" rel="noopener">@cynews24</a> · <a href="{e(TELEGRAM["en"])}" target="_blank" rel="noopener">@cynews24en</a> · <a href="https://www.instagram.com/cynews24/" target="_blank" rel="noopener">Instagram @cynews24</a> · {threads_link()}</p>'
    h+=f'<h2>{e(a["packages_h"])}</h2><div class="fmts">{cards}</div><p class="adnote">{e(a["note"])}</p>'
    h+=f'<div class="consult">{advertise_form(l)}</div></article></main>'+footer(l)
    return h
def page_advertise_thanks(l):
    a=ADVERTISE[l]; pathfn=lambda x:f"/{x}/advertise/thanks/"
    h=head(l, f'{a["thanks_t"]} | {SITE}', a["thanks"], [SITE], f"/{l}/advertise/thanks/", pathfn, "/assets/og-default.jpg", robots="noindex,follow")
    h+=header(l, pathfn, "advertise")
    h+=f'<main id="main" class="wrap"><article class="adpage"><h1>{e(a["thanks_t"])}</h1><p class="leadin">{e(a["thanks"])}</p><p><a href="{href(f"/{l}/advertise/")}">{e(a["back"])}</a></p></article></main>'+footer(l)
    return h
def page_ad_thanks(l):
    a=AD[l]; pathfn=lambda x:f"/{x}/advertising/thanks/"
    h=head(l,f'{a["thanks_t"]} | {SITE}',a["thanks"],[SITE],f"/{l}/advertising/thanks/",pathfn,"/assets/og-default.jpg",robots="noindex,follow")
    h+=header(l,pathfn,"advertising")
    h+=f'<main id="main" class="wrap"><article class="adpage"><h1>{e(a["thanks_t"])}</h1><p class="leadin">{e(a["thanks"])}</p><p><a class="mail" href="{href(f"/{l}/advertising/")}">{e(a["back"])}</a></p></article></main>'+footer(l)
    return h

EVL={
 "en":dict(title="Events in Cyprus",week="This week",upcoming="Coming months",later="Later",see="All events",
  desc="Concerts, festivals, fairs, exhibitions, theatre, family shows and sport in Cyprus. Dates and prices come from the linked sources and are left out where a source does not give them.",
  city="City",kind="Type",all="All",source="Source",empty="No events match these filters.",
  cities=dict(nicosia="Nicosia",limassol="Limassol",larnaca="Larnaca",paphos="Paphos",**{"ayia-napa":"Ayia Napa & Protaras"},other="Towns & villages"),
  types=dict(theatre="Theatre",cinema="Cinema",concert="Concerts",festival="Festivals",fair="Fairs & markets",exhibition="Exhibitions",kids="For children",sport="Sport")),
 "ru":dict(title="Мероприятия на Кипре",week="На этой неделе",upcoming="В ближайшие месяцы",later="Позже",see="Все события",
  desc="Концерты, фестивали, ярмарки, выставки, театр, семейные спектакли и спорт на Кипре. Даты и цены взяты из указанных источников и не дополняются, если источник их не называет.",
  city="Город",kind="Тип",all="Все",source="Источник",empty="Нет событий с таким фильтром.",
  cities=dict(nicosia="Никосия",limassol="Лимассол",larnaca="Ларнака",paphos="Пафос",**{"ayia-napa":"Айя-Напа и Протарас"},other="Города и деревни"),
  types=dict(theatre="Театр",cinema="Кино",concert="Концерты",festival="Фестивали",fair="Ярмарки",exhibition="Выставки",kids="Для детей",sport="Спорт")),
 "el":dict(title="Εκδηλώσεις στην Κύπρο",week="Αυτή την εβδομάδα",upcoming="Τους επόμενους μήνες",later="Αργότερα",see="Όλες οι εκδηλώσεις",
  desc="Συναυλίες, φεστιβάλ, αγορές, εκθέσεις, θέατρο, οικογενειακές παραστάσεις και αθλητισμός στην Κύπρο. Ημερομηνίες και τιμές προέρχονται από τις πηγές και δεν συμπληρώνονται όταν η πηγή δεν τις δίνει.",
  city="Πόλη",kind="Είδος",all="Όλα",source="Πηγή",empty="Καμία εκδήλωση με αυτά τα φίλτρα.",
  cities=dict(nicosia="Λευκωσία",limassol="Λεμεσός",larnaca="Λάρνακα",paphos="Πάφος",**{"ayia-napa":"Αγία Νάπα & Πρωταράς"},other="Πόλεις και χωριά"),
  types=dict(theatre="Θέατρο",cinema="Κινηματογράφος",concert="Συναυλίες",festival="Φεστιβάλ",fair="Αγορές",exhibition="Εκθέσεις",kids="Για παιδιά",sport="Αθλητισμός")),
}
def event_buckets():
    today=datetime.date.fromisoformat(TODAY)
    week_end=today+datetime.timedelta(days=6)
    later_from=datetime.date(2027,3,1)
    buckets={"week":[],"upcoming":[],"later":[]}
    for ev in EV_EVENTS:
        start=datetime.date.fromisoformat(ev["start"][:10])
        end=datetime.date.fromisoformat((ev.get("end") or ev["start"])[:10])
        if end<today: continue
        if start<=week_end: buckets["week"].append(ev)
        elif start<later_from: buckets["upcoming"].append(ev)
        else: buckets["later"].append(ev)
    for rows in buckets.values():
        rows.sort(key=lambda ev: ev["start"])
    return buckets
def ev_icon(kind):
    paths={
     "concert":'<path d="M22 46V16l16-4v28" fill="none" stroke="#fff" stroke-width="2"/><circle cx="18" cy="46" r="5" fill="#c4571a"/><circle cx="34" cy="40" r="5" fill="#c4571a"/>',
     "festival":'<path d="M16 46V18h6l10 8 10-8h6v28" fill="none" stroke="#fff" stroke-width="2"/><path d="M22 18v28" stroke="#c4571a" stroke-width="2"/>',
     "fair":'<path d="M12 28h40v16H12z" fill="none" stroke="#fff" stroke-width="2"/><path d="M16 28l6-10h20l6 10" fill="none" stroke="#c4571a" stroke-width="2"/>',
     "exhibition":'<path d="M18 14h20a4 4 0 0 1 4 4v32H18z" fill="none" stroke="#fff" stroke-width="2"/><path d="M18 18H14v32h4" stroke="#c4571a" stroke-width="2"/>',
     "theatre":'<path d="M16 20c6 8 26 8 32 0v22c-6-6-26-6-32 0z" fill="none" stroke="#fff" stroke-width="2"/><path d="M32 20v22" stroke="#c4571a" stroke-width="2"/>',
     "sport":'<circle cx="32" cy="32" r="14" fill="none" stroke="#fff" stroke-width="2"/><path d="M32 18v28M18 32h28" stroke="#c4571a" stroke-width="2"/>',
     "kids":'<circle cx="32" cy="24" r="8" fill="none" stroke="#fff" stroke-width="2"/><path d="M18 48c2-8 8-12 14-12s12 4 14 12" fill="none" stroke="#c4571a" stroke-width="2"/>',
     "cinema":'<rect x="12" y="18" width="40" height="28" rx="2" fill="none" stroke="#fff" stroke-width="2"/><path d="M12 26h40M22 18l-4 8M32 18l-4 8M42 18l-4 8" stroke="#c4571a" stroke-width="2"/>',
    }
    return f'<svg viewBox="0 0 64 64" width="64" height="64" aria-hidden="true">{paths.get(kind, paths["festival"])}</svg>'
def ev_caption(photo,l):
    label={"en":"Photo","ru":"Фото","el":"Φωτογραφία"}[l]
    return (f'{label}: {e(photo["author"])} / <a href="{e(photo["page"])}">{e(photo["source"])}</a>, '
            f'<a href="{e(photo["license_url"])}">{e(photo["license"])}</a>')
def event_ld(ev,l):
    addr={"@type":"PostalAddress","addressLocality":ev["locality"],"addressCountry":"CY"}
    if ev.get("street"): addr["streetAddress"]=ev["street"]
    kind="ScreeningEvent" if ev.get("type")=="cinema" else "Event"
    organizer={"@type":"Organization","name":ev["source"],"url":ev["url"]}
    obj={"@type":kind,"name":ev["title"][l],"startDate":ev["start"],"eventStatus":"https://schema.org/EventScheduled",
         "eventAttendanceMode":"https://schema.org/OfflineEventAttendanceMode",
         "location":{"@type":"Place","name":ev["venue"][l],"address":addr},
         "url":ev["url"],"description":ev["desc"][l],
         "organizer":organizer,"performer":organizer}
    if ev.get("end"): obj["endDate"]=ev["end"]
    # Include free events (low "0"); omit offers entirely when the price is unknown.
    if ev.get("low") is not None and str(ev.get("low")) != "":
        obj["offers"]={"@type":"AggregateOffer","lowPrice":ev["low"],"highPrice":ev.get("high", ev["low"]),
                       "priceCurrency":"EUR","url":ev["url"],
                       "availability":"https://schema.org/InStock"}
        # offers.validFrom is omitted: ticket on-sale dates are not in the source data.
    # Own photograph only. A category fallback is a listing illustration and
    # must not be published as this event's image.
    if ev.get("photo"):
        obj["image"]=[abs_(f"/assets/img/events/{ev['photo']}-1200.webp"),
                      abs_(f"/assets/img/events/{ev['photo']}-600.webp")]
    return obj
def event_illustration(ev):
    """Card image: the event's own photo, or the category fallback when it has none."""
    if ev.get("photo"):
        return ev["photo"], EV_PHOTOS[ev["photo"]]
    key=EV_FALLBACK.get(ev.get("type"))
    ph=CREDITS.get(key) if key else None
    if ph and ph.get("file") and ph.get("alt"):
        return key, ph
    return None, None
def ev_card(ev,l,u):
    key,ph=event_illustration(ev)
    if ph:
        media=(f'<figure class="pic"><img src="{href(f"/assets/img/events/{key}-600.webp")}" '
               f'srcset="{href(f"/assets/img/events/{key}-600.webp")} 600w, {href(f"/assets/img/events/{key}-1200.webp")} 1200w" '
               f'sizes="(max-width:600px) 100vw, 240px" width="600" height="338" alt="{e(ph["alt"][l])}" loading="lazy">'
               f'<figcaption>{ev_caption(ph,l)}</figcaption></figure>')
    else:
        media=f'<div class="ico" aria-hidden="true">{ev_icon(ev["type"])}</div>'
    price=f' · {e(ev["price"][l])}' if ev.get("price") else ""
    return (f'<article class="ev" id="ev-{ev["id"]}" data-ev data-city="{ev["city"]}" data-type="{ev["type"]}">'
            f'{media}<div><p class="cat">{e(u["types"][ev["type"]])}</p><h2>{e(ev["title"][l])}</h2>'
            f'<p class="when">{e(ev["when"][l])}</p>'
            f'<p class="meta">{e(ev["venue"][l])}{price}</p>'
            f'<p>{e(ev["desc"][l])}</p>'
            f'<p><a href="{e(ev["url"])}">{e(u["source"])}: {e(ev["source"])}</a></p></div></article>')
def week_home(l):
    u=EVL[l]; rows=event_buckets()["week"]
    if not rows: return ""
    items="".join(f'<li><a href="{href(f"/{l}/events/#ev-{ev["id"]}")}">{e(ev["title"][l])}</a><span class="meta">{e(ev["when"][l])}</span></li>' for ev in rows)
    return (f'<section class="weekband" aria-label="{e(u["week"])}"><h2><a href="{href(f"/{l}/events/")}">{e(u["week"])}</a></h2>'
            f'<ul>{items}</ul></section>')
TRAVEL_GUIDES = (
 "best-things-to-do-cyprus-2026",
 "renting-a-car-in-cyprus",
 "where-to-stay-in-cyprus",
 "esim-mobile-data-cyprus",
)
TRAVEL_PAGE = {
 "en": ("Travel in Cyprus: things to do, cars, stays and eSIM", "Guides to things to do, hiring a car, where to stay, and mobile data. Each page cites its sources and does not invent a price."),
 "ru": ("Путешествия по Кипру: маршруты, авто, жильё и eSIM", "Путеводители: чем заняться, аренда машины, где остановиться и мобильный интернет. На каждой странице указаны источники, цены не выдуманы."),
 "el": ("Ταξίδι στην Κύπρο: αξιοθέατα, αυτοκίνητο, διαμονή και eSIM", "Οδηγοί για αξιοθέατα, ενοικίαση αυτοκινήτου, πού να μείνετε και δεδομένα κινητού. Κάθε σελίδα αναφέρει τις πηγές της και δεν επινοεί τιμή."),
}
GUIDE_PAGE = {
 "en": ("Guides to Cyprus", "Explainers on moving to Cyprus, EU residence, tax, property, healthcare, driving and travel. Each page cites public sources, shows when it was updated, and does not invent a price or a permit."),
 "ru": ("Гиды по Кипру", "Разборы о переезде на Кипр, виде на жительство, налогах, жилье, медицине, вождении и поездках. У каждой страницы есть источники и дата обновления. Цены и разрешения здесь не выдуманы."),
 "el": ("Οδηγοί για την Κύπρο", "Επεξηγήσεις για μετακόμιση, διαμονή, φόρους, ακίνητα, υγεία, οδήγηση και ταξίδια. Κάθε σελίδα αναφέρει πηγές και ημερομηνία ενημέρωσης και δεν επινοεί τιμή ή άδεια."),
}
GUIDE_NOTE = {
 "en": "A guide is not a permit, a tax return or a quote. Where two official pages disagree, the guide says so.",
 "ru": "Гид — не разрешение, не декларация и не оферта. Если две официальные страницы расходятся, материал об этом говорит.",
 "el": "Ο οδηγός δεν είναι άδεια, δήλωση ή προσφορά. Όπου δύο επίσημες σελίδες διαφωνούν, το κείμενο το λέει.",
}
GUIDE_EL_NOTE = "Οδηγοί που δεν έχουν ακόμη ελληνικό κείμενο μένουν στα αγγλικά και στα ρωσικά."
# Slugs in reading order. A missing file is a build error, so a renamed guide cannot vanish from the hub.
GUIDE_GROUPS = (
 ("move", {"en":"Moving and residence","ru":"Переезд и проживание","el":"Μετακόμιση και διαμονή"}, (
    "relocating-to-cyprus","cyprus-pink-slip-visitor-visa","digital-nomad-visa-cyprus","cyprus-digital-nomad-visa-2026","cyprus-permanent-residency-300k","eu-residence-cyprus","best-areas-to-live-cyprus","moving-to-cyprus-with-pets","cyprus-resident-handbook","cyprus-malta-portugal-relocation")),
 ("tax", {"en":"Tax, work and companies","ru":"Налоги, работа и компании","el":"Φόροι, εργασία και εταιρείες"}, (
    "cyprus-taxes-for-individuals","cyprus-tax-residency-2026","cyprus-non-dom-tax-2026","cost-of-living-cyprus","cost-of-living-cyprus-2026","jobs-and-pay-cyprus","open-a-company-in-cyprus","cysec-forex-crypto","opening-bank-account-cyprus","bank-account-cyprus")),
 ("borders", {"en":"Borders and the region","ru":"Границы и регион","el":"Σύνορα και περιοχή"}, (
    "cyprus-schengen-2026","ees-etias-cyprus-2026","cyprus-and-the-region")),
 ("property", {"en":"Property","ru":"Жильё","el":"Ακίνητα"}, (
    "buying-property-cyprus","buying-property-cyprus-foreigner","renting-apartment-cyprus","renting-in-cyprus")),
 ("daily", {"en":"Health and the road","ru":"Здоровье и дорога","el":"Υγεία και δρόμος"}, (
    "gesy-healthcare-cyprus","gesy-for-foreigners","international-health-insurance","schools-kindergartens-cyprus","driving-license-car-cyprus","driving-in-cyprus","protect-data-foreign-banks")),
 ("travel", {"en":"Travel","ru":"Поездки","el":"Ταξίδια"}, (
    "flights-to-cyprus","cyprus-weather-by-month","beaches-in-cyprus","best-things-to-do-cyprus-2026","where-to-stay-in-cyprus","renting-a-car-in-cyprus","esim-mobile-data-cyprus","cyprus-airport-transfers-2026")),
 ("projects", {"en":"Development notes","ru":"Заметки о проектах","el":"Σημειώσεις για αναπτύξεις"}, (
    "yoo-limassol-review","limassol-blu-marine-review","one-limassol-review","dream-tower-limassol-review","eden-coast-paphos-review","kean-limassol-review","minthis-residences-review")),
)
RELOCATION_PAGE = {
 "en": ("Relocation and expat life in Cyprus", "How people move to Cyprus: residence, tax, work, healthcare, driving and housing. The pages below are guides and news already on the site, each with its sources."),
 "ru": ("Переезд на Кипр и жизнь экспатов", "Как переезжают на Кипр: вид на жительство, налоги, работа, медицина, вождение и жильё. Ниже — гиды и новости, которые уже есть на сайте, у каждого свои источники."),
 "el": ("Μετακόμιση και ζωή στην Κύπρο", "Πώς μετακομίζει κανείς στην Κύπρο: διαμονή, φόροι, εργασία, υγεία, οδήγηση και στέγη. Παρακάτω είναι οδηγοί και ειδήσεις που υπάρχουν ήδη στον ιστότοπο, ο καθένας με τις πηγές του."),
}
RELOCATION_NOTE = {
 "en": "A page here is not a residence permit or a tax opinion. Where two official sources disagree, the article says so.",
 "ru": "Страница в этом разделе — не вид на жительство и не налоговая консультация. Если два официальных источника расходятся, материал об этом говорит.",
 "el": "Μια σελίδα εδώ δεν είναι άδεια διαμονής ούτε φορολογική γνώμη. Όπου δύο επίσημες πηγές διαφωνούν, το κείμενο το λέει.",
}
RELOCATION_GROUPS = (
 ("move", {"en":"Moving and residence","ru":"Переезд и проживание","el":"Μετακόμιση και διαμονή"}, (
    "relocating-to-cyprus","cyprus-pink-slip-visitor-visa","digital-nomad-visa-cyprus","cyprus-permanent-residency-300k","best-areas-to-live-cyprus","moving-to-cyprus-with-pets","eu-residence-cyprus","cyprus-digital-nomad-visa-2026","cyprus-resident-handbook","cyprus-malta-portugal-relocation","digital-citizen-residence-documents")),
 ("tax", {"en":"Tax, work and the cost of living","ru":"Налоги, работа и стоимость жизни","el":"Φόροι, εργασία και κόστος ζωής"}, (
    "cyprus-taxes-for-individuals","cost-of-living-cyprus","opening-bank-account-cyprus","cyprus-tax-residency-2026","cyprus-non-dom-tax-2026","cost-of-living-cyprus-2026","jobs-and-pay-cyprus","open-a-company-in-cyprus","bank-account-cyprus","third-country-workers-four-year-cap")),
 ("daily", {"en":"Healthcare, driving and a home","ru":"Медицина, дорога и жильё","el":"Υγεία, οδήγηση και σπίτι"}, (
    "gesy-healthcare-cyprus","schools-kindergartens-cyprus","driving-license-car-cyprus","buying-property-cyprus","renting-apartment-cyprus","gesy-for-foreigners","international-health-insurance","driving-in-cyprus","renting-in-cyprus","buying-property-cyprus-foreigner")),
 ("borders", {"en":"Borders","ru":"Границы","el":"Σύνορα"}, (
    "cyprus-schengen-2026","cyprus-schengen-july-2027","ees-etias-cyprus-2026")),
)
EVENT_RELATED = ("nicosia-christmas-market-2026","weekend-events-14-15-november","tourist-arrivals-october")
EVENT_INTRO = {
 "en":[
  "Visitor numbers and holiday plans are in [tourism](/en/tourism/). People who live here year-round start with [relocation and expat life](/en/relocation/)."],
 "ru":[
  "Число гостей и отпускные планы — в разделе [туризма](/ru/tourism/). Тем, кто живёт здесь круглый год, ближе [переезд и жизнь экспатов](/ru/relocation/)."],
 "el":[
  "Οι αφίξεις και τα σχέδια διακοπών είναι στον [τουρισμό](/el/tourism/). Όσοι μένουν όλο τον χρόνο ξεκινούν από τη [μετακόμιση](/el/relocation/)."],
}
def page_relocation(l):
    title, desc = RELOCATION_PAGE[l]
    path=f"/{l}/relocation/"
    pathfn=lambda x:f"/{x}/relocation/"
    blocks=[]
    listed=[]
    for _key, names, slugs in RELOCATION_GROUPS:
        cards=[]
        for slug in slugs:
            s=BYSLUG.get(slug)
            if not s:
                raise SystemExit(f"relocation hub lists unknown slug {slug}")
            if l in s.get("missing", ()):
                continue
            cards.append(f'<article class="fmt"><h3><a href="{href(f"/{l}/{slug}/")}">{e(s["title"][l])}</a></h3><p>{e(trunc(s["lede"][l],180))}</p></article>')
            listed.append(s)
        if cards:
            blocks.append(f'<h2>{e(names[l])}</h2><div class="fmts">{"".join(cards)}</div>')
    links=intro_html([
        {"en":"News that affects a move also sits in the [economy](/en/economy/), [real estate](/en/real-estate/) and [tourism](/en/tourism/) sections. The full [guide index](/en/guides/) lists every explainer.",
         "ru":"Новости, от которых зависит переезд, есть и в разделах [экономики](/ru/economy/), [недвижимости](/ru/real-estate/) и [туризма](/ru/tourism/). Полный список разборов — в [гидах](/ru/guides/).",
         "el":"Ειδήσεις που αλλάζουν μια μετακόμιση βρίσκονται και στην [οικονομία](/el/economy/), στα [ακίνητα](/el/real-estate/) και στον [τουρισμό](/el/tourism/). Όλοι οι οδηγοί είναι στους [οδηγούς](/el/guides/)."}[l]])
    note=f'<p>{e(RELOCATION_NOTE[l])}</p>'
    if l=="el":
        note+=f'<p>{e(GUIDE_EL_NOTE)} <a href="{href("/en/relocation/")}">English</a></p>'
    ld=[collection_ld(l, title, path, desc, listed),
        breadcrumb_ld([(UI[l]["crumb_home"], f"/{l}/"), (RELOCATION_MENU[l], path)])]
    h=head(l, f'{title} | {SITE}', desc, [title, "Cyprus", SITE], path, pathfn, "/assets/og-default.jpg", jsonld=ld)
    h+=header(l, pathfn, "relocation")
    h+=f'<main id="main" class="wrap"><article class="adpage"><nav class="crumb" aria-label="breadcrumb"><a href="{href(f"/{l}/")}">{e(UI[l]["crumb_home"])}</a> › <span>{e(RELOCATION_MENU[l])}</span></nav><h1>{e(title)}</h1><p class="leadin">{e(desc)}</p>{note}{links}{"".join(blocks)}</article></main>'+footer(l)
    return h
def page_guides(l):
    title, desc = GUIDE_PAGE[l]
    path=f"/{l}/guides/"
    pathfn=lambda x:f"/{x}/guides/"
    blocks=[]
    listed=[]
    for _key, names, slugs in GUIDE_GROUPS:
        cards=[]
        for slug in slugs:
            s=BYSLUG.get(slug)
            if not s:
                raise SystemExit(f"guides hub lists unknown slug {slug}")
            if l in s.get("missing", ()):
                continue
            cards.append(f'<article class="fmt"><h3><a href="{href(f"/{l}/{slug}/")}">{e(s["title"][l])}</a></h3><p>{e(trunc(s["lede"][l],180))}</p></article>')
            listed.append(s)
        if cards:
            blocks.append(f'<h2>{e(names[l])}</h2><div class="fmts">{"".join(cards)}</div>')
    note=f'<p>{e(GUIDE_NOTE[l])}</p>'
    if l=="el":
        note+=f'<p>{e(GUIDE_EL_NOTE)} <a href="{href("/en/guides/")}">English</a></p>'
    elements=[{"@type":"ListItem","position":i+1,"url":abs_(f"/{l}/{s['slug']}/"),"name":s["title"][l]} for i,s in enumerate(listed)]
    ld=[{"@context":"https://schema.org","@type":"CollectionPage","name":title,"url":abs_(path),"inLanguage":l,"description":desc,
         "isPartOf":{"@type":"WebSite","name":SITE,"url":abs_(f"/{l}/")},
         "mainEntity":{"@type":"ItemList","itemListElement":elements}},
        breadcrumb_ld([(UI[l]["crumb_home"], f"/{l}/"), (GUIDE_MENU[l], path)])]
    h=head(l, f'{title} | {SITE}', desc, [title, GUIDE_MENU[l], "Cyprus", SITE], path, pathfn, "/assets/og-default.jpg", jsonld=ld)
    h+=header(l, pathfn, "guides")
    h+=f'<main id="main" class="wrap"><article class="adpage"><h1>{e(title)}</h1><p class="leadin">{e(desc)}</p>{note}{"".join(blocks)}</article></main>'+footer(l)
    return h
def page_travel(l):
    title, desc = TRAVEL_PAGE[l]
    path=f"/{l}/travel/"
    pathfn=lambda x:f"/{x}/travel/"
    cards=[]
    for slug in TRAVEL_GUIDES:
        s=BYSLUG[slug]
        cards.append(f'<article class="fmt"><h3><a href="{href(f"/{l}/{slug}/")}">{e(s["title"][l])}</a></h3><p>{e(trunc(s["lede"][l],180))}</p></article>')
    ld=[{"@context":"https://schema.org","@type":"CollectionPage","name":title,"url":abs_(path),"inLanguage":l,"description":desc,
         "isPartOf":{"@type":"WebSite","name":SITE,"url":abs_(f"/{l}/")}},
        breadcrumb_ld([(UI[l]["crumb_home"], f"/{l}/"), (TRAVEL_MENU[l], path)])]
    h=head(l, f'{title} | {SITE}', desc, [title, "Cyprus", SITE], path, pathfn, "/assets/og-default.jpg", jsonld=ld)
    h+=header(l, pathfn, "travel")
    h+=f'<main id="main" class="wrap"><article class="adpage"><h1>{e(title)}</h1><p class="leadin">{e(desc)}</p><div class="fmts">{"".join(cards)}</div>{travel_box_html(l, "default")}</article></main>'+footer(l)
    return h
def page_events(l):
    u=EVL[l]; pathfn=lambda x:f"/{x}/events/"
    buckets=event_buckets()
    rows=buckets["week"]+buckets["upcoming"]+buckets["later"]
    graph={"@context":"https://schema.org","@graph":[event_ld(ev,l) for ev in rows]}
    cities="".join(f'<button type="button" data-city-btn="{c}"{" class=on" if c=="" else ""}>{e(u["all"] if c=="" else u["cities"][c])}</button>' for c in [""]+list(u["cities"]))
    kinds="".join(f'<button type="button" data-type-btn="{t}"{" class=on" if t=="" else ""}>{e(u["all"] if t=="" else u["types"][t])}</button>' for t in [""]+list(u["types"]))
    groups=""
    for key in ("week","upcoming","later"):
        if not buckets[key]: continue
        cards="".join(ev_card(ev,l,u) for ev in buckets[key])
        groups+=f'<section class="evgroup" data-evgroup><h2 class="sec">{e(u[key])}</h2><div class="evlist">{cards}</div></section>'
    script='''<script>
(function(){
  var city="", type="";
  function apply(){
    var n=0;
    document.querySelectorAll("[data-ev]").forEach(function(el){
      var ok=(!city||el.getAttribute("data-city")===city)&&(!type||el.getAttribute("data-type")===type);
      el.hidden=!ok; if(ok) n++;
    });
    document.querySelectorAll("[data-evgroup]").forEach(function(g){
      var vis=false;
      g.querySelectorAll("[data-ev]").forEach(function(el){ if(!el.hidden) vis=true; });
      g.hidden=!vis;
    });
    var empty=document.querySelector("[data-evempty]");
    if(empty) empty.hidden=n!==0;
  }
  document.querySelectorAll("[data-city-btn]").forEach(function(b){
    b.addEventListener("click",function(){ city=b.getAttribute("data-city-btn");
      document.querySelectorAll("[data-city-btn]").forEach(function(x){x.classList.toggle("on",x===b);}); apply();});
  });
  document.querySelectorAll("[data-type-btn]").forEach(function(b){
    b.addEventListener("click",function(){ type=b.getAttribute("data-type-btn");
      document.querySelectorAll("[data-type-btn]").forEach(function(x){x.classList.toggle("on",x===b);}); apply();});
  });
})();
</script>'''
    ld=[graph,
        {"@context":"https://schema.org","@type":"CollectionPage","name":u["title"],"url":abs_(f"/{l}/events/"),"inLanguage":l,"description":u["desc"],
         "isPartOf":{"@type":"WebSite","name":SITE,"url":abs_(f"/{l}/")}},
        breadcrumb_ld([(UI[l]["crumb_home"], f"/{l}/"), (u["title"], f"/{l}/events/")])]
    h=head(l,f'{u["title"]} | {SITE}',u["desc"],[u["title"],"Cyprus",SITE],f"/{l}/events/",pathfn,"/assets/og-default.jpg",jsonld=ld)
    h+=header(l,pathfn,"events")
    h+=f'<main id="main" class="wrap"><h1 class="sec">{e(u["title"])}</h1><p class="leadin" style="max-width:760px">{e(u["desc"])}</p>'
    h+=intro_html(EVENT_INTRO[l])
    related=[BYSLUG[slug] for slug in EVENT_RELATED if slug in BYSLUG and l not in BYSLUG[slug].get("missing",())]
    if related:
        h+=f'<div class="grid g3" style="margin:8px 0 18px">'+"".join(card(s,l) for s in related)+'</div>'
    h+=f'<div class="filters"><p>{e(u["city"])}</p>{cities}<p>{e(u["kind"])}</p>{kinds}</div>'
    h+=f'<p data-evempty hidden>{e(u["empty"])}</p>{groups}</main>'
    h+=script+footer(l)
    return h
def _write_event_webp(d, key, p):
    im=Image.open(os.path.join(HERE,"photos",p["file"]))
    plain=cover_crop(im,1200,675,tuple(p.get("focus",(0.5,0.5))))
    watermark(plain).save(f"{d}/{key}-1200.webp","WEBP",quality=78,method=6)
    watermark(plain.resize((600,338),Image.LANCZOS)).save(f"{d}/{key}-600.webp","WEBP",quality=76,method=6)
def build_event_photos():
    d=OUT+"/assets/img/events"; os.makedirs(d,exist_ok=True)
    for key,p in EV_PHOTOS.items():
        _write_event_webp(d, key, p)
    for key in EV_FALLBACK.values():
        _write_event_webp(d, key, CREDITS[key])

def page_root():
    # Language chooser. It is x-default for the three homepages only, and it does not
    # redirect: a redirect made Google treat this URL and /en/ as the same page.
    alts="\n".join(f'<link rel="alternate" hreflang="{x}" href="{abs_(f"/{x}/")}">' for x in LANGS)+f'\n<link rel="alternate" hreflang="x-default" href="{abs_("/")}">'
    root_desc="CyNews 24: Cyprus news in English, Russian and Greek."
    blocks=[website_ld("en", "/", root_desc), {"@context":"https://schema.org",**org_ld("en")}]
    blocks[0]["inLanguage"]=list(LANGS)
    ld="\n".join('<script type="application/ld+json">'+json.dumps(j,ensure_ascii=False).replace("</","<\\/")+'</script>' for j in blocks)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{PATH_CANON_JS}
{YANDEX_VERIFICATION}
{IMPACT_VERIFICATION}
{bing_meta()}
<title>CyNews 24 – Cyprus News · Новости Кипра · Ειδήσεις Κύπρου</title>
<meta name="description" content="CyNews 24: Cyprus news in English, Russian and Greek. Новости Кипра на русском, английском и греческом. Ειδήσεις Κύπρου στα ελληνικά, αγγλικά και ρωσικά.">
<meta name="keywords" content="Cyprus news, Кипр новости, Κύπρος ειδήσεις, CyNews 24">
<meta name="robots" content="index,follow,max-image-preview:large"><link rel="canonical" href="{abs_("/")}">
{alts}
<meta property="og:site_name" content="{SITE}"><meta property="og:type" content="website"><meta property="og:title" content="CyNews 24 – Cyprus News · Новости Кипра · Ειδήσεις Κύπρου"><meta property="og:description" content="Cyprus news in English, Russian and Greek."><meta property="og:url" content="{abs_("/")}"><meta property="og:image" content="{abs_("/assets/og-default.jpg")}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="CyNews 24"><meta name="twitter:description" content="Cyprus news in English, Russian and Greek."><meta name="twitter:image" content="{abs_("/assets/og-default.jpg")}">
<link rel="icon" href="{href("/favicon.svg")}" type="image/svg+xml"><link rel="apple-touch-icon" href="{href("/apple-touch-icon.png")}"><meta name="theme-color" content="#111827"><link rel="stylesheet" href="{href("/assets/css/style.css")}">
<link rel="alternate" type="application/rss+xml" title="{SITE} (EN)" href="{href("/en/feed.xml")}">
{ld}
{google_tags()}
{TRAVELPAYOUTS_DRIVE}</head>
<body class="choose-body"><main class="choose"><div><div class="logo"><b>CyNews</b><i>24</i></div><p>Cyprus news · Новости Кипра · Ειδήσεις Κύπρου</p>
<div class="btns"><a href="{href("/ru/")}" hreflang="ru" lang="ru">Русский</a><a href="{href("/en/")}" hreflang="en" lang="en">English</a><a href="{href("/el/")}" hreflang="el" lang="el">Ελληνικά</a></div></div></main>
{cookie_banner("en")}</body></html>'''

def rss(l):
    items=news_sorted()
    x=['<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>',f'<title>{SITE} ({l.upper()})</title><link>{abs_(f"/{l}/")}</link><description>{e(HOME_D[l])}</description><language>{l}</language>']
    for s in items:
        dt=datetime.datetime.fromisoformat(s["date"]+"T09:00:00+02:00")
        x.append(f'<item><title>{e(s["title"][l])}</title><link>{abs_(f"/{l}/{s["slug"]}/")}</link><guid>{abs_(f"/{l}/{s["slug"]}/")}</guid><pubDate>{dt.strftime("%a, %d %b %Y %H:%M:%S +0200")}</pubDate><description>{e(s["lede"][l])}</description></item>')
    x.append('</channel></rss>'); return "".join(x)

def hreflang_xml(pathfn, langs):
    alts="".join(f'<xhtml:link rel="alternate" hreflang="{x}" href="{abs_(pathfn(x))}"/>' for x in langs)
    return alts+f'<xhtml:link rel="alternate" hreflang="x-default" href="{abs_(x_default_path(pathfn, langs))}"/>'
def sitemap():
    def entry(pathfn,lastmod,prio,langs=None):
        langs=list(langs or LANGS)
        alts=hreflang_xml(pathfn, langs)
        return "".join(f'<url><loc>{abs_(pathfn(l))}</loc><lastmod>{lastmod}</lastmod><priority>{prio}</priority>{alts}</url>' for l in langs)
    x=['<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
       f'<url><loc>{abs_("/")}</loc><lastmod>{TODAY}</lastmod><priority>0.5</priority>'+hreflang_xml(lambda l:f"/{l}/", LANGS)+'</url>']
    x.append(entry(lambda l:f"/{l}/",TODAY,"1.0"))
    for c in CATS: x.append(entry(lambda l,c=c:f"/{l}/{c}/",TODAY,"0.7"))
    for s in STORIES:
        langs=indexed_langs(s)
        if langs:
            # A guide's lastmod is the date on the page. News keeps the build date.
            last=(s.get("updated") or s["date"])[:10] if s.get("guide") else TODAY
            x.append(entry(lambda l,s=s:f"/{l}/{s['slug']}/",last,"0.8",langs))
    x.append(entry(lambda l:f"/{l}/about/",TODAY,"0.3"))
    x.append(entry(lambda l:f"/{l}/editorial-policy/",TODAY,"0.3"))
    x.append(entry(lambda l:f"/{l}/affiliate-disclosure/",TODAY,"0.3"))
    x.append(entry(lambda l:f"/{l}/privacy/",TODAY,"0.3"))
    x.append(entry(lambda l:f"/{l}/cookies/",TODAY,"0.3"))
    x.append(entry(lambda l:f"/{l}/advertising/",TODAY,"0.4"))
    x.append(entry(lambda l:f"/{l}/advertise/",TODAY,"0.4"))
    x.append(entry(lambda l:f"/{l}/property-consultation/",TODAY,"0.5"))
    x.append(entry(lambda l:f"/{l}/events/",TODAY,"0.6"))
    x.append(entry(lambda l:f"/{l}/travel/",TODAY,"0.6"))
    x.append(entry(lambda l:f"/{l}/guides/",TODAY,"0.8"))
    x.append(entry(lambda l:f"/{l}/relocation/",TODAY,"0.7"))
    for r in REGIONS:
        x.append(entry(lambda l, r=r: f"/{l}/world/{r}/", TODAY, "0.6"))
    for prop in published_listings():
        pid=prop["id"]
        x.append(entry(lambda l, pid=pid: f"/{l}/real-estate/{pid}/", TODAY, "0.5"))
    x.append('</urlset>'); return "".join(x)

def news_sitemap():
    """Google News sitemap: articles whose publication time is within the last 48 hours."""
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2)))
    cutoff=now-datetime.timedelta(hours=48)
    x=['<?xml version="1.0" encoding="UTF-8"?>',
       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">']
    for s in sorted_all():
        if s.get("guide"): continue
        pub,_mod=article_times(s)
        published=datetime.datetime.fromisoformat(pub)
        if published < cutoff: continue
        for l in indexed_langs(s):
            loc=abs_(f"/{l}/{s['slug']}/")
            x.append("<url><loc>"+e(loc)+"</loc><news:news><news:publication><news:name>CyNews 24</news:name><news:language>"+l+"</news:language></news:publication><news:publication_date>"+e(pub)+"</news:publication_date><news:title>"+e(s["title"][l])+"</news:title></news:news></url>")
    x.append("</urlset>")
    return "".join(x)

_MYCYTAX=None
def mycytax_catalog():
    """Fetched once per build. A sitemap timeout falls back to the committed list."""
    global _MYCYTAX
    if _MYCYTAX is None:
        _MYCYTAX=mycytax.load_catalog()
    return _MYCYTAX
def w(path,content):
    p=OUT+path; os.makedirs(os.path.dirname(p),exist_ok=True); open(p,"w",encoding="utf8").write(content)
def page_404():
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">{PATH_CANON_JS}{YANDEX_VERIFICATION}{IMPACT_VERIFICATION}{bing_meta()}'
      f'<title>404 — {SITE}</title><meta name="robots" content="noindex">'
      f'<link rel="stylesheet" href="{href("/assets/css/style.css")}">{google_tags()}{TRAVELPAYOUTS_DRIVE}</head>'
      f'<body><main class="choose"><div><div class="logo"><b>CyNews</b><i>24</i></div>'
      f'<p>404 — Page not found · Страница не найдена · Η σελίδα δεν βρέθηκε</p>'
      f'<div class="btns"><a href="{href("/ru/")}">RU</a><a href="{href("/en/")}">EN</a><a href="{href("/el/")}">EL</a></div>'
      f'</div></main>{cookie_banner("en")}</body></html>')

def main():
    small=enforce_lead_images()
    if small:
        photos=[s for s in small if not lead_geometry(s)["placeholder"]]
        print(f"Lead photographs under 1200px: {len(photos)} (kept; social tags use that file)")
        for s in small:
            geo=lead_geometry(s)
            if geo["placeholder"]:
                print(f"  {s['slug']}: no source photograph")
            else:
                sw,sh=geo["native"]; lw,lh=geo["lead"]
                print(f"  {s['slug']}: source {sw}x{sh}px, lead {lw}x{lh}px")
    for d in ["ru","en","el","assets"]:
        shutil.rmtree(f"{OUT}/{d}",ignore_errors=True)
    os.makedirs(OUT+"/assets/css",exist_ok=True)
    build_assets()
    build_event_photos()
    build_listing_photos()
    w("/assets/css/style.css",CSS)
    os.makedirs(OUT+"/assets/js",exist_ok=True)
    w("/assets/js/affiliates.js",affiliates_js())
    w("/index.html",page_root())
    for l in LANGS:
        w(f"/{l}/index.html",page_home(l))
        for c in CATS: w(f"/{l}/{c}/index.html",page_cat(l,c))
        for prop in published_listings():
            w(f"/{l}/real-estate/{prop['id']}/index.html", page_listing(l, prop))
        for s in STORIES: w(f"/{l}/{s['slug']}/index.html",page_article(l,s))
        for s in STORIES:
            if s["file"] != s["slug"]:
                w(f"/{l}/{s['file']}/index.html", page_moved(l, s))
        w(f"/{l}/about/index.html",page_about(l))
        w(f"/{l}/editorial-policy/index.html",page_info(l,"editorial-policy",POLICY[l],"WebPage"))
        w(f"/{l}/affiliate-disclosure/index.html",page_info(l,"affiliate-disclosure",DISCLOSURE[l],"WebPage"))
        w(f"/{l}/privacy/index.html",page_info(l,"privacy",privacy_for(l),"WebPage"))
        w(f"/{l}/cookies/index.html",page_info(l,"cookies",cookies_for(l),"WebPage"))
        w(f"/{l}/events/index.html",page_events(l))
        for r in REGIONS:
            w(f"/{l}/world/{r}/index.html", page_region(l, r))
        w(f"/{l}/relocation/index.html", page_relocation(l))
        w(f"/{l}/travel/index.html",page_travel(l))
        w(f"/{l}/guides/index.html",page_guides(l))
        w(f"/{l}/advertising/index.html",page_advertising(l))
        w(f"/{l}/advertising/thanks/index.html",page_ad_thanks(l))
        w(f"/{l}/advertise/index.html",page_advertise(l))
        w(f"/{l}/advertise/thanks/index.html",page_advertise_thanks(l))
        w(f"/{l}/property-consultation/index.html",page_property_consultation(l))
        w(f"/{l}/property-consultation/thanks/index.html",page_property_consult_thanks(l))
        w(f"/{l}/thanks/index.html",page_lead_thanks(l))
        w(f"/{l}/feed.xml",rss(l))
    # One feed per language. /feed.xml was a second copy of the English feed.
    stale_feed=os.path.join(OUT,"feed.xml")
    if os.path.isfile(stale_feed):
        os.remove(stale_feed)
    w("/sitemap.xml",sitemap())
    w("/news-sitemap.xml",news_sitemap())
    w("/robots.txt","User-agent: *\nAllow: /\nDisallow: /feed.xml\nDisallow: /ru/feed.xml\nDisallow: /en/feed.xml\nDisallow: /el/feed.xml\n\n"+f"Sitemap: {BASE}/sitemap.xml\nSitemap: {BASE}/news-sitemap.xml\n")
    w("/404.html",page_404())
    w("/_headers","/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n")
    open(os.path.join(OUT,".nojekyll"),"w").close()
    # Google Search Console verification. Rewritten on every build so a rebuild cannot drop it.
    w("/google62249645dc64d12b.html","google-site-verification: google62249645dc64d12b.html\n")
    # GitHub Pages custom domain. Rewritten on every build so a rebuild cannot drop it.
    w("/CNAME","cynews24.net\n")
    w("/ads.txt",ADS_TXT)
    # IndexNow key file. Rewritten on every build so a rebuild cannot drop it.
    w(f"/{indexnow_key()}.txt", indexnow_key()+"\n")
    write_credits_md()
    print("built",len(STORIES),"stories; BASE=",BASE,"; PREFIX=",PREFIX or "(root)","; OUT=",OUT,"; photos",sum(1 for s in STORIES if credit_for(s)),"; untranslated",{l:sorted(s["slug"] for s in STORIES if l in s["missing"]) for l in ("en","el")})
if __name__=="__main__":
    main()
