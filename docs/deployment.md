# Cloudflare Pages deployment

## Current production

- Application: <https://fruitingforecast.com/>
- Canonical redirect: `https://www.fruitingforecast.com/*` returns `301` to the matching apex path and query
- Immutable GIS: <https://data.hanksjunkdrawer.com/>
- Repository: <https://github.com/hmarquardt/fruitingforecast>
- Rollback/reference: <https://hmarquardt.github.io/junkdrawer/fruiting-forecast.html>

The application is a Cloudflare Pages Direct Upload project named `fruitingforecast`; its project hostname is `fruitingforecast.pages.dev` and production branch is `main`. Direct Upload was chosen because it publishes a deterministic allowlisted artifact without granting Cloudflare access to the GitHub repository. GitHub Actions is now the authoritative website release path: a push to `main` validates, stages the same allowlisted artifact, deploys it to the existing project, and verifies production. `tools/deploy_pages.py` remains the deliberate operator recovery path, not the normal release mechanism.

## GitHub Actions release path

`.github/workflows/production.yml` is the only automated publishing path. It uses the existing Cloudflare Pages project and the pinned Wrangler version already used by `tools/deploy_pages.py`; it does not create a second project, Git-integration build, or alternate hosting mechanism.

| Event | Validate | Deploy |
| --- | --- | --- |
| `pull_request` to `main` | Yes | Never |
| Push to `main` | Yes | Only after validation succeeds |
| Any other branch | No | Never |

The **Validate release candidate** job runs the deployment contract tests, stages the minimal artifact from `config/pages-runtime.json`, rejects source-only files, installs the pinned Playwright toolchain, and runs the application, hosting and analytics browser specs. The validated `dist/` directory is uploaded and passed to deployment, so the published bytes are the bytes that passed validation.

The **Deploy production** job is gated on `needs: validate` plus `github.event_name == 'push'` and `github.ref == 'refs/heads/main'`. It checks the artifact commit against `GITHUB_SHA`, publishes with

```sh
npx --yes wrangler@4.135.0 pages deploy dist \
  --project-name fruitingforecast \
  --branch main \
  --commit-hash "$GITHUB_SHA" \
  --commit-dirty=false
```

and then runs `tools/verify_pages_production.py` and `tools/fruiting_production_smoke.js`. Production verification evidence is retained as a workflow artifact for 30 days; the staged artifact is retained for 7 days. GitHub Actions pins every action by commit SHA, uses `npm ci` with the committed lockfile, and pins Python (`3.12`), Node (`24`), pytest, PyYAML and Wrangler.

### Required credentials

No Cloudflare credential belongs in this repository. The deployment job requires two repository secrets:

| Secret | Value | Scope |
| --- | --- | --- |
| `CLOUDFLARE_API_TOKEN` | API token created at **My Profile → API Tokens** | Account → **Cloudflare Pages: Edit** only |
| `CLOUDFLARE_ACCOUNT_ID` | Account ID from the Cloudflare dashboard or `npx wrangler whoami` | Not secret, stored as a secret for a single configuration surface |

Create the token as a **Custom Token** with Account resources limited to the Fruiting Forecast account. Do not grant Zone, DNS, R2, Workers, KV, D1, SSL or Page Rules permissions; this workflow only uploads static files to the existing Pages project. Set a rotation/expiry policy appropriate to the owner.

Owner setup:

```sh
gh secret set CLOUDFLARE_API_TOKEN --repo hmarquardt/fruitingforecast
gh secret set CLOUDFLARE_ACCOUNT_ID --repo hmarquardt/fruitingforecast
```

If either secret is absent or empty, the deployment job fails at **Require deployment credentials** with a `::error` annotation before Wrangler runs. Validation still completes; nothing is published and no credential is exposed. A red deployment job therefore means **not released**, even if validation passed.

### Release verification

After a successful deployment, confirm:

1. `https://fruitingforecast.com/deployment.json` reports the exact `GITHUB_SHA` and app version.
2. The apex serves HTTPS and the homepage canonical, Open Graph and `WebApplication` JSON-LD metadata.
3. `www.fruitingforecast.com` returns `301` to the apex with path and query preserved.
4. `/robots.txt` and `/sitemap.xml` return `200`; the sitemap is byte-identical to the committed artifact and robots.txt retains the canonical `Sitemap:` line. Cloudflare may prepend its zone-managed Content Signals block to an origin robots.txt; the origin file is still merged into the response.
5. `/data/manifest.json` matches the committed GIS dataset version and 922-tile roster, and a representative immutable R2 Parquet object verifies length, SHA-256 and CORS without any upload.

Run the same checks manually when needed:

```sh
python3 tools/verify_pages_production.py --expected-commit "$(git rev-parse HEAD)"
node tools/fruiting_production_smoke.js /tmp/ff-production-smoke.json
```

