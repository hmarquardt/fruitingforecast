# Search discovery — Fruiting Forecast

Canonical site: https://fruitingforecast.com/

## SEO foundation
- Homepage has a descriptive title, description, canonical and Open Graph metadata.
- A factual WebApplication JSON-LD block describes the public tool without making unsupported claims.
- `/robots.txt` permits crawlers and names `https://fruitingforecast.com/sitemap.xml`.
- `/sitemap.xml` lists only the canonical homepage; dynamic user-specific searches and private state are not indexable pages.
- The established staging process must include both crawler files.

## Release and owner verification
1. Run `python3 tools/stage_pages.py` and verify the built deployment contains `robots.txt`, `sitemap.xml`, and the updated `index.html`.
2. Direct upload with Wrangler is required to publish the staged artifact.
3. Once production deployment is confirmed, retrieve the homepage, `/robots.txt` and `/sitemap.xml` through the canonical hostname and confirm HTTP 200, correct contents, and expected canonical metadata.
4. In Google Search Console, verify the domain property and submit `https://fruitingforecast.com/sitemap.xml`; inspect the homepage using URL Inspection. Indexing is up to Google.

Avoid invented reviews, local-business addresses, guarantees of results, or additional tracking. Do not expose runtime data, private investigation state or source-only materials for indexing.
