# Cloudflare Pages deployment

## Current production

- Application: <https://fruitingforecast.com/>
- Canonical redirect: `https://www.fruitingforecast.com/*` returns `301` to the matching apex path and query
- Immutable GIS: <https://data.hanksjunkdrawer.com/>
- Repository: <https://github.com/hmarquardt/fruitingforecast>
- Rollback/reference: <https://hmarquardt.github.io/junkdrawer/fruiting-forecast.html>

The application is a Cloudflare Pages Direct Upload project named `fruitingforecast`; its project hostname is `fruitingforecast.pages.dev` and production branch is `main`. Direct Upload was chosen because it publishes a deterministic allowlisted artifact without granting Cloudflare access to the GitHub repository or adding a CI workflow. A deployment remains an explicit operator action after `main` changes.

## Runtime artifact

`tools/stage_pages.py` validates the expected application, scoring, GIS, and origin identifiers, then recreates ignored `dist/` from `config/pages-runtime.json`. Only these source files are published:

- `index.html`
- `data/ecoregions.js`
- `data/states.js`
- `data/manifest.json`
- `data/public-land-rules.json`
- `data/tile-catalog.json`

The staging script also adds `_headers`, a safe `404.html`, and deployment metadata. Tests, tools, source-only data, production journals, browser reports, and Git metadata are excluded. `_headers` applies `Cache-Control: public, no-transform, max-age=0, must-revalidate`; `no-transform` prevents zone-level HTML rewriting from injecting scripts into the application.

Stage and inspect locally:

```sh
python3 tools/stage_pages.py
find dist -type f -print | sort
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist
```

Deploy the clean `main` candidate with authenticated Wrangler:

```sh
npx wrangler pages deploy dist \
  --project-name fruitingforecast \
  --branch main \
  --commit-hash "$(git rev-parse HEAD)" \
  --commit-dirty=false
```

`tools/deploy_pages.py` performs the staging and Wrangler call together and refuses a dirty checkout by default:

```sh
python3 tools/deploy_pages.py
```

No Cloudflare token belongs in the repository. Use Wrangler login or a local environment/file excluded from Git.

## Domains and redirect

The apex is attached as a Pages custom domain and has a proxied CNAME to `fruitingforecast.pages.dev`. Cloudflare manages the Pages certificate; Always Use HTTPS is enabled for the zone.

`www` uses a proxied placeholder record solely so Cloudflare can evaluate the zone redirect. The dynamic redirect rule is recorded in `config/www-redirect-rule.json`; it returns permanent status `301`, replaces the host with the apex, and preserves both request path and query string. It does not serve a second application copy.

Do not create a second Pages custom-domain binding for `www` unless the redirect design is intentionally replaced.

## R2 CORS

The production bucket remains unchanged and continues to serve through `https://data.hanksjunkdrawer.com/`. Its CORS policy is recorded in `config/fruiting-forecast-r2-cors.json`. It permits the apex, `www`, the Pages project hostname, the existing Junk Drawer origins, and the supported local development origins. Existing behavior is preserved:

- methods: `GET`, `HEAD`
- allowed request header: `Range`
- exposed response headers: `Accept-Ranges`, `Content-Range`
- preflight cache: 3,600 seconds

After a policy change, verify `GET`, `HEAD`, byte-range `206`, `Content-Range`, `Accept-Ranges`, `Content-Length`, `ETag`, and browser access from the production origin. An R2 ETag is not a SHA-256 digest. Do not upload or rewrite Parquet for an application-domain deployment.

## Release validation

Before accepting a deployment:

1. Confirm the Pages deployment metadata points to the intended clean commit.
2. Verify apex HTTPS and the `www` path/query redirect.
3. Run the 13-profile launch matrix on the apex with real app, manifest, R2, and DuckDB.
4. Run `tools/fruiting_domain_qa.js` for acceptance cases, mobile behavior, origin auditing, Suggested Start invariants, and bounded failure injection.
5. Compare deterministic local and production results under fixed mutable inputs.
6. Audit all 3,688 active GIS references without upload.
7. Verify the old Junk Drawer deployment still bootstraps and runs.

The detailed evidence and exact production identifiers are in `domain-deployment-report.json`.

## Rollback

Cloudflare Pages retains immutable deployments. Promote a previously accepted Pages deployment if an application rollback is required. The old Junk Drawer URL is also retained as a reference during this transition. Rolling back the static application does not require modifying R2 objects or the GIS hostname.
