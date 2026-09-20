# Next pass: fruitingforecast.com

1. Inspect GitHub repository settings and delegated DNS; select the static host explicitly. The promotion pass has not enabled Pages, created a Cloudflare Pages project, or configured apex/www records.
2. Deploy standalone `main` with root `index.html`, no application build. Retain `data.hanksjunkdrawer.com` as the GIS origin.
3. Configure TLS and `fruitingforecast.com`; decide whether www redirects to apex or also serves the app.
4. Append `https://fruitingforecast.com` and, if serving the application there, `https://www.fruitingforecast.com` to the existing R2 allowed origins. Preserve all current origins, GET/HEAD, Range and exposed response headers. Do not replace unrelated rules.
5. Run the acceptance checklist and launch QA against the actual domain; test cold and warm caches, DuckDB, all four GIS layers, mobile, filter recovery and errors. Confirm no app-local 404s and compare deterministic scores with the promotion report.
6. Decide separately whether a GIS hostname migration is worthwhile. No national rebuild or R2 object rewrite is required.
7. Keep the old Junk Drawer application live as rollback/reference; only change compatibility behavior after the new deployment is accepted.

Outstanding operator decisions: static hosting choice, apex/www behavior, and eventual old-URL policy. Licensing is currently unspecified for original code; choose an explicit license before claiming open-source redistribution rights. No credentials should be added to Git.
