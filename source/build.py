# -*- coding: utf-8 -*-
import os, sys, json, html, shutil, re, datetime
from urllib.parse import urlparse
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s1,s2,s3,s4
STORIES = s1.S + s2.S + s3.S + s4.S
with open(os.path.join(HERE,"events.json"),encoding="utf8") as _ef:
    _EV=json.load(_ef)
EV_EVENTS=_EV["events"]
EV_PHOTOS=_EV["photos"]
SITE = "CyNews 24"
# Absolute origin, no trailing slash. Include the repo path for GitHub project pages:
#   BASE=https://anlap26.github.io/cynews24 python3 build.py
BASE = os.environ.get("BASE","https://cynews24.example").rstrip("/")
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
CATN = {
 "en":dict(zip(CATS,["Politics","Economy","Real Estate","Society","Tourism","Sport","World"])),
 "ru":dict(zip(CATS,["Политика","Экономика","Недвижимость","Общество","Туризм","Спорт","В мире"])),
 "el":dict(zip(CATS,["Πολιτική","Οικονομία","Ακίνητα","Κοινωνία","Τουρισμός","Αθλητισμός","Κόσμος"]))}
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
TODAY="2026-11-13"
UI = {
 "en":dict(home="Home",latest="Latest",more="More news",sources="Sources",related="Related stories",toplines="Top stories",
  byline="By the CyNews 24 newsroom",illus="Illustration created for CyNews 24 (AI-generated, not a photograph)",
  sources_note="This article is an original rewrite of facts reported by the outlets below; read the originals for full detail.",
  read="Read more",tags="Topics",lang="Language",about="About us",ads="Advertise & Contact",events="Events",menu="Sections",skip="Skip to content",
  tagline="Cyprus news in three languages",
  footer="CyNews 24 summarises public reporting from Cypriot and international media in Russian, English and Greek. Articles are rewritten in our own words and link to their sources; photographs are used under open licences and credited. CyNews 24 is not affiliated with the outlets cited.",
  copy="All rights reserved.",updated="Updated",home_h="Top stories from Cyprus",realestate_h="Real estate & planning",allnews="All news",
  cat_h="{c} — news from Cyprus", crumb_home="Home"),
 "ru":dict(home="Главная",latest="Последние новости",more="Ещё новости",sources="Источники",related="Читайте также",toplines="Главное",
  byline="Редакция CyNews 24",illus="Иллюстрация создана для CyNews 24 (сгенерирована ИИ, не фотография)",
  sources_note="Материал — авторский пересказ фактов, опубликованных изданиями ниже; полные подробности — в оригиналах.",
  read="Читать далее",tags="Темы",lang="Язык",about="О проекте",ads="Реклама и контакты",events="Мероприятия",menu="Разделы",skip="Перейти к содержанию",
  tagline="Новости Кипра на трёх языках",
  footer="CyNews 24 обобщает публикации кипрских и международных СМИ на русском, английском и греческом языках. Тексты написаны своими словами и содержат ссылки на источники; фотографии используются по открытым лицензиям с указанием автора. CyNews 24 не связан с упомянутыми изданиями.",
  copy="Все права защищены.",updated="Обновлено",home_h="Главные новости Кипра",realestate_h="Недвижимость и градостроительство",allnews="Все новости",
  cat_h="{c} — новости Кипра", crumb_home="Главная"),
 "el":dict(home="Αρχική",latest="Τελευταία νέα",more="Περισσότερες ειδήσεις",sources="Πηγές",related="Σχετικά θέματα",toplines="Κορυφαία θέματα",
  byline="Η συντακτική ομάδα του CyNews 24",illus="Εικονογράφηση για το CyNews 24 (δημιουργήθηκε με ΤΝ, όχι φωτογραφία)",
  sources_note="Το κείμενο είναι πρωτότυπη αναδιατύπωση γεγονότων που δημοσίευσαν τα παρακάτω μέσα· για πλήρεις λεπτομέρειες δείτε τα πρωτότυπα.",
  read="Διαβάστε περισσότερα",tags="Θέματα",lang="Γλώσσα",about="Σχετικά με εμάς",ads="Διαφήμιση & Επικοινωνία",events="Εκδηλώσεις",menu="Ενότητες",skip="Μετάβαση στο περιεχόμενο",
  tagline="Ειδήσεις Κύπρου σε τρεις γλώσσες",
  footer="Το CyNews 24 συνοψίζει δημοσιεύματα κυπριακών και διεθνών μέσων στα ρωσικά, αγγλικά και ελληνικά. Τα κείμενα γράφονται με δικά μας λόγια και παραπέμπουν στις πηγές τους· οι φωτογραφίες χρησιμοποιούνται με ανοιχτές άδειες και αναφέρουν τον δημιουργό. Το CyNews 24 δεν συνδέεται με τα μέσα που αναφέρονται.",
  copy="Με επιφύλαξη παντός δικαιώματος.",updated="Ενημερώθηκε",home_h="Κορυφαίες ειδήσεις από την Κύπρο",realestate_h="Ακίνητα και πολεοδομία",allnews="Όλες οι ειδήσεις",
  cat_h="{c} — ειδήσεις από την Κύπρο", crumb_home="Αρχική"),
}
HOME_T = {"en":"CyNews 24 – Latest Cyprus News: Politics, Economy, Property",
 "ru":"CyNews 24 — Новости Кипра сегодня: политика, экономика, недвижимость",
 "el":"CyNews 24 — Ειδήσεις Κύπρου: πολιτική, οικονομία, ακίνητα"}
HOME_D = {"en":"CyNews 24 brings you the latest Cyprus news today in English, Russian and Greek: politics, economy, real estate, society, tourism and sport, with sources linked.",
 "ru":"CyNews 24 — свежие новости Кипра сегодня на русском, английском и греческом: политика, экономика, недвижимость, общество, туризм и спорт со ссылками на источники.",
 "el":"Το CyNews 24 φέρνει τις τελευταίες ειδήσεις Κύπρου σήμερα σε ελληνικά, αγγλικά και ρωσικά: πολιτική, οικονομία, ακίνητα, κοινωνία, τουρισμός, αθλητισμός, με συνδέσμους στις πηγές."}
GKW = {"en":["Cyprus news","Cyprus news today","latest news Cyprus","Cyprus real estate news","Cyprus property market","Limassol news","Nicosia news","Paphos news","Larnaca news","Cyprus politics","Cyprus economy","news from Cyprus in English"],
 "ru":["Кипр новости","новости Кипра сегодня","последние новости Кипра","новости недвижимости Кипра","рынок недвижимости Кипра","новости Лимассола","новости Никосии","новости Пафоса","Кипр на русском","политика Кипра","экономика Кипра"],
 "el":["Κύπρος ειδήσεις","ειδήσεις Κύπρου σήμερα","τελευταία νέα Κύπρος","ειδήσεις ακινήτων Κύπρος","αγορά ακινήτων Κύπρος","ειδήσεις Λεμεσός","ειδήσεις Λευκωσία","ειδήσεις Πάφος","πολιτική Κύπρος","οικονομία Κύπρου"]}
