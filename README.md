# CyNews 24

Trilingual Cyprus news site (Russian, English, Greek) at https://cynews24.net. Static HTML, CSS and images, served by GitHub Pages from branch `main`, folder `/ (root)`, with the custom domain in `CNAME`.

## Editing articles

- **In the browser:** https://cynews24.net/admin/ (Sveltia CMS, configured in `admin/config.yml`). Sign in with a GitHub fine-grained token that has *Contents: Read and write* on this repository.
- **By hand:** one JSON file per article in `source/content/articles/`. Russian (`ru`) is required; `en` and `el` are optional. A missing translation falls back to the Russian text and that language page is marked `noindex` until it is translated.
- The lead story and the four side stories on the home pages are set in `source/content/home.json`.
- Uploaded photos go to `source/src/`. The generator crops them to 16:9, resizes and watermarks them. Photos of the original articles are listed in `source/credits.json` and stored in `source/photos/`.

Article fields: `slug` (page address; empty = file name), `cat` (politics, economy, real-estate, society, tourism, sport, world), `date` (YYYY-MM-DD), `image` (uploaded photo) or `img` (credits.json key), `photo_credit`, `sources` (`name`, `url`), and per language `title`, `lede`, `body` (paragraphs separated by a blank line), `alt`, `kw`.

## Publishing

A push to `main` that touches `source/` starts the **Build site** workflow (`.github/workflows/build.yml`). It runs `source/build.py` with `BASE=https://cynews24.net` and commits the generated pages to `main`. Pages keeps serving `main` / root, with the custom domain in `CNAME`. That push already starts a Pages build. A commit the workflow itself pushes does not, so the workflow requests a Pages build after its own commit, and also on the daily and manual runs. The workflow runs daily so the date in the header, the events of the week and the sitemaps stay current, and on pull requests as a check. A commit that only updates `source/content/telegram-posted.json`, `source/content/telegram-digest.json` or `source/content/facebook-posted.json` does not start a rebuild.

## Telegram

After **Build site** succeeds on `main`, **Post to Telegram** (`.github/workflows/telegram.yml`) publishes each new article once:

- Russian text goes to [@cynews24](https://t.me/cynews24) and links to `/ru/…`.
- English text goes to [@cynews24en](https://t.me/cynews24en) and links to `/en/…`. If the article has no English translation yet, that channel is skipped until a translation is added.

The bot token is the repository secret `TELEGRAM_BOT_TOKEN` (`@Cynews24_poster_bot`). If the secret is missing, the job logs a notice and stays green, and it does not update the state file. Adding the secret does not by itself start a run: publish an article, wait for the daily rebuild, or run **Post to Telegram** manually.

Slugs already sent are stored in `source/content/telegram-posted.json` (Russian and English separately). Editing an article does not post it again. An article, or a late English translation, first seen more than 3 days after its publication date is recorded without posting. The poster waits until the article URL returns HTTP 200 and the live page contains that language's title, so Telegram can build the link preview from the deployed page.

Run the workflow manually with **dry run** checked to print the messages. A dry run does not send anything.

**Telegram evening digest** (`.github/workflows/telegram-digest.yml`) runs every day at 20:00 Asia/Nicosia, using the UTC cron `0 18 * * *` (Cyprus is UTC+2 in winter). It posts one message to [@cynews24](https://t.me/cynews24) in Russian and one to [@cynews24en](https://t.me/cynews24en) in English. Each message is that day's headlines, numbered and linked to the live article in that language, plus a closing line with the site link. Articles with no English translation are left out of the English digest. A day with no articles sends nothing.

Dates already sent are stored in `source/content/telegram-digest.json`, separately for each channel, and the workflow commits that file back. A re-run does not post a digest that was already sent. The same `TELEGRAM_BOT_TOKEN` secret is used and is never printed. If the secret is missing, the job logs a notice and stays green, and it does not update the state file. Run the workflow manually with **dry run** checked to print the messages. An optional date input (`YYYY-MM-DD`) previews or sends another Asia/Nicosia day; leave it empty to use today.

## Facebook

After **Build site** succeeds on `main`, **Post to Facebook** (`.github/workflows/facebook.yml`) publishes each new article once to the CyNews24 Facebook Page. The language is `FB_POST_LANG` in that workflow (default `en`): the link is the live `/en/…` article, and the message is the English title, a one- or two-sentence lead, and hashtags such as `#Cyprus` and `#CyprusNews`. Change `FB_POST_LANG` to `ru` or `el` to use that language for articles that have not been posted yet. Facebook builds the link preview from the page's Open Graph tags (`og:title`, `og:description`, `og:image` at 1200×630), which every article page already includes.

The Page token and Page id are the repository secrets `FB_PAGE_TOKEN` and `FB_PAGE_ID`. If the token is missing, the job logs a notice and stays green, and it does not update the state file. Adding the secret does not by itself start a run: publish an article, wait for the daily rebuild, or run **Post to Facebook** manually.

Slugs already sent are stored in `source/content/facebook-posted.json`. Editing an article does not post it again. An article first seen more than 3 days after its publication date is recorded without posting. A run posts at most 10 articles and pauses briefly between posts. The poster waits until the article URL returns HTTP 200 and the live page contains that language's title and Open Graph tags, so Facebook can build the preview from the deployed page.

Run the workflow manually with **dry run** checked to print the messages and to confirm the Page is reachable. A dry run does not publish anything.

## Rebuild locally

From `source/` (Python 3 and Pillow, DejaVu fonts):

```bash
pip install -r requirements.txt
BASE=https://cynews24.net python3 build.py
```

`TODAY=YYYY-MM-DD` overrides the site date (default: today in Cyprus). `OUT` writes the site somewhere other than the repository root.
