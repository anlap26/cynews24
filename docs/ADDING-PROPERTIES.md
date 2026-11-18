# Adding a property listing

Listings on the Real Estate pages (`/ru/real-estate/`, `/en/real-estate/`, `/el/real-estate/`) are read from `data/properties.json`. The generator builds a card for each published entry and a page in Russian, English and Greek at `/{lang}/real-estate/{id}/`.

News articles in the same section are separate. They stay in `source/content/articles/` with `"cat": "real-estate"`. A listing is a home or a development with a price, not a news story.

## Publish a listing

1. Copy the object whose `id` is `example-limassol-apartment`, or add a new object to the `listings` array.
2. Set a new `id`: lowercase Latin letters, digits and hyphens only. It becomes the page address.
3. Set `"published": true`. Leave `"status"` as `available`, `under construction` or `sold`. The value `example` is never shown, even if `published` is true.
4. Fill `title`, `city`, `area` and `description` in `ru`, `en` and `el`.
5. Set `type` to one of `project`, `apartment`, `villa`, `house`, `land`, `office`.
6. Set `price` in euros (a number). `"price_from": true` prints “from” in front of the price.
7. Set `bedrooms` and `area_m2` as numbers. Use `null` when the figure does not apply (for example a plot with no bedrooms).
8. Put photographs in `images/properties/{id}/` and list the paths in `photos`, for example `images/properties/limassol-tower/cover.jpg`. The first photo is the card image. JPEG or PNG.
9. Contact details sit once, at the top of the file: `email` (info@cynews24.net), optional `whatsapp` (international digits, no plus, spaces or dashes) and `path` (the advertising and contact page, `/advertising/`). A listing may override them with its own `contact` object.

Rebuild from `source/`:

```bash
BASE=https://cynews24.net python3 build.py
```

A push to `main` that changes `source/` or `data/properties.json` runs the same build on GitHub.

## Empty section

If every listing has `"published": false`, or the only entry is the example, the Real Estate page shows a short note that no listings are published yet. The example page is not generated and is not added to `sitemap.xml`.

## Fields

| Field | Meaning |
|---|---|
| `id` | Page address. Unique. |
| `published` | `true` shows the card, the page and the sitemap URL. |
| `type` | `project`, `apartment`, `villa`, `house`, `land` or `office`. |
| `status` | `available`, `under construction`, `sold`, or `example` for the sample. |
| `city`, `area` | Place, in all three languages. |
| `price` | Euros. |
| `price_from` | Optional. `true` means the price is a starting price. |
| `bedrooms` | Number, or `null`. |
| `area_m2` | Floor or plot area in square metres, or `null`. |
| `title`, `description` | Text in `ru`, `en` and `el`. |
| `photos` | Paths under `images/properties/{id}/`. |
| `contact` | Optional override of email, WhatsApp and the contact path. |
