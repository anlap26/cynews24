# CyNews 24

Trilingual Cyprus news site (Russian, English, Greek) at https://cynews24.net. Static HTML, CSS and images, served by GitHub Pages from branch `main`, folder `/ (root)`, with the custom domain in `CNAME`.

## Editing articles

- **In the browser:** https://cynews24.net/admin/ (Sveltia CMS, configured in `admin/config.yml`). Sign in with a GitHub fine-grained token that has *Contents: Read and write* on this repository.
- **By hand:** one JSON file per article in `source/content/articles/`. Russian (`ru`) is required; `en` and `el` are optional. A missing translation falls back to the Russian text and that language page is marked `noindex` until it is translated.
- The lead story and the four side stories on the home pages are set in `source/content/home.json`.
- Uploaded photos go to `source/src/`. The generator crops them to 16:9, resizes and watermarks them. Photos of the original articles are listed in `source/credits.json` and stored in `source/photos/`.

Article fields: `slug` (page address; empty = file name), `cat` (politics, economy, real-estate, society, tourism, sport, world), `date` (YYYY-MM-DD), `image` (uploaded photo) or `img` (credits.json key), `photo_credit`, `sources` (`name`, `url`), and per language `title`, `lede`, `body` (paragraphs separated by a blank line), `alt`, `kw`.

## Publishing

A push to `main` that touches `source/` starts the **Build site** workflow (`.github/workflows/build.yml`). It runs `source/build.py` with `BASE=https://cynews24.net` and commits the generated pages to `main`. Pages keeps serving `main` / root, with the custom domain in `CNAME`. That push already starts a Pages build. A commit the workflow itself pushes does not, so the workflow requests a Pages build after its own commit, and also on the daily and manual runs. The workflow runs daily so the date in the header, the events of the week and the sitemaps stay current, and on pull requests as a check. A commit that only updates `source/content/telegram-posted.json` does not start a rebuild.

## Telegram

After **Build site** succeeds on `main`, **Post to Telegram** (`.github/workflows/telegram.yml`) publishes each new article once:

- Russian text goes to [@cynews24](https://t.me/cynews24) and links to `/ru/…`.
- English text goes to [@cynews24en](https://t.me/cynews24en) and links to `/en/…`. If the article has no English translation yet, that channel is skipped until a translation is added.

The bot token is the repository secret `TELEGRAM_BOT_TOKEN` (`@Cynews24_poster_bot`). If the secret is missing, the job logs a notice and stays green, and it does not update the state file. Adding the secret does not by itself start a run: publish an article, wait for the daily rebuild, or run **Post to Telegram** manually.

Slugs already sent are stored in `source/content/telegram-posted.json` (Russian and English separately). Editing an article does not post it again. An article, or a late English translation, first seen more than 3 days after its publication date is recorded without posting. The poster waits until the article URL returns HTTP 200 and the live page contains that language's title, so Telegram can build the link preview from the deployed page.

Run the workflow manually with **dry run** checked to print the messages. A dry run does not send anything.

## Rebuild locally

From `source/` (Python 3 and Pillow, DejaVu fonts):

```bash
pip install -r requirements.txt
BASE=https://cynews24.net python3 build.py
```

`TODAY=YYYY-MM-DD` overrides the site date (default: today in Cyprus). `OUT` writes the site somewhere other than the repository root.
