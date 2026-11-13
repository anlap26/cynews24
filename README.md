# CyNews 24

Trilingual Cyprus news site (Russian, English, Greek). Static HTML, CSS and images.

Intended URL: https://anlap26.github.io/cynews24/

The built site is on the `main` branch at the repository root, including `.nojekyll`. Canonical, hreflang, Open Graph, JSON-LD, sitemap and RSS URLs use `https://anlap26.github.io/cynews24`. Internal links, stylesheets and images are prefixed with `/cynews24/` so they work on the GitHub Pages project path.

## GitHub Pages

The site is published from branch `main`, folder `/ (root)`, at https://anlap26.github.io/cynews24/. `robots.txt` points at https://anlap26.github.io/cynews24/sitemap.xml. A push to `main` starts a new Pages build.

The generator in `source/` is part of the repository, so it is also reachable under `/cynews24/source/` when Pages serves the branch root. The site does not link to it.

Story photographs are openly licensed (CC0, CC BY, CC BY-SA) and listed in [CREDITS.md](CREDITS.md). `source/credits.json` and `source/photos/` are what `build.py` uses, so the next rebuild keeps the same pictures, captions and watermark.

## Rebuild

From `source/` (Python 3 and Pillow):

```bash
pip install -r requirements.txt
BASE=https://anlap26.github.io/cynews24 python3 build.py
```

`BASE` is the public origin, including `/cynews24` when the site is a project page. The generator uses that path as the prefix for root-relative links. Set `PREFIX` only to override it (`PREFIX=` keeps links at the domain root). Set `OUT` to write the site somewhere other than the repository root.
