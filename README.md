# Economic Analysis

Python data pipeline for fetching and normalizing U.S. economic datasets:

- BLS labor data: CPS labor force/employment measures and CES payroll employment.
- BEA consumer spending: Personal Consumption Expenditures by major type of product.
- Federal Reserve SCF: primary residence/home asset distributions by standard household groups.
- BEA GDP by industry: current-dollar and real/chained-dollar value added.

## Setup

```bash
make setup
```

BEA fetches require a BEA API key:

```bash
export BEA_API_KEY=your-key-here
```

BLS fetches work without a key for public limits. You can optionally export `BLS_API_KEY`.

## Usage

```bash
make dry-run-data
make download-data
```

`make download-data` fetches all configured datasets. BEA downloads require `BEA_API_KEY`
in the shell environment.

Raw responses are written to `data/raw/<source>/`. Normalized outputs are written to
`data/processed/<dataset>/` as both CSV and Parquet, with a metadata JSON sidecar.

## Development

```bash
make format
make lint
make typecheck
make test
make check
```

Live integration tests are intentionally opt-in:

```bash
RUN_INTEGRATION=1 BEA_API_KEY=your-key uv run pytest tests/test_integration.py
```
