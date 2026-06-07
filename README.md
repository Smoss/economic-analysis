# Economic Analysis

Python data pipeline for fetching and normalizing U.S. economic datasets:

- BLS labor data: CPS labor force/employment measures and CES payroll employment.
- BLS OEWS occupational employment: all occupations and harmonized software-developer employment.
- BLS Consumer Expenditure Surveys: annual aggregate spending by income quintile.
- BEA consumer spending: Personal Consumption Expenditures by major type of product.
- Federal Reserve SCF: primary residence/home asset distributions by standard household groups.
- Census ACS PUMS: national employment rates by college major for recent graduates, 2015-2024.
- FRED SWE labor market data: software-developer employment, broader computer/math employment proxy, and Indeed job-postings indexes.
- FRED Indeed job-postings data: current U.S. sector/occupation indexes and selected state indexes.
- FRED oil and gasoline prices: WTI crude and U.S. regular gasoline for oil-price scenario models.
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
uv run python -m economic_analysis fetch acs-major-employment
uv run python -m economic_analysis fetch fred-swe-labor-market
uv run python -m economic_analysis fetch fred-indeed-job-postings
uv run python -m economic_analysis fetch fred-oil-energy-prices
uv run python -m economic_analysis fetch bls-oews-swe-employment
uv run python -m economic_analysis model oil-consumer-burden
uv run python -m economic_analysis model oil-consumer-burden --oil-prices 80,100,120
uv run python -m economic_analysis model oil-consumer-burden --supply-shocks-mbd 1,3,5,8,10 --crude-demand-elasticity -0.10
```

`make download-data` fetches all configured datasets. BEA downloads require `BEA_API_KEY`
in the shell environment.

Raw responses are written to `data/raw/<source>/`. Normalized outputs are written to
`data/processed/<dataset>/` as both CSV and Parquet, with a metadata JSON sidecar.
The GDP components dataset stores exports and imports separately; trade balance can be
computed downstream as exports minus imports.

The oil consumer-burden model reads processed FRED oil/gasoline prices and CEX
income-quintile spending, then writes `outputs/oil_consumer_burden_scenarios.csv`.
By default it evaluates oil-price scenarios at $40, $60, $80, $100, $120, and
$140 per barrel. It can also estimate WTI scenarios from net crude supply gaps
using a tunable short-run demand elasticity and a default 100 million
barrels/day baseline supply assumption.
Model assumptions are documented in
[`docs/oil-consumer-burden-assumptions.html`](docs/oil-consumer-burden-assumptions.html).

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
