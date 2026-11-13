# CyNews 24

Trilingual Cyprus news site (Russian, English, Greek). Static HTML, CSS and images.

Intended URL: https://anlap26.github.io/cynews24/

The built site is on the `main` branch at the repository root, including `.nojekyll`. Canonical, hreflang, Open Graph, JSON-LD, sitemap and RSS URLs use `https://anlap26.github.io/cynews24`. Internal links, stylesheets and images are prefixed with `/cynews24/` so they work on the GitHub Pages project path.

## Enable GitHub Pages

This repository's automation token cannot change Pages settings (`POST /repos/anlap26/cynews24/pages` returns 403). Turn it on once:

1. Open [Settings → Pages](https://github.com/anlap26/cynews24/settings/pages).
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Set **Branch** to `main` and the folder to **`/ (root)`**.
4. Save.

GitHub then publishes this branch to https://anlap26.github.io/cynews24/ (usually within a few minutes). `robots.txt` points at https://anlap26.github.io/cynews24/sitemap.xml.

The generator in `source/` is part of the repository, so it is also reachable under `/cynews24/source/` when Pages serves the branch root. The site does not link to it.

## Rebuild

From `source/` (Python 3 and Pillow):

```bash
pip install -r requirements.txt
BASE=https://anlap26.github.io/cynews24 python3 build.py
```

`BASE` is the public origin, including `/cynews24` when the site is a project page. The generator uses that path as the prefix for root-relative links. Set `PREFIX` only to override it (`PREFIX=` keeps links at the domain root). Set `OUT` to write the site somewhere other than the repository root.
