# Fruiting Forecast contributor guide

Static-first: `index.html`, compact configuration in `data/`, Python data tools, Playwright/Python tests. No runtime npm dependency or backend. Read README and docs/data-build.md before GIS operations.

Preserve separate app, scoring and GIS versions. Bump the app footer for committed HTML changes using YYYY.MM.DD.N; extraction app version is 2026.09.20.4. There is no Junk Drawer registry in this standalone repository. Never change biology, profile mapping, weights, access or collecting semantics during infrastructure work.

Never commit secrets, Parquet, raw rasters/PBFs, source caches or browser profiles. Test hydration is ignored. Keep user records in IndexedDB, bounded preferences in guarded localStorage. Keep optional AI separate from deterministic scores.

Production uploads, manifest normalization and domain/CORS mutations need an explicit task scope. Read-only verification is preferred. Run relevant Python and Chrome Playwright tests; preserve current production and record accurate evidence. See docs/domain-deployment-handoff.md for the separate domain migration.
