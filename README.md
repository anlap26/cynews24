# CyNews 24

Trilingual Cyprus news site (Russian, English, Greek) at https://cynews24.net. Static HTML, CSS and images, served by GitHub Pages from branch `main`, folder `/ (root)`, with the custom domain in `CNAME`.

## Editing articles

- **In the browser:** https://cynews24.net/admin/ (Sveltia CMS, configured in `admin/config.yml`). Sign in with a GitHub fine-grained token that has *Contents: Read and write* on this repository.
- **By hand:** one JSON file per article in `source/content/articles/`. Russian (`ru`) is required; `en` and `el` are optional. A missing translation falls back to the Russian text and that language page is marked `noindex` until it is translated.
- The lead story and the four side stories on the home pages are set in `source/content/home.json`.
- Uploaded photos go to `source/src/`. The generator crops them to 16:9, resizes and watermarks them. Photos of the original articles are listed in `source/credits.json` and stored in `source/photos/`.

Article fields: `slug` (page address; empty = file name), `cat` (politics, economy, real-estate, society, tourism, sport, world), `date` (YYYY-MM-DD), `image` (uploaded photo) or `img` (credits.json key), `photo_credit`, `sources` (`name`, `url`), and per language `title`, `lede`, `body` (paragraphs separated by a blank line), `alt`, `kw`.

## Publishing

A push to `main` that touches `source/` starts the **Build site** workflow (`.github/workflows/build.yml`). It runs `source/build.py` with `BASE=https://cynews24.net` and commits the generated pages to `main`. Pages keeps serving `main` / root, with the custom domain in `CNAME`. That push already starts a Pages build. A commit the workflow itself pushes does not, so the workflow requests a Pages build after its own commit, and also on the daily and manual runs. The workflow runs daily so the date in the header, the events of the week and the sitemaps stay current, and on pull requests as a check.

## Rebuild locally

From `source/` (Python 3 and Pillow, DejaVu fonts):

```bash
pip install -r requirements.txt
BASE=https://cynews24.net python3 build.py
```

`TODAY=YYYY-MM-DD` overrides the site date (default: today in Cyprus). `OUT` writes the site somewhere other than the repository root.