Heavyweight national GIS validation remains a separate operator task. The workflow deliberately does not rebuild the national data lake, rewrite Parquet, normalize GIS manifests, change scoring, or touch R2, CORS, DNS or custom-domain routing.

## Runtime artifact

`tools/stage_pages.py` validates the expected application, scoring, GIS, and origin identifiers, then recreates ignored `dist/` from `config/pages-runtime.json`. Only these source files are published:

- `index.html`
- `robots.txt`
- `sitemap.xml`
- `data/ecoregions.js`
- `data/states.js`
- `data/manifest.json`
- `data/public-land-rules.json`
- `data/tile-catalog.json`

The staging script also adds `_headers`, a safe `404.html`, and deployment metadata. It fails if the canonical link, Open Graph URL, `WebApplication` JSON-LD, robots `Sitemap:` line or sitemap location drift from `canonicalOrigin`. Tests, tools, source-only data, production journals, browser reports, and Git metadata are excluded. `_headers` applies `Cache-Control: public, no-transform, max-age=0, must-revalidate`; `no-transform` prevents zone-level HTML rewriting from injecting scripts into the application.

Stage and inspect locally:

```sh
python3 tools/stage_pages.py
find dist -type f -print | sort
python3 -m http.server 8000 --bind 127.0.0.1 --directory dist
```

## Manual recovery deployment

The normal release path is GitHub Actions. If Actions is unavailable or credentials must be recovered, an authenticated operator may deliberately publish from a clean `main` checkout using the existing mechanism. This bypasses the CI gate and must be recorded as a manual recovery.

```sh
python3 tools/deploy_pages.py
```

`tools/deploy_pages.py` stages the allowlisted artifact, refuses a dirty or non-`main` checkout, and runs the pinned Wrangler direct upload with the exact local commit:

```sh
npx wrangler@4.135.0 pages deploy dist \
  --project-name fruitingforecast \
  --branch main \
  --commit-hash "$(git rev-parse HEAD)" \
  --commit-dirty=false
```

No Cloudflare token belongs in the repository. Use Wrangler login or an environment/file excluded from Git. After any manual recovery, run `tools/verify_pages_production.py` and `tools/fruiting_production_smoke.js` and confirm that Actions uses the same project and branch again for the next release.

## Domains and redirect

The apex is attached as a Pages custom domain and has a proxied CNAME to `fruitingforecast.pages.dev`. Cloudflare manages the Pages certificate; Always Use HTTPS is enabled for the zone.

`www` uses a proxied placeholder record solely so Cloudflare can evaluate the zone redirect. The dynamic redirect rule is recorded in `config/www-redirect-rule.json`; it returns permanent status `301`, replaces the host with the apex, and preserves both request path and query string. It does not serve a second application copy.

Do not create a second Pages custom-domain binding for `www` unless the redirect design is intentionally replaced.

## Analytics

Fruiting Forecast is a first-class site on the separate, first-party **AI Small Biz Guru Analytics** service. This is not Google Analytics, Plausible, Cloudflare Web Analytics, or any third-party telemetry, and it is not proxied through the application.

| Item | Value |
| --- | --- |
| Service | <https://analytics.aismallbizguru.com/> |
| Client | <https://analytics.aismallbizguru.com/script.js> (canonical deferred snippet, `data-site`) |
| Collection | `POST https://analytics.aismallbizguru.com/collect` |
| Public site ID | `as_Puys7BZHNPEG5lHUysxjHO` |
| Registered domains | `fruitingforecast.com` (primary), `www.fruitingforecast.com` (alias) |
| Dashboard | <https://analytics.aismallbizguru.com/?site=fruiting-forecast> |

The deferred script tag lives in the `index.html` head and provides the page view plus the `window.cflabAnalytics.track` client. The only custom-event code is the small `ANALYTICS_EVENTS`/`trackFruitingEvent` block inside the inline application script: a fixed property allowlist is enforced there, so precise coordinates, user-entered location text, query payloads, GIS geometry, full URLs, OpenRouter content, and credentials cannot be sent by accident. Events are best-effort only; a blocked or failing analytics script never delays or breaks the app.

| Event | When | Coarse properties |
| --- | --- | --- |
| `forecast_run` | A forecast finishes successfully (run, refresh, or filter recovery) | `profile`, `focus`, `depth`, `radius`, `results` bucket, `gis` mode |
| `species_selected` | Species/focus control change or a ranking card is opened | `species`, `source` |
| `result_opened` | A property candidate or map sector is opened | `kind`, `rank`, `species`, coarse `actionability` |
| `map_interaction` | Explicit map layer change or overlay toggle | `action`, `value`, `enabled` |
| `outbound_resource` | A click on an external `http(s)` link | `host`, coarse `surface` |