CAT_D = {
 "en":{"politics":"Cyprus politics news: Cyprus problem, government, parliament and EU affairs.","economy":"Cyprus economy news: business, pensions, technology and finance.","real-estate":"Cyprus real estate news: property law, planning, new builds and housing market stories.","society":"Cyprus society news: courts, police, health and everyday life.","tourism":"Cyprus tourism and events news: what's on, festive markets and travel.","sport":"Cyprus sport news: results, athletes and major events.","world":"World news with a Cyprus angle: EU, technology and global events."},
 "ru":{"politics":"Политические новости Кипра: кипрская проблема, правительство, парламент и дела ЕС.","economy":"Экономические новости Кипра: бизнес, пенсии, технологии и финансы.","real-estate":"Новости недвижимости Кипра: законы, градостроительство, новостройки и рынок жилья.","society":"Общественные новости Кипра: суды, полиция, здоровье и повседневная жизнь.","tourism":"Новости туризма и событий Кипра: афиша, праздничные рынки и путешествия.","sport":"Спортивные новости Кипра: результаты, спортсмены и крупные события.","world":"Мировые новости с кипрским акцентом: ЕС, технологии и глобальные события."},
 "el":{"politics":"Πολιτικές ειδήσεις Κύπρου: Κυπριακό, κυβέρνηση, Βουλή και ευρωπαϊκά θέματα.","economy":"Οικονομικές ειδήσεις Κύπρου: επιχειρήσεις, συντάξεις, τεχνολογία και χρηματοοικονομικά.","real-estate":"Ειδήσεις ακινήτων Κύπρου: νομοθεσία, πολεοδομία, νεόδμητα και αγορά κατοικίας.","society":"Κοινωνικές ειδήσεις Κύπρου: δικαστήρια, αστυνομία, υγεία και καθημερινότητα.","tourism":"Ειδήσεις τουρισμού και εκδηλώσεων Κύπρου: προγράμματα, εορταστικές αγορές και ταξίδια.","sport":"Αθλητικές ειδήσεις Κύπρου: αποτελέσματα, αθλητές και μεγάλες διοργανώσεις.","world":"Παγκόσμιες ειδήσεις με κυπριακό ενδιαφέρον: ΕΕ, τεχνολογία και διεθνή γεγονότα."}}
ABOUT = {
 "en":dict(t="About CyNews 24",d="How CyNews 24 works: a trilingual Cyprus news site that rewrites public reporting in its own words, links to sources and credits openly licensed photographs.",
  p=["CyNews 24 is a news site about Cyprus published in Russian, English and Greek. Every story exists in all three languages.",
   "We follow reporting from Cypriot and international outlets, check that the same story is not covered twice, and write each article in our own words. We add facts only from the cited sources — no invented numbers or quotes — and every article lists the original reports it is based on.",
   "Photographs on this site are real pictures published under open licences that allow commercial use and adaptation — CC0, CC BY or CC BY-SA, from Wikimedia Commons. Each picture is credited with its author, source and licence and links to the original file. Where the licence is CC BY-SA, the cropped and watermarked version stays under that same licence. A picture shows the place or subject of a story; it is not a photograph of a person named in the article unless the credit says so.",
   "CyNews 24 is an independent project and is not affiliated with the media outlets it cites. For breaking developments, always check the linked original sources."]),
 "ru":dict(t="О проекте CyNews 24",d="Как устроен CyNews 24: трёхъязычный сайт новостей Кипра, который пересказывает открытые публикации своими словами, указывает источники и подписывает фотографии с открытой лицензией.",
  p=["CyNews 24 — новостной сайт о Кипре на русском, английском и греческом языках. Каждый материал доступен на всех трёх языках.",
   "Мы следим за публикациями кипрских и международных изданий, не дублируем одну и ту же историю и пишем каждый материал своими словами. Мы добавляем только факты из указанных источников — без выдуманных цифр и цитат — и в каждом материале перечисляем оригинальные публикации, на которых он основан.",
   "Фотографии на сайте — настоящие снимки по открытым лицензиям, которые разрешают коммерческое использование и переработку: CC0, CC BY или CC BY-SA, с Wikimedia Commons. У каждого снимка указаны автор, источник и лицензия и есть ссылка на оригинал. Если лицензия CC BY-SA, кадрированная версия с водяным знаком остаётся под той же лицензией. Снимок показывает место или тему материала и не является фотографией человека, названного в тексте, если это прямо не сказано в подписи.",
   "CyNews 24 — независимый проект, не связанный с упомянутыми изданиями. По оперативным новостям всегда сверяйтесь с оригинальными источниками по ссылкам."]),
 "el":dict(t="Σχετικά με το CyNews 24",d="Πώς λειτουργεί το CyNews 24: τρίγλωσσος ιστότοπος ειδήσεων Κύπρου που αναδιατυπώνει δημόσιο ρεπορτάζ με δικά του λόγια, παραπέμπει σε πηγές και αναφέρει φωτογραφίες με ανοιχτή άδεια.",
  p=["Το CyNews 24 είναι ιστότοπος ειδήσεων για την Κύπρο στα ρωσικά, αγγλικά και ελληνικά. Κάθε είδηση υπάρχει και στις τρεις γλώσσες.",
   "Παρακολουθούμε ρεπορτάζ κυπριακών και διεθνών μέσων, φροντίζουμε να μην καλύπτουμε δύο φορές το ίδιο θέμα και γράφουμε κάθε άρθρο με δικά μας λόγια. Προσθέτουμε μόνο γεγονότα από τις αναφερόμενες πηγές — χωρίς επινοημένους αριθμούς ή δηλώσεις — και κάθε άρθρο παραθέτει τα πρωτότυπα δημοσιεύματα στα οποία βασίζεται.",
   "Οι φωτογραφίες του ιστότοπου είναι πραγματικές εικόνες με ανοιχτές άδειες που επιτρέπουν εμπορική χρήση και διασκευή — CC0, CC BY ή CC BY-SA, από τα Wikimedia Commons. Κάθε εικόνα αναφέρει τον δημιουργό, την πηγή και την άδεια και συνδέεται με το πρωτότυπο αρχείο. Όταν η άδεια είναι CC BY-SA, η περικομμένη εκδοχή με το υδατογράφημα παραμένει στην ίδια άδεια. Η εικόνα δείχνει τον τόπο ή το θέμα του άρθρου και δεν είναι φωτογραφία προσώπου που κατονομάζεται στο κείμενο, εκτός αν αυτό αναφέρεται στη λεζάντα.",
   "Το CyNews 24 είναι ανεξάρτητο εγχείρημα και δεν συνδέεται με τα μέσα που αναφέρει. Για εξελισσόμενα γεγονότα, ελέγχετε πάντα τις πρωτότυπες πηγές."])}
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
    c=CREDITS.get(s["img"])
    if not c: return UI[l]["illus"]
    label={"en":"Photo","ru":"Фото","el":"Φωτογραφία"}[l]
    return (f'{label}: {e(c["author"])} / '
            f'<a href="{e(c["page"])}">{e(c["source"])}</a>, '
            f'<a href="{e(c["license_url"])}">{e(c["license"])}</a>')
