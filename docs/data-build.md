# Data reproduction and operations

The current release is already built and verified. Repository promotion does not require regeneration or publication. Start by reading the manifest, normalization report, source pins in `tools/fruiting_bulk_adapters.py`, and the original [CONUS handoff](fruiting-forecast-conus-expansion.md).

## Inputs and preparation

Required caches depend on the selected state/tile: pinned forest-type rasters, NLCD land cover, canopy, state boundaries, NRCS soils, USGS elevation, PAD-US public lands, MTBS fire evidence and state OpenStreetMap extracts. Source-cache metadata records upstream versions/digests and preparation status. The existing optional soil package adapters accept gNATSGO GeoPackage/SQLite; cached hosted-service responses can avoid repeat queries. Optional cache availability is not permission to fabricate missing evidence. A cache miss may require a large download; keep caches outside Git and budget disk space before preparation.

`fruiting_bulk_adapters.py` prepares/samples federal source products; `fruiting_osm_access.py prepare` prepares a state extract and `build` clips access evidence. `fruiting_pnw_release.py` and `fruiting_batch2.py` orchestrate state preparation and bounded tile execution; the latter also supports derived national scopes. Historical batch/revision tools remain for reproducibility, not as instructions to resume completed production.

## Operational sequence

1. Inspect current source pins, state-prep metadata and normalized relevance. Use each tool's `--help` and planner/dry-run mode before execution.
2. Prepare only the authorized state source caches, outside the checkout.
3. Produce bounded normalized tile layers and provenance sidecars in a scratch output directory. Do not point experiments at `data/`.
4. Validate schemas, units, jurisdictions, source status, row counts and digests. Publisher tests enforce idempotence and failure recovery.
5. **PRODUCTION MUTATION:** `fruiting_tile_publish.py` publication and runner production execution may upload immutable objects and change the app manifest. `fruiting_remote.py migrate` uploads missing objects to the live R2 bucket. These require a separately reviewed release scope; they are not extraction commands.
6. Verify every published object by public GET against its expected length and SHA-256. Commit/deploy the manifest only after verification. A successful upload alone is insufficient.
7. **MANIFEST MUTATION:** `fruiting_manifest_normalize.py` can remove obsolete references/update manifest normalization. Do not rerun it casually; preserve `content-db0f839a4352ef82` until an explicitly approved data release.

Read-only checks (apart from local reports/cache/lock files):

```sh
uv run tools/fruiting_remote.py audit --report /tmp/ff-remote-audit.json
uv run tools/fruiting_remote.py hydrate --report /tmp/ff-hydrate.json
```

`audit` downloads all active objects and checks full bytes/digests. `hydrate` additionally saves ignored local copies for release-data tests. Neither uploads; both can be lengthy. Audit orphan coverage is limited to an available publisher inventory, not exhaustive bucket enumeration. This checkout intentionally excludes that local ledger.

## Artifact policy

A — Permanent provenance: biology research, pinned relevance, national normalization report, manifest, geometry and source contracts.

B — Release state: launch QA, remote audit, national storage stats and manifest normalization, retained under `data/production/`. These are dated snapshots, not claims of continuous monitoring.

C — Historical evidence: compact batch scope/final reports and state-prep metadata retained in the same directory for existing report-tool compatibility and clearly labeled by batch/revision. Historical paths/SHAs in those reports describe their original executions.

D — Excluded: repetitive chunk checkpoints, journals, JSONL metrics, temporary run state, raw caches and Parquet. Originals remain in Junk Drawer. Exact retained/excluded paths are in `extraction-inventory.json`; the 167 historical commits retain useful product evolution without unrelated projects.