The collector additionally derives coarse browser/OS/device, Cloudflare country/region, pathname, and referrer host; it never stores cookies, full IP addresses, raw User-Agent, query strings, or full referrer URLs. No event property contains latitude, longitude, GPS, or forecast query data.

Only the production domains are registered. Localhost, `fruitingforecast.pages.dev`, and preview URLs are intentionally unregistered: their collector requests are rejected with `403` and nothing is stored, so development, tests, CI, and previews cannot pollute production analytics. The Playwright suite and QA tools intercept `https://analytics.aismallbizguru.com/**` locally for the same reason. `www.fruitingforecast.com` is an alias registration only; the zone `301` redirect means requests normally execute on the apex.

Verify after a deployment (the accepted page-view call records a row under the site):

```sh
curl --fail --silent https://analytics.aismallbizguru.com/api/health
# 204: accepted; 403: origin validation rejected the caller.
curl -s -o /dev/null -w '%{http_code}\n' https://analytics.aismallbizguru.com/collect \
  -H 'Origin: https://fruitingforecast.com' -H 'Content-Type: application/json' \
  -d '{"site":"as_Puys7BZHNPEG5lHUysxjHO","kind":"pageview","name":"pageview","path":"/deploy-verification"}'
curl -s -o /dev/null -w '%{http_code}\n' https://analytics.aismallbizguru.com/collect \
  -H 'Origin: https://unrelated.example' -H 'Content-Type: application/json' \
  -d '{"site":"as_Puys7BZHNPEG5lHUysxjHO","kind":"pageview","name":"pageview","path":"/"}'
```

Then confirm page and event reporting in the dashboard (`?site=fruiting-forecast`, Events tab for `forecast_run`) and that no coordinate-shaped properties appear in recent activity.

## R2 CORS

The production bucket remains unchanged and continues to serve through `https://data.hanksjunkdrawer.com/`. Its CORS policy is recorded in `config/fruiting-forecast-r2-cors.json`. It permits the apex, `www`, the Pages project hostname, the existing Junk Drawer origins, and the supported local development origins. Existing behavior is preserved:

- methods: `GET`, `HEAD`
- allowed request header: `Range`
- exposed response headers: `Accept-Ranges`, `Content-Range`
- preflight cache: 3,600 seconds

After a policy change, verify `GET`, `HEAD`, byte-range `206`, `Content-Range`, `Accept-Ranges`, `Content-Length`, `ETag`, and browser access from the production origin. An R2 ETag is not a SHA-256 digest. Do not upload or rewrite Parquet for an application-domain deployment.

## Release validation

Every push and pull request runs the automated gate:

1. Deployment contract tests (`tests/test_pages_deployment.py`) verify allowlisting, SEO metadata, staging determinism, commit traceability, and workflow gating.
2. `tools/stage_pages.py` stages the minimal artifact and the job rejects any source-only file or directory.
3. Application, hosting-cache and analytics Playwright specs start the real application locally.
4. Production deployment then runs `tools/verify_pages_production.py` (commit identity, apex metadata, `www` redirect, robots/sitemap, headers, manifest and one immutable R2 object) and `tools/fruiting_production_smoke.js` (browser startup and GIS manifest/cache compatibility).

Heavyweight acceptance remains a separate, deliberate operator task rather than a per-website-change workflow step:

1. Confirm the Pages deployment metadata points to the intended clean commit.
2. Verify apex HTTPS and the `www` path/query redirect.
3. Run the 13-profile launch matrix on the apex with real app, manifest, R2, and DuckDB.
4. Run `tools/fruiting_domain_qa.js` for acceptance cases, mobile behavior, origin auditing, Suggested Start invariants, and bounded failure injection.
5. Compare deterministic local and production results under fixed mutable inputs.
6. Audit all 3,688 active GIS references without upload.
7. Verify the old Junk Drawer deployment still bootstraps and runs.

The detailed evidence and exact production identifiers are in `domain-deployment-report.json`.

## Rollback

Cloudflare Pages retains immutable deployments. Promote a previously accepted Pages deployment in the Pages project if an application rollback is required, then confirm `https://fruitingforecast.com/deployment.json` reports the restored commit and rerun the release verification. An ordinary rollback does not require a Git revert, a new artifact, or any R2/GIS change.

Because production deploys only on a push to `main`, a rollback made in the Cloudflare dashboard stays in place until the next validated push. If the rollback must be represented in Git, revert the offending commit on `main` so the next workflow run publishes the reverted tree. The old Junk Drawer URL is also retained as a reference during this transition. Rolling back the static application never requires modifying R2 objects, GIS manifests or the GIS hostname.