def image_ld(s):
    c=CREDITS.get(s["img"])
    obj={"@type":"ImageObject","url":abs_(f"/assets/img/{s['img']}-1200.webp"),
         "contentUrl":abs_(f"/assets/img/{s['img']}-1200.webp"),"width":1200,"height":675}
    if c:
        credit=f'{c["author"]} / {c["source"]}, {c["license"]}'
        obj.update({"creditText":credit,"copyrightNotice":credit,"license":c["license_url"],
                    "acquireLicensePage":c["page"],"creator":{"@type":"Person","name":c["author"]}})
    return obj
def write_credits_md():
    lines=["# Photo credits","","Story photographs are openly licensed pictures. The generator crops each one to 16:9, resizes it and adds a CyNews 24 watermark. Adaptations of CC BY-SA photographs stay under the same licence.","","| Image | What it shows | Author | Licence | Original |","|---|---|---|---|---|"]
    for s in STORIES:
        c=CREDITS.get(s["img"])
        if not c:
            lines.append(f'| `{s["img"]}` | Original illustration kept | — | — | — |')
            continue
        lines.append(f'| `{s["img"]}` | {c.get("depicts","")} | {c["author"]} | [{c["license"]}]({c["license_url"]}) | [{c["source"]}]({c["page"]}) |')
    lines += ["","## Event photographs","","| Image | Author | Licence | Original |","|---|---|---|---|"]
    for key,p in EV_PHOTOS.items():
        lines.append(f'| `events/{key}` | {p["author"]} | [{p["license"]}]({p["license_url"]}) | [{p["source"]}]({p["page"]}) |')
    lines += ["","CC BY-SA files: the cropped, resized and watermarked images published with the site are adaptations and remain under the same CC BY-SA licence as the original.",""]
    text="\n".join(lines)+"\n"
    open(os.path.join(OUT,"CREDITS.md"),"w",encoding="utf8").write(text)

