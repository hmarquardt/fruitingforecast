# Fruiting Forecast

A deterministic, regional mushroom-fruiting and hunting-opportunity planner for the contiguous United States.

Fruiting Forecast combines weather, seasonality, mapped habitat, forest type and hosts, canopy, soils, terrain and elevation, fire history, public lands, mapped access, collecting-rule evidence, and recent observations into regional species opportunity and huntability information.

**It predicts opportunity.** It does not identify mushrooms or guarantee edibility, mushroom presence, collecting legality, or access. Verify identification with qualified local expertise and permission with the responsible land manager.

## Coverage and status

The current GIS release covers **922 / 922 normalized relevant CONUS tiles** with four layers per tile. Biology resolves to **13 regional profiles**: 11 `PROVISIONAL` and two `MODELED_SPARSE`. Provisional means explicit regional models that still need field validation; sparse means intentionally limited biological evidence and potentially no modeled target species. National mapped coverage is not proof of species presence or scientific validation of predicted scores.

Revision 19 launch QA: **READY WITH DOCUMENTED NON-BLOCKING ISSUES**. Most properties require collecting-rule verification; historical orphan accounting covers the publisher ledger rather than a full bucket listing; the slowest measured launch canary took 35.3 seconds cold. See [launch evidence](data/production/launch-qa-report.json) and [acceptance checklist](docs/fruiting-forecast-launch-acceptance.md).

| Component | Version |
| --- | --- |
| Standalone application | `2026.09.20.6` |
| Deterministic scoring model | `FF-1.7.0` |
| Immutable GIS dataset | `content-db0f839a4352ef82` |

The app-only increments from `.3` record entry-point/data-path normalization, removal of the Junk Drawer analytics dependency, canonical-domain metadata, and deployment-safe response headers. Biology, scoring, GIS and UI behavior remain unchanged.

## Architecture

**Static HTML/JavaScript + immutable Parquet object storage + DuckDB-Wasm in the browser.** There is no application server, Worker, VM, database server, bundler, or application build step. `index.html` loads compact local configuration; the manifest points to verified immutable objects at `https://data.hanksjunkdrawer.com/`. IndexedDB holds local records and caches. Weather and observations remain external mutable inputs; optional AI interpretation never replaces deterministic scores.

See [architecture](docs/architecture.md), [data reproduction](docs/data-build.md), and [deployment transition](docs/deployment.md).

## Run locally

From the repository root:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Open <http://localhost:8000/>. This port/origin is permitted by current R2 CORS. Internet access is needed for GIS, CDN libraries, weather and observations. File URLs support reduced functionality; use HTTP for DuckDB and GIS.

## Tests

Node is test tooling only. Install Chrome and the pinned test dependency:

```sh
npm ci
uv run --with pytest --with duckdb --with requests --with shapely --with pyproj --with rasterio --with osmium --with pyshp python3 -m pytest tests/test_fruiting_*.py -q
npm test
```

Production-data assertions require ignored local Parquet hydration. This downloads the existing release without rebuilding or uploading it (about 271 MB); it also verifies remote objects:

```sh
uv run tools/fruiting_remote.py hydrate --report /tmp/ff-hydrate.json
```

Hydrate before running the full browser suite or the Python release-data classes; unhydrated Python release classes explicitly skip. Tests cover biology, normalization, planner/runner invariants, publication, R2 integrity, failures/retries, access, filter recovery and browser behavior. Run `node tools/fruiting_launch_qa.js /tmp/ff-launch.json` against the local server for the 13-profile live GIS matrix with deterministic weather/observations. `FF_APP_URL` and `FF_APP_VERSION` can select the existing deployment. `node tools/fruiting_promotion_parity.js /tmp/ff-parity.json` compares source and standalone canaries using fixed mutable inputs.

## Data and attribution

Major sources: [EPA ecoregions](https://www.epa.gov/eco-research/ecoregions), [Census boundaries](https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.html), [USFS forest inventory](https://www.fia.fs.usda.gov/), [MRLC land cover and canopy](https://www.mrlc.gov/), [NRCS soils](https://sdmdataaccess.sc.egov.usda.gov/), [USGS 3DEP](https://www.usgs.gov/3d-elevation-program), [PAD-US](https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview), [MTBS fire history](https://www.mtbs.gov/), and [OpenStreetMap](https://www.openstreetmap.org/copyright) via [Geofabrik](https://download.geofabrik.de/). Mutable services include [Open-Meteo](https://open-meteo.com/) and [iNaturalist](https://www.inaturalist.org/). Individual provenance, dates and evidence status live in the manifest and biology research product. See [licensing and attribution](LICENSE.md).

## Deployment

The production application is <https://fruitingforecast.com/> on Cloudflare Pages. `www.fruitingforecast.com` permanently redirects to the apex while preserving the path and query string. GIS remains at the independent, immutable origin <https://data.hanksjunkdrawer.com/>. The previous [Junk Drawer deployment](https://hmarquardt.github.io/junkdrawer/fruiting-forecast.html) remains available as rollback/reference.

The deployment is a deterministic direct upload of a minimal runtime artifact. It does not publish tests, tools, internal reports, or source-only data:

```sh
python3 tools/stage_pages.py
npx wrangler pages deploy dist --project-name fruitingforecast --branch main --commit-hash "$(git rev-parse HEAD)" --commit-dirty=false
```

See the [deployment runbook](docs/deployment.md) and [domain deployment report](docs/domain-deployment-report.json). No secrets belong in this repository or deployment artifact.
