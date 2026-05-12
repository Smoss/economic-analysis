# Agent Guidance

This repository is a reproducible economic data pipeline. Future agents should preserve repeatability and avoid one-off data handling.

## Required Data Rule

Any downloaded data must be fetched through a repeatable Python fetcher in the repo's pipeline.

- Do not use `curl`, browser downloads, ad hoc shell commands, or one-off scripts to fetch source data.
- New data may be requested when needed, but add or update a Python fetcher before relying on it.
- Store raw source files under `data/raw/<source>/`.
- Store normalized outputs under `data/processed/<dataset>/` with CSV, Parquet, and metadata sidecars when following existing dataset conventions.
- Metadata should include source URL, fetch time, raw paths, frequency, units, and method.
- If data is missing, update the fetcher and tests, then regenerate outputs through the pipeline.

## Analysis Reference

Before extending the labor, GDP, PCE, CEX, or debt/saving analysis, read:

- `docs/analysis-reference.md`

That note documents the generated artifacts, formulas, caveats, and the manual-download audit exception from prior exploration.

## Working Notes

- Prefer existing source modules under `economic_analysis/sources/` and pipeline wiring in `economic_analysis/pipeline.py`.
- Keep generated charts and intermediate analysis outputs under `outputs/`.
- Do not treat manually downloaded files as precedent; make them reproducible through Python fetchers.
- Run tests after code or pipeline changes. Docs-only changes should at least verify referenced paths and markdown readability.