# ---------- assets ----------
def build_assets():
    d=OUT+"/assets/img"; os.makedirs(d,exist_ok=True)
    for s in STORIES:
        c=CREDITS.get(s["img"])
        photo=os.path.join(HERE,"photos",c["file"]) if c else ""
        if c and os.path.exists(photo):
            src=Image.open(photo)
            focus=tuple(c.get("focus",[0.5,0.5]))
            plain=cover_crop(src,1200,675,focus)
            watermark(plain).save(f"{d}/{s['img']}-1200.webp","WEBP",quality=78,method=6)
            watermark(plain.resize((600,338),Image.LANCZOS)).save(f"{d}/{s['img']}-600.webp","WEBP",quality=76,method=6)
            watermark(plain.crop((0,22,1200,652))).save(f"{d}/{s['img']}-og.jpg","JPEG",quality=82,optimize=True,progressive=True)
        else:
            im=Image.open(os.path.join(SRC, f"{s['img']}.jpg")).convert("RGB")
            a=im.resize((1200,675),Image.LANCZOS); a.save(f"{d}/{s['img']}-1200.webp","WEBP",quality=78,method=6)
            b=im.resize((600,338),Image.LANCZOS); b.save(f"{d}/{s['img']}-600.webp","WEBP",quality=76,method=6)
            o=im.resize((1200,675),Image.LANCZOS).crop((0,22,1200,652)); o.save(f"{d}/{s['img']}-og.jpg","JPEG",quality=82,optimize=True,progressive=True)
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
nav.cats{border-bottom:1px solid var(--line);background:#fff;position:sticky;top:0;z-index:20}
nav.cats ul{list-style:none;margin:0;padding:0;display:flex;overflow-x:auto;scrollbar-width:none}
nav.cats li a{display:block;padding:13px 14px;font-weight:700;font-size:15px;white-space:nowrap;border-bottom:4px solid transparent}
nav.cats li a:hover{border-color:var(--ink)}nav.cats li a[aria-current=page]{border-color:var(--acc)}
.tagline{font-size:13px;color:var(--mut);padding:10px 0 0}
h1.sec{font-size:28px;margin:18px 0 14px;border-top:4px solid var(--ink);padding-top:8px;letter-spacing:-.3px}
.lead{display:grid;grid-template-columns:1.9fr 1fr;gap:24px;margin:8px 0 28px}
.card .img{display:block;background:var(--soft);overflow:hidden}.card .img img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
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
.crumb{font-size:13px;color:var(--mut);margin:18px 0 8px}.crumb a{text-decoration:underline}
article.a{max-width:760px;margin:0 auto}
article.a h1{font-size:40px;line-height:1.1;letter-spacing:-.8px;margin:6px 0 12px}
.dek{font-size:20px;line-height:1.4;font-weight:600;color:#23272d;margin:0 0 14px}
.by{font-size:14px;color:var(--mut);border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:10px 0;margin-bottom:18px;display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}
figure{margin:0 0 22px}figcaption{font-size:13px;color:var(--mut);padding-top:6px}figcaption a{color:#0b57b0;text-decoration:underline}
.body p{font-size:18px;line-height:1.65;margin:0 0 18px}
.src{background:var(--soft);border-left:4px solid var(--acc);padding:14px 16px;margin:28px 0;font-size:15px}.src h2{font-size:15px;margin:0 0 6px;text-transform:uppercase;letter-spacing:.5px}.src p{margin:0 0 8px;color:var(--mut)}.src ul{margin:0;padding-left:18px}.src a{text-decoration:underline;color:#0b57b0}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 28px;padding:0;list-style:none}.tags li{border:1px solid var(--line);border-radius:20px;padding:3px 12px;font-size:13px;color:#33383f}
.rel h2{font-size:22px;border-top:4px solid var(--ink);padding-top:8px}
.rel .grid{grid-template-columns:repeat(3,1fr)}
.langsw{display:flex;gap:10px;font-size:14px;margin:0 0 6px;flex-wrap:wrap}.langsw a{text-decoration:underline}
footer{background:var(--dark);color:#c8cdd5;margin-top:48px;padding:28px 0;font-size:14px}footer .logo{font-size:22px;margin-bottom:10px}footer a{text-decoration:underline}
footer p{max-width:820px;margin:8px 0}
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
@media(max-width:980px){.lead{grid-template-columns:1fr}.grid,.g3{grid-template-columns:repeat(2,1fr)}.cols{grid-template-columns:1fr}.rel .grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.lead .big h2{font-size:26px}article.a h1,.adpage h1{font-size:30px}.grid,.g3,.rel .grid,.fmts,.weekband ul{grid-template-columns:1fr}.side .card{grid-template-columns:110px 1fr}.ev{grid-template-columns:1fr}.date{display:none}.body p{font-size:17px}h1.sec{font-size:24px}}
"""

def alt_links(l, pathfn):
    out=[]
    for x in LANGS:
        out.append(f'<link rel="alternate" hreflang="{x}" href="{abs_(pathfn(x))}">')
    out.append(f'<link rel="alternate" hreflang="x-default" href="{abs_("/")}">')
    return "\n".join(out)

def head(l, title, desc, kws, path, pathfn, og_img, typ="website", extra="", jsonld=None, pub=None, robots="index,follow,max-image-preview:large,max-snippet:-1"):
    h=[f'<!doctype html><html lang="{l}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
    f'<title>{e(title)}</title><meta name="description" content="{e(desc)}">',
    f'<meta name="keywords" content="{e(", ".join(kws))}">',
    f'<meta name="robots" content="{e(robots)}">',
    f'<link rel="canonical" href="{abs_(path)}">',
    alt_links(l,pathfn),
    f'<meta property="og:site_name" content="{SITE}"><meta property="og:type" content="{typ}"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{abs_(path)}"><meta property="og:image" content="{abs_(og_img)}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:locale" content="{LOCALE[l]}">']
    for x in LANGS:
        if x!=l: h.append(f'<meta property="og:locale:alternate" content="{LOCALE[x]}">')
    if pub: h.append(f'<meta property="article:published_time" content="{pub}"><meta property="article:modified_time" content="{pub}"><meta property="article:publisher" content="{SITE}">')
    h.append(f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title)}"><meta name="twitter:description" content="{e(desc)}"><meta name="twitter:image" content="{abs_(og_img)}">')
    h.append(f'<link rel="icon" href="{href("/favicon.svg")}" type="image/svg+xml"><link rel="apple-touch-icon" href="{href("/apple-touch-icon.png")}"><meta name="theme-color" content="#111827">')
    h.append(f'<link rel="stylesheet" href="{href("/assets/css/style.css")}">')
    h.append(f'<link rel="alternate" type="application/rss+xml" title="{SITE} ({l.upper()})" href="{href(f"/{l}/feed.xml")}">')
    if jsonld:
        for j in jsonld: h.append('<script type="application/ld+json">'+json.dumps(j,ensure_ascii=False).replace("</","<\\/")+'</script>')
    h.append(extra); h.append('</head>')
    return "\n".join(h)

def header(l, pathfn, active=None):
    u=UI[l]
    sw="".join(f'<a href="{href(pathfn(x))}" hreflang="{x}" lang="{x}" {"aria-current=\"true\"" if x==l else ""} title="{LANGNAME[x]}">{x.upper()}</a>' for x in LANGS)
    nav=f'<li><a href="{href(f"/{l}/")}" {"aria-current=\"page\"" if active=="home" else ""}>{u["home"]}</a></li>'+"".join(
      f'<li><a href="{href(f"/{l}/{c}/")}" {"aria-current=\"page\"" if active==c else ""}>{CATN[l][c]}</a></li>' for c in CATS)
    nav+=f'<li><a href="{href(f"/{l}/events/")}" {"aria-current=\"page\"" if active=="events" else ""}>{u["events"]}</a></li>'
    nav+=f'<li class="promo"><a href="{href(f"/{l}/advertising/")}" {"aria-current=\"page\"" if active=="advertising" else ""}>{u["ads"]}</a></li>'
    return (f'<body><a class="skip" href="#main">{u["skip"]}</a><header class="top"><div class="wrap"><a class="logo" href="{href(f"/{l}/")}" aria-label="{SITE}"><b>CyNews</b><i>24</i></a>'
      f'<div class="tr"><span class="date">{fdate(TODAY,l,True)}</span><nav class="lang" aria-label="{u["lang"]}">{sw}</nav></div></div></header>'
      f'<nav class="cats" aria-label="{u["menu"]}"><div class="wrap"><ul>{nav}</ul></div></nav>')

def footer(l):
    u=UI[l]
    return (f'<footer><div class="wrap"><div class="logo"><b>CyNews</b><i>24</i></div><p>{u["footer"]}</p>'
      f'<p><a href="{href(f"/{l}/about/")}">{u["about"]}</a> · <a href="{href(f"/{l}/advertising/")}">{u["ads"]}</a> · '+" · ".join(f'<a href="{href(f"/{x}/")}" hreflang="{x}" lang="{x}">{LANGNAME[x]}</a>' for x in LANGS)+f'</p><p>© 2026 {SITE}. {u["copy"]}</p></div></footer></body></html>')

def S_(s,key,l): return s[key][l]
def img_tag(s,l,w,lazy=True,prio=False,sizes="100%"):
    n=s["img"]; alt=e(s["alt"][l])
    if w==600: src=href(f"/assets/img/{n}-600.webp"); W,H=600,338
    else: src=href(f"/assets/img/{n}-1200.webp"); W,H=1200,675
    srcset=f'{href(f"/assets/img/{n}-600.webp")} 600w, {href(f"/assets/img/{n}-1200.webp")} 1200w'
    ex = ' fetchpriority="high"' if prio else (' loading="lazy"' if lazy else '')
    return f'<img src="{src}" srcset="{srcset}" sizes="{sizes}" width="{W}" height="{H}" alt="{alt}" decoding="async"{ex}>'

def card(s,l,kind="grid",lazy=True):
    u=UI[l]; link=href(f'/{l}/{s["slug"]}/')
    if kind=="side":
        return (f'<article class="card"><a href="{link}" class="img">{img_tag(s,l,600,lazy,sizes="128px")}</a><div><span class="cat">{CATN[l][s["cat"]]}</span><a href="{link}"><h3>{e(s["title"][l])}</h3></a><div class="meta"><time datetime="{s["date"]}">{fdate(s["date"],l)}</time></div></div></article>')
    return (f'<article class="card"><a href="{link}" class="img" tabindex="-1">{img_tag(s,l,600,lazy,sizes="(max-width:600px) 100vw,(max-width:980px) 50vw,280px")}</a><span class="cat" style="display:block;margin-top:10px">{CATN[l][s["cat"]]}</span><a href="{link}"><h3 style="margin-top:4px">{e(s["title"][l])}</h3></a><p>{e(trunc(s["lede"][l],150))}</p><div class="meta"><time datetime="{s["date"]}">{fdate(s["date"],l)}</time></div></article>')

ORDER_LEAD=["fitto-cyprus-talks","eu-ai-summit-dublin","frozen-assets-51-million","property-sale-fines-100000","governors-beach-caravan-eviction"]
BYSLUG={s["slug"]:s for s in STORIES}
def sorted_all():
    return sorted(STORIES,key=lambda s:(s["date"],STORIES.index(s)),reverse=True)

def page_home(l):
    u=UI[l]; pathfn=lambda x:f"/{x}/"
    lead=BYSLUG[ORDER_LEAD[0]]; side=[BYSLUG[x] for x in ORDER_LEAD[1:]]
    re_=[s for s in STORIES if s["cat"]=="real-estate"]
    used=set(ORDER_LEAD)|{s["slug"] for s in re_}
    rest=[s for s in sorted_all() if s["slug"] not in used]
    latest=sorted_all()[:8]
    kws=GKW[l]
    ld=[{"@context":"https://schema.org","@type":"WebSite","name":SITE,"url":abs_(f"/{l}/"),"inLanguage":l,"description":HOME_D[l],"publisher":{"@id":abs_("/")+"#org"}},
        {"@context":"https://schema.org","@type":"NewsMediaOrganization","@id":abs_("/")+"#org","name":SITE,"url":abs_("/"),"email":AD_EMAIL,"logo":{"@type":"ImageObject","url":abs_("/assets/logo-512.png"),"width":512,"height":512},"description":HOME_D[l],"contactPoint":{"@type":"ContactPoint","contactType":"advertising","email":AD_EMAIL,"availableLanguage":["Russian","English","Greek"],"url":abs_(f"/{l}/advertising/")}},
        {"@context":"https://schema.org","@type":"ItemList","itemListElement":[{"@type":"ListItem","position":i+1,"url":abs_(f"/{l}/{s['slug']}/"),"name":s["title"][l]} for i,s in enumerate(sorted_all())]}]
    h=head(l,HOME_T[l],HOME_D[l],kws,f"/{l}/",pathfn,"/assets/og-default.jpg",jsonld=ld)
    h+=header(l,pathfn,"home")
    h+=f'<main id="main" class="wrap"><p class="tagline">{u["tagline"]}</p><h1 class="sec">{u["home_h"]}</h1>'
    h+=week_home(l)
    h+=f'<section class="lead" aria-label="{u["toplines"]}"><article class="card big"><a href="{href(f"/{l}/{lead["slug"]}/")}" class="img">{img_tag(lead,l,1200,False,True,"(max-width:980px) 100vw,760px")}</a><span class="cat" style="display:block;margin-top:12px">{CATN[l][lead["cat"]]}</span><a href="{href(f"/{l}/{lead["slug"]}/")}"><h2>{e(lead["title"][l])}</h2></a><p>{e(lead["lede"][l])}</p><div class="meta"><time datetime="{lead["date"]}">{fdate(lead["date"],l)}</time></div></article>'
    h+='<div class="side">'+"".join(card(s,l,"side",False) for s in side)+'</div></section>'
    h+=f'</main><div class="band"><div class="wrap"><h2 style="font-size:24px;border-top:4px solid var(--acc);padding-top:8px;margin:18px 0 16px"><a href="{href(f"/{l}/real-estate/")}">{u["realestate_h"]}</a></h2><div class="grid">'+"".join(card(s,l) for s in re_[:4])+'</div></div></div>'
    h+=f'<div class="wrap"><div class="cols"><section><h2 style="font-size:24px;border-top:4px solid var(--ink);padding-top:8px;margin:0 0 16px">{u["more"]}</h2><div class="grid g3">'+"".join(card(s,l) for s in rest)+'</div></section>'
    h+=f'<aside class="latest" aria-label="{u["latest"]}"><h2>{u["latest"]}</h2><ol class="latest">'+"".join(f'<li><span class="cat">{CATN[l][s["cat"]]}</span><a href="{href(f"/{l}/{s["slug"]}/")}">{e(s["title"][l])}</a><span class="meta"><time datetime="{s["date"]}">{fdate(s["date"],l)}</time></span></li>' for s in latest)+'</ol></aside></div></div>'
    h+=footer(l)
    # grid override for tablet/mobile handled by CSS? add class
    return h

def page_cat(l,c):
    u=UI[l]; pathfn=lambda x:f"/{x}/{c}/"
    items=[s for s in sorted_all() if s["cat"]==c]
    title=f'{CATN[l][c]} — {SITE}' if l!="en" else f'{CATN[l][c]} News from Cyprus — {SITE}'
    if l=="ru": title=f'{CATN[l][c]}: новости Кипра — {SITE}'
    if l=="el": title=f'{CATN[l][c]}: ειδήσεις Κύπρου — {SITE}'
    desc=CAT_D[l][c]
    kws=[CATN[l][c]]+GKW[l][:6]
    ld=[{"@context":"https://schema.org","@type":"CollectionPage","name":title,"url":abs_(f"/{l}/{c}/"),"inLanguage":l,"description":desc,"isPartOf":{"@type":"WebSite","name":SITE,"url":abs_(f"/{l}/")}},
        {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":u["crumb_home"],"item":abs_(f"/{l}/")},{"@type":"ListItem","position":2,"name":CATN[l][c],"item":abs_(f"/{l}/{c}/")}]}]
    og=f'/assets/img/{items[0]["img"]}-og.jpg'
    h=head(l,title,desc,kws,f"/{l}/{c}/",pathfn,og,jsonld=ld)+header(l,pathfn,c)
    h+=f'<main id="main" class="wrap"><h1 class="sec">{CATN[l][c]}</h1><p class="meta" style="margin-top:-6px">{e(desc)}</p><div class="grid g3" style="margin-top:18px">'+"".join(card(s,l,lazy=(i>2)) for i,s in enumerate(items))+'</div></main>'+footer(l)
    return h

def page_article(l,s):
    u=UI[l]; path=f"/{l}/{s['slug']}/"; pathfn=lambda x:f"/{x}/{s['slug']}/"
    title=f'{s["title"][l]} | {SITE}'
    desc=trunc(s["lede"][l],158)
    kws=s["kw"][l]+GKW[l][:4]
    pub=f'{s["date"]}T09:00:00+02:00'; mod=f'{TODAY}T10:00:00+02:00'
    og=f'/assets/img/{s["img"]}-og.jpg'
    ld=[{"@context":"https://schema.org","@type":"NewsArticle","mainEntityOfPage":{"@type":"WebPage","@id":abs_(path)},"headline":s["title"][l][:110],"description":s["lede"][l],"image":image_ld(s),"datePublished":pub,"dateModified":mod,"inLanguage":l,"articleSection":CATN[l][s["cat"]],"keywords":", ".join(s["kw"][l]),
        "author":{"@type":"Organization","name":SITE,"url":abs_("/")},"publisher":{"@type":"NewsMediaOrganization","name":SITE,"url":abs_("/"),"logo":{"@type":"ImageObject","url":abs_("/assets/logo-512.png"),"width":512,"height":512}},
        "isBasedOn":[x[1] for x in s["sources"]],"citation":[{"@type":"CreativeWork","name":x[0],"url":x[1]} for x in s["sources"]],"articleBody":" ".join(s["body"][l]),"url":abs_(path),
        "locationCreated":{"@type":"Place","name":"Cyprus"},"about":{"@type":"Place","name":"Cyprus"}},
      {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":u["crumb_home"],"item":abs_(f"/{l}/")},{"@type":"ListItem","position":2,"name":CATN[l][s["cat"]],"item":abs_(f"/{l}/{s['cat']}/")},{"@type":"ListItem","position":3,"name":s["title"][l],"item":abs_(path)}]}]
    preload=f'<link rel="preload" as="image" href="{href(f"/assets/img/{s["img"]}-1200.webp")}" imagesrcset="{href(f"/assets/img/{s["img"]}-600.webp")} 600w, {href(f"/assets/img/{s["img"]}-1200.webp")} 1200w" imagesizes="(max-width:800px) 100vw,760px">'
    h=head(l,title,desc,kws,path,pathfn,og,"article",preload,ld,pub)+header(l,pathfn,s["cat"])
    h+=f'<main id="main" class="wrap"><nav class="crumb" aria-label="breadcrumb"><a href="{href(f"/{l}/")}">{u["crumb_home"]}</a> › <a href="{href(f"/{l}/{s["cat"]}/")}">{CATN[l][s["cat"]]}</a></nav>'
    h+=f'<article class="a"><span class="cat">{CATN[l][s["cat"]]}</span><h1>{e(s["title"][l])}</h1><p class="dek">{e(s["lede"][l])}</p>'
    h+=f'<div class="by"><span>{u["byline"]}</span><span><time datetime="{pub}">{fdate(s["date"],l)}</time></span></div>'
    h+=f'<figure>{img_tag(s,l,1200,False,True,"(max-width:800px) 100vw,760px")}<figcaption>{photo_caption(s,l)}</figcaption></figure>'
    h+='<div class="body">'+"".join(f'<p>{e(p)}</p>' for p in s["body"][l])+'</div>'
    h+=f'<section class="src" aria-label="{u["sources"]}"><h2>{u["sources"]}</h2><p>{u["sources_note"]}</p><ul>'+"".join(f'<li><a href="{e(x[1])}" target="_blank" rel="noopener nofollow">{e(x[0])}</a></li>' for x in s["sources"])+'</ul></section>'
    h+=f'<h2 style="font-size:16px;margin:0 0 8px">{u["tags"]}</h2><ul class="tags">'+"".join(f'<li>{e(k)}</li>' for k in s["kw"][l])+'</ul>'
    h+=f'<p class="langsw">'+" ".join(f'<a href="{href(pathfn(x))}" hreflang="{x}" lang="{x}">{LANGNAME[x]}</a>' for x in LANGS if x!=l)+'</p></article>'
    rel=[x for x in sorted_all() if x["slug"]!=s["slug"]]
    rel.sort(key=lambda x:(x["cat"]!=s["cat"],))
    h+=f'<section class="rel"><h2>{u["related"]}</h2><div class="grid">'+"".join(card(x,l) for x in rel[:3])+'</div></section></main>'+footer(l)
    return h

def page_about(l):
    a=ABOUT[l]; u=UI[l]; pathfn=lambda x:f"/{x}/about/"
    ld=[{"@context":"https://schema.org","@type":"AboutPage","name":a["t"],"url":abs_(f"/{l}/about/"),"inLanguage":l}]
    h=head(l,f'{a["t"]} | {SITE}',a["d"],GKW[l][:5]+[SITE],f"/{l}/about/",pathfn,"/assets/og-default.jpg",jsonld=ld)+header(l,pathfn)
    h+=f'<main id="main" class="wrap"><article class="a"><h1 style="margin-top:24px">{e(a["t"])}</h1><div class="body">'+"".join(f"<p>{e(p)}</p>" for p in a["p"])+'</div></article></main>'+footer(l)
    return h

AD_EMAIL="cynews24@gmail.com"
# Real profile URLs only. An empty string is not rendered, so unfinished accounts stay hidden.
SOCIAL={"facebook":"","instagram":"","telegram":""}
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
     "telegram":'<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M21 4 2.8 11.2c-1.2.5-1.2 1.2-.2 1.5l4.7 1.5 1.8 5.5c.2.6.1.9.8.9.4 0 .6-.2.8-.4l2.6-2.5 5.4 4c.6.4 1.2.2 1.3-.6L22.2 5c.2-1-.4-1.4-1.2-1zM8.7 14.3l9.2-5.8c.4-.3.8 0 .5.3l-7.6 6.9-.3 3.3z"/></svg>',
    }
def social_block(l):
    a=AD[l]; icons=_icons(); names={"facebook":"Facebook","instagram":"Instagram","telegram":"Telegram"}
    bits=[]
    for key in ("facebook","instagram","telegram"):
        url=(SOCIAL.get(key) or "").strip()
        if not url: continue
        bits.append(f'<a href="{e(url)}" rel="noopener noreferrer">{icons[key]}{e(names[key])}</a>')
    if not bits: return ""
    return f'<h2>{e(a["follow"])}</h2><div class="social">{"".join(bits)}</div>'
def contact_point(l):
    return {"@type":"ContactPoint","contactType":"advertising","email":AD_EMAIL,"availableLanguage":["Russian","English","Greek"],"url":abs_(f"/{l}/advertising/")}
def ad_form(l):
    a=AD[l]
    checks="".join(f'<label><input type="checkbox" name="formats" value="{e(name)}"> <span>{e(name)}</span></label>' for name,_desc in a["formats"])
    opts="".join(f'<option value="{e(v)}">{e(lab)}</option>' for v,lab in a["budgets"])
    return f'''<form class="adform" action="https://formsubmit.co/{AD_EMAIL}" method="POST">
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
         "mainEntity":{"@type":"Organization","@id":abs_("/")+"#org","name":SITE,"url":abs_("/"),"email":AD_EMAIL,"contactPoint":contact_point(l)}}]
    cards="".join(f'<article class="fmt"><h3>{e(n)}</h3><p>{e(d)}</p></article>' for n,d in a["formats"])
    h=head(l,f'{a["title"]} | {SITE}',a["desc"],[a["title"],SITE,"Cyprus"],f"/{l}/advertising/",pathfn,"/assets/og-default.jpg",jsonld=ld)
    h+=header(l,pathfn,"advertising")
    h+=f'<main id="main" class="wrap"><article class="adpage"><h1>{e(a["title"])}</h1><p class="leadin">{e(a["pitch"])}</p><p class="adnote">{e(a["rates"])}</p>'
    h+=f'<h2>{e(a["formats_h"])}</h2><div class="fmts">{cards}</div><p class="adnote">{e(a["standards"])}</p>'
    h+=f'<h2>{e(a["contact_h"])}</h2><p>{e(a["email_l"])}: <a class="mail" href="mailto:{AD_EMAIL}">{AD_EMAIL}</a></p>'
    h+=ad_form(l)+social_block(l)+'</article></main>'+footer(l)
    return h
def page_ad_thanks(l):
    a=AD[l]; pathfn=lambda x:f"/{x}/advertising/thanks/"
    h=head(l,f'{a["thanks_t"]} | {SITE}',a["thanks"],[SITE],f"/{l}/advertising/thanks/",pathfn,"/assets/og-default.jpg",robots="noindex,follow")
    h+=header(l,pathfn,"advertising")
    h+=f'<main id="main" class="wrap"><article class="adpage"><h1>{e(a["thanks_t"])}</h1><p class="leadin">{e(a["thanks"])}</p><p><a class="mail" href="{href(f"/{l}/advertising/")}">{e(a["back"])}</a></p></article></main>'+footer(l)
    return h

EVL={
 "en":dict(title="Events",week="This week",upcoming="Coming months",later="Later",see="All events",
  desc="Concerts, festivals, fairs, exhibitions, theatre, family shows and sport in Cyprus. Dates and prices come from the linked sources and are left out where a source does not give them.",
  city="City",kind="Type",all="All",source="Source",empty="No events match these filters.",
  cities=dict(nicosia="Nicosia",limassol="Limassol",larnaca="Larnaca",paphos="Paphos",**{"ayia-napa":"Ayia Napa & Protaras"},other="Towns & villages"),
  types=dict(theatre="Theatre",cinema="Cinema",concert="Concerts",festival="Festivals",fair="Fairs & markets",exhibition="Exhibitions",kids="For children",sport="Sport")),
 "ru":dict(title="Мероприятия",week="На этой неделе",upcoming="В ближайшие месяцы",later="Позже",see="Все события",
  desc="Концерты, фестивали, ярмарки, выставки, театр, семейные спектакли и спорт на Кипре. Даты и цены взяты из указанных источников и не дополняются, если источник их не называет.",
  city="Город",kind="Тип",all="Все",source="Источник",empty="Нет событий с таким фильтром.",
  cities=dict(nicosia="Никосия",limassol="Лимассол",larnaca="Ларнака",paphos="Пафос",**{"ayia-napa":"Айя-Напа и Протарас"},other="Города и деревни"),
  types=dict(theatre="Театр",cinema="Кино",concert="Концерты",festival="Фестивали",fair="Ярмарки",exhibition="Выставки",kids="Для детей",sport="Спорт")),
 "el":dict(title="Εκδηλώσεις",week="Αυτή την εβδομάδα",upcoming="Τους επόμενους μήνες",later="Αργότερα",see="Όλες οι εκδηλώσεις",
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
    obj={"@type":kind,"name":ev["title"][l],"startDate":ev["start"],"eventStatus":"https://schema.org/EventScheduled",
         "eventAttendanceMode":"https://schema.org/OfflineEventAttendanceMode",
         "location":{"@type":"Place","name":ev["venue"][l],"address":addr},
         "url":ev["url"],"description":ev["desc"][l],
         "organizer":{"@type":"Organization","name":ev["source"],"url":ev["url"]}}
    if ev.get("end"): obj["endDate"]=ev["end"]
    if ev.get("low"):
        obj["offers"]={"@type":"AggregateOffer","lowPrice":ev["low"],"highPrice":ev["high"],"priceCurrency":"EUR","url":ev["url"]}
    if ev.get("photo"):
        obj["image"]=abs_(f"/assets/img/events/{ev['photo']}-1200.webp")
    return obj
def ev_card(ev,l,u):
    if ev.get("photo"):
        ph=EV_PHOTOS[ev["photo"]]
        media=(f'<figure class="pic"><img src="{href(f"/assets/img/events/{ev["photo"]}-600.webp")}" '
               f'srcset="{href(f"/assets/img/events/{ev["photo"]}-600.webp")} 600w, {href(f"/assets/img/events/{ev["photo"]}-1200.webp")} 1200w" '
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
    h=head(l,f'{u["title"]} | {SITE}',u["desc"],[u["title"],"Cyprus",SITE],f"/{l}/events/",pathfn,"/assets/og-default.jpg",jsonld=[graph])
    h+=header(l,pathfn,"events")
    h+=f'<main id="main" class="wrap"><h1 class="sec">{e(u["title"])}</h1><p class="leadin" style="max-width:760px">{e(u["desc"])}</p>'
    h+=f'<div class="filters"><p>{e(u["city"])}</p>{cities}<p>{e(u["kind"])}</p>{kinds}</div>'
    h+=f'<p data-evempty hidden>{e(u["empty"])}</p>{groups}</main>'
    h+=script+footer(l)
    return h
def build_event_photos():
    d=OUT+"/assets/img/events"; os.makedirs(d,exist_ok=True)
    for key,p in EV_PHOTOS.items():
        im=Image.open(os.path.join(HERE,"photos",p["file"]))
        plain=cover_crop(im,1200,675,tuple(p.get("focus",(0.5,0.5))))
        watermark(plain).save(f"{d}/{key}-1200.webp","WEBP",quality=78,method=6)
        watermark(plain.resize((600,338),Image.LANCZOS)).save(f"{d}/{key}-600.webp","WEBP",quality=76,method=6)

def page_root():
    # language chooser = x-default
    alts="\n".join(f'<link rel="alternate" hreflang="{x}" href="{abs_(f"/{x}/")}">' for x in LANGS)+f'\n<link rel="alternate" hreflang="x-default" href="{abs_("/")}">'
    ld={"@context":"https://schema.org","@type":"WebSite","name":SITE,"url":abs_("/"),"inLanguage":LANGS}
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CyNews 24 – Cyprus News · Новости Кипра · Ειδήσεις Κύπρου</title>
<meta name="description" content="CyNews 24: Cyprus news in English, Russian and Greek. Новости Кипра на русском, английском и греческом. Ειδήσεις Κύπρου στα ελληνικά, αγγλικά και ρωσικά.">
<meta name="keywords" content="Cyprus news, Кипр новости, Κύπρος ειδήσεις, CyNews 24">
<meta name="robots" content="index,follow,max-image-preview:large"><link rel="canonical" href="{abs_("/")}">
{alts}
<meta property="og:site_name" content="{SITE}"><meta property="og:type" content="website"><meta property="og:title" content="CyNews 24 – Cyprus News · Новости Кипра · Ειδήσεις Κύπρου"><meta property="og:description" content="Cyprus news in English, Russian and Greek."><meta property="og:url" content="{abs_("/")}"><meta property="og:image" content="{abs_("/assets/og-default.jpg")}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="CyNews 24"><meta name="twitter:description" content="Cyprus news in English, Russian and Greek."><meta name="twitter:image" content="{abs_("/assets/og-default.jpg")}">
<link rel="icon" href="{href("/favicon.svg")}" type="image/svg+xml"><link rel="apple-touch-icon" href="{href("/apple-touch-icon.png")}"><meta name="theme-color" content="#111827"><link rel="stylesheet" href="{href("/assets/css/style.css")}">
<script type="application/ld+json">{json.dumps(ld)}</script></head>
<body class="choose-body"><main class="choose"><div><div class="logo"><b>CyNews</b><i>24</i></div><p>Cyprus news · Новости Кипра · Ειδήσεις Κύπρου</p>
<div class="btns"><a href="{href("/ru/")}" hreflang="ru" lang="ru">Русский</a><a href="{href("/en/")}" hreflang="en" lang="en">English</a><a href="{href("/el/")}" hreflang="el" lang="el">Ελληνικά</a></div></div></main>
<script>try{{var l=(navigator.language||"en").slice(0,2).toLowerCase();if(!/[?&]choose/.test(location.search)&&["ru","en","el"].indexOf(l)>-1&&!document.referrer.includes(location.host)){{location.replace("{href("/")}"+l+"/")}}}}catch(e){{}}</script>
<noscript></noscript></body></html>'''

def rss(l):
    items=sorted_all()
    x=['<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>',f'<title>{SITE} ({l.upper()})</title><link>{abs_(f"/{l}/")}</link><description>{e(HOME_D[l])}</description><language>{l}</language>']
    for s in items:
        dt=datetime.datetime.fromisoformat(s["date"]+"T09:00:00+02:00")
        x.append(f'<item><title>{e(s["title"][l])}</title><link>{abs_(f"/{l}/{s["slug"]}/")}</link><guid>{abs_(f"/{l}/{s["slug"]}/")}</guid><pubDate>{dt.strftime("%a, %d %b %Y %H:%M:%S +0200")}</pubDate><description>{e(s["lede"][l])}</description></item>')
    x.append('</channel></rss>'); return "".join(x)

def sitemap():
    def entry(pathfn,lastmod,prio):
        out=[]
        for l in LANGS:
            alts="".join(f'<xhtml:link rel="alternate" hreflang="{x}" href="{abs_(pathfn(x))}"/>' for x in LANGS)+f'<xhtml:link rel="alternate" hreflang="x-default" href="{abs_("/")}"/>'
            out.append(f'<url><loc>{abs_(pathfn(l))}</loc><lastmod>{lastmod}</lastmod><priority>{prio}</priority>{alts}</url>')
        return "".join(out)
    x=['<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
       f'<url><loc>{abs_("/")}</loc><lastmod>{TODAY}</lastmod><priority>0.5</priority>'+"".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{abs_(f"/{l}/")}"/>' for l in LANGS)+f'<xhtml:link rel="alternate" hreflang="x-default" href="{abs_("/")}"/></url>']
    x.append(entry(lambda l:f"/{l}/",TODAY,"1.0"))
    for c in CATS: x.append(entry(lambda l,c=c:f"/{l}/{c}/",TODAY,"0.7"))
    for s in STORIES: x.append(entry(lambda l,s=s:f"/{l}/{s['slug']}/",TODAY,"0.8"))
    x.append(entry(lambda l:f"/{l}/about/",TODAY,"0.3"))
    x.append(entry(lambda l:f"/{l}/advertising/",TODAY,"0.4"))
    x.append(entry(lambda l:f"/{l}/events/",TODAY,"0.6"))
    x.append('</urlset>'); return "".join(x)

def w(path,content):
    p=OUT+path; os.makedirs(os.path.dirname(p),exist_ok=True); open(p,"w",encoding="utf8").write(content)

def main():
    for d in ["ru","en","el","assets"]:
        shutil.rmtree(f"{OUT}/{d}",ignore_errors=True)
    os.makedirs(OUT+"/assets/css",exist_ok=True)
    build_assets()
    build_event_photos()
    w("/assets/css/style.css",CSS)
    w("/index.html",page_root())
    for l in LANGS:
        w(f"/{l}/index.html",page_home(l))
        for c in CATS: w(f"/{l}/{c}/index.html",page_cat(l,c))
        for s in STORIES: w(f"/{l}/{s['slug']}/index.html",page_article(l,s))
        w(f"/{l}/about/index.html",page_about(l))
        w(f"/{l}/events/index.html",page_events(l))
        w(f"/{l}/advertising/index.html",page_advertising(l))
        w(f"/{l}/advertising/thanks/index.html",page_ad_thanks(l))
        w(f"/{l}/feed.xml",rss(l))
    w("/sitemap.xml",sitemap())
    w("/robots.txt",f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n")
    w("/404.html",f'<!doctype html><meta charset="utf-8"><title>404 — {SITE}</title><meta name="robots" content="noindex"><link rel="stylesheet" href="{href("/assets/css/style.css")}"><main class="choose"><div><div class="logo"><b>CyNews</b><i>24</i></div><p>404 — Page not found · Страница не найдена · Η σελίδα δεν βρέθηκε</p><div class="btns"><a href="{href("/ru/")}">RU</a><a href="{href("/en/")}">EN</a><a href="{href("/el/")}">EL</a></div></div></main>')
    w("/_headers","/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n")
    open(os.path.join(OUT,".nojekyll"),"w").close()
    # Google Search Console verification. Rewritten on every build so a rebuild cannot drop it.
    w("/google62249645dc64d12b.html","google-site-verification: google62249645dc64d12b.html\n")
    write_credits_md()
    print("built",len(STORIES),"stories; BASE=",BASE,"; PREFIX=",PREFIX or "(root)","; OUT=",OUT,"; photos",sum(1 for s in STORIES if s["img"] in CREDITS))
main()
