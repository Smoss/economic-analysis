from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from economic_analysis.config import Settings
from economic_analysis.io import write_dataset
from economic_analysis.sources import (
    acs_pums,
    bea,
    bls,
    bls_oews,
    cex,
    fred,
    noaa_ndfd,
    noaa_observations,
    nws_accuracy,
    scf,
)


@dataclass(frozen=True)
class FetchResult:
    dataset: str
    rows: int
    outputs: dict[str, str]


FetchFn = Callable[[Settings, bool], FetchResult]


def dry_run_outputs(settings: Settings, dataset: str) -> dict[str, str]:
    base = settings.data_dir / "processed" / dataset
    return {
        "csv": str(base / f"{dataset}.csv"),
        "parquet": str(base / f"{dataset}.parquet"),
        "metadata": str(base / "metadata.json"),
    }


def dry_run_result(settings: Settings, dataset: str) -> FetchResult:
    return FetchResult(dataset=dataset, rows=0, outputs=dry_run_outputs(settings, dataset))


def fetch_bls_labor(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "bls_labor"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = bls.fetch_labor(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_bls_sector_employment(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "bls_sector_employment"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = bls.fetch_sector_employment(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_bls_cex_consumption(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "bls_cex_consumption"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = cex.fetch_consumption(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_bls_oews_swe_employment(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "bls_oews_swe_employment"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = bls_oews.fetch_swe_employment(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_bea_pce(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "bea_pce"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = bea.fetch_pce(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_bea_gdp_components(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "bea_gdp_components"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = bea.fetch_gdp_components(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_bea_gdp_industry(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "bea_gdp_industry"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = bea.fetch_gdp_industry(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_scf_home_assets(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "scf_home_assets"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = scf.fetch_home_assets(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_acs_major_employment(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "acs_major_employment"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = acs_pums.fetch_major_employment(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_fred_swe_labor_market(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "fred_swe_labor_market"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = fred.fetch_swe_labor_market(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_fred_consumer_sentiment(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "fred_consumer_sentiment"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = fred.fetch_consumer_sentiment(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_fred_oil_energy_prices(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "fred_oil_energy_prices"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = fred.fetch_oil_energy_prices(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_fred_indeed_job_postings(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "fred_indeed_job_postings"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = fred.fetch_indeed_job_postings(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_noaa_ndfd_forecasts(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "noaa_ndfd_forecasts"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = noaa_ndfd.fetch_ndfd_forecasts(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_noaa_station_observations(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "noaa_station_observations"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = noaa_observations.fetch_station_observations(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


def fetch_nws_forecast_accuracy(settings: Settings, dry_run: bool = False) -> FetchResult:
    dataset = "nws_forecast_accuracy"
    if dry_run:
        return dry_run_result(settings, dataset)
    frame, metadata = nws_accuracy.fetch_forecast_accuracy(settings)
    outputs = write_dataset(settings.data_dir, dataset, frame, metadata)
    outputs.update(metadata.get("report_outputs", {}))
    return FetchResult(dataset=dataset, rows=len(frame), outputs=outputs)


FETCHERS: dict[str, FetchFn] = {
    "bls-labor": fetch_bls_labor,
    "bls-sector-employment": fetch_bls_sector_employment,
    "bls-cex-consumption": fetch_bls_cex_consumption,
    "bls-oews-swe-employment": fetch_bls_oews_swe_employment,
    "bea-pce": fetch_bea_pce,
    "bea-gdp-components": fetch_bea_gdp_components,
    "bea-gdp-industry": fetch_bea_gdp_industry,
    "scf-home-assets": fetch_scf_home_assets,
    "acs-major-employment": fetch_acs_major_employment,
    "fred-swe-labor-market": fetch_fred_swe_labor_market,
    "fred-consumer-sentiment": fetch_fred_consumer_sentiment,
    "fred-oil-energy-prices": fetch_fred_oil_energy_prices,
    "fred-indeed-job-postings": fetch_fred_indeed_job_postings,
    "noaa-ndfd-forecasts": fetch_noaa_ndfd_forecasts,
    "noaa-station-observations": fetch_noaa_station_observations,
    "nws-forecast-accuracy": fetch_nws_forecast_accuracy,
}


def fetch_all(settings: Settings, dry_run: bool = False) -> list[FetchResult]:
    if not dry_run and not settings.bea_api_key:
        raise RuntimeError("BEA_API_KEY is required for `fetch all`. Fetch non-BEA datasets individually if needed.")
    return [fetcher(settings, dry_run) for fetcher in FETCHERS.values()]


def normalize_data_dir(path: str | Path | None) -> Path | None:
    return Path(path).expanduser() if path else None
