# Deployment transition

Current proven application: https://hmarquardt.github.io/junkdrawer/fruiting-forecast.html

Current immutable GIS origin: https://data.hanksjunkdrawer.com/

Future primary domain: https://fruitingforecast.com/

This promotion does not deploy the future domain or configure a host. DNS delegation alone does not establish application hosting. There is no CNAME file or deployment workflow that silently activates that domain.

Serve `index.html`, `data/` and app-local assets from a static host; no build command is required. Keep immutable Parquet outside the repository. App HTML and manifest need normal revalidation; Parquet uses long-lived immutable caching. The application verifies object lengths/digests and runs DuckDB-Wasm in the browser. Verify host CSP/CDN worker behavior and MIME types with the live canary suite before launch.

Live R2 CORS read on 2026-09-20 allows GET/HEAD with Range from hanksjunkdrawer.com, www.hanksjunkdrawer.com, hmarquardt.github.io, localhost:8000 and 127.0.0.1:8000. It does **not** allow fruitingforecast.com or www.fruitingforecast.com. The checked-in CORS JSON records current state; no production rule was changed.

The next pass must choose static hosting, deploy the standalone repo, attach apex/optional www, and append the selected origins to R2 CORS while preserving existing origins. Keep `https://data.hanksjunkdrawer.com/` initially. A later GIS-hostname change is a separate migration. Keep the Junk Drawer URL functional until the new domain is verified; decide its long-term compatibility behavior afterward.
