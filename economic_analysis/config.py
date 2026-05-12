from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    bea_api_key: str | None
    bls_api_key: str | None
    noaa_cdo_token: str | None = None
    noaa_ndfd_forecast_csv_url: str | None = None


def load_settings(data_dir: Path | None = None) -> Settings:
    return Settings(
        data_dir=data_dir or Path("data"),
        bea_api_key=os.getenv("BEA_API_KEY") or None,
        bls_api_key=os.getenv("BLS_API_KEY") or None,
        noaa_cdo_token=os.getenv("NOAA_CDO_TOKEN") or None,
        noaa_ndfd_forecast_csv_url=os.getenv("NOAA_NDFD_FORECAST_CSV_URL") or None,
    )
