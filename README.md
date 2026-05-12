# Economic Analysis

Python data pipeline for fetching and normalizing U.S. economic datasets:

- BLS labor data: CPS labor force/employment measures and CES payroll employment.
- BLS Consumer Expenditure Surveys: annual aggregate spending by income quintile.
- BEA consumer spending: Personal Consumption Expenditures by major type of product.
- Federal Reserve SCF: primary residence/home asset distributions by standard household groups.
- BEA GDP by industry: current-dollar and real/chained-dollar value added.
- BEA GDP components: consumer spending, investment, government spending, exports, and imports.
- NOAA/NWS forecast accuracy: Northeast airport-station NDFD forecasts compared with daily station observations.

## Setup

```bash
make setup
```

BEA fetches require a BEA API key:

```bash
export BEA_API_KEY=your-key-here
```

BLS fetches work without a key for public limits. You can optionally export `BLS_API_KEY`.
NOAA daily station observations require a CDO token. NDFD live fetches expect a repeatable
point-extracted CSV URL generated from the NCEI NDFD GRIB-2 archive:

```bash
export NOAA_CDO_TOKEN=your-token-here
export NOAA_NDFD_FORECAST_CSV_URL=https://example.org/reproducible-ndfd-point-extract.csv
```

## Usage

```bash
make dry-run-data
make download-data
uv run python -m economic_analysis fetch noaa-ndfd-forecasts
uv run python -m economic_analysis fetch noaa-station-observations
uv run python -m economic_analysis fetch nws-forecast-accuracy
```

`make download-data` fetches all configured datasets. BEA downloads require `BEA_API_KEY`
in the shell environment.

Raw responses are written to `data/raw/<source>/`. Normalized outputs are written to
`data/processed/<dataset>/` as both CSV and Parquet, with a metadata JSON sidecar.
The GDP components dataset stores exports and imports separately; trade balance can be
computed downstream as exports minus imports.

Future-agent analysis notes and reproducibility guidance are in
[`docs/analysis-reference.md`](docs/analysis-reference.md).

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
