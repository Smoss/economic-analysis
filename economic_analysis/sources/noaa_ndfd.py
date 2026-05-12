from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd
import requests

from economic_analysis.config import Settings
from economic_analysis.io import utc_now_iso, write_text
from economic_analysis.sources.noaa_common import (
    ISSUE_CYCLE,
    LEAD_DAYS,
    STUDY_END,
    STUDY_START,
    station_metadata,
)

NDFD_NCEI_URL = "https://www.ncei.noaa.gov/products/weather-climate-models/national-digital-forecast-database"
NDFD_THREDDS_CATALOG_URL = "https://www.ncei.noaa.gov/thredds/catalog/model-ndfd-file/catalog.html"
FORECAST_COLUMNS = [
    "station",
    "station_id",
    "issue_date",
    "issue_cycle",
    "valid_date",
    "lead_day",
    "forecast_high_f",
    "forecast_low_f",
    "forecast_precip_in",
    "forecast_pop_pct",
]


def fetch_ndfd_forecasts(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not settings.noaa_ndfd_forecast_csv_url:
        raise RuntimeError(
            "NOAA_NDFD_FORECAST_CSV_URL is required for live NDFD fetches. "
            "Point-extracted NDFD CSV must be generated repeatably from the NCEI GRIB-2 archive."
        )

    response = requests.get(settings.noaa_ndfd_forecast_csv_url, timeout=120)
    response.raise_for_status()
    raw_text = response.text
    raw_path = settings.data_dir / "raw" / "noaa" / "ndfd" / "ndfd_point_forecasts.csv"
    write_text(raw_path, raw_text)

    frame = normalize_ndfd_forecasts(pd.read_csv(StringIO(raw_text)))
    metadata = {
        "source": "NOAA/NCEI National Digital Forecast Database point extraction",
        "source_url": NDFD_NCEI_URL,
        "thredds_catalog_url": NDFD_THREDDS_CATALOG_URL,
        "raw_url": settings.noaa_ndfd_forecast_csv_url,
        "raw_path": str(raw_path),
        "fetched_at": utc_now_iso(),
        "frequency": "daily",
        "issue_cycle": ISSUE_CYCLE,
        "lead_days": list(LEAD_DAYS),
        "period": {"start": STUDY_START.isoformat(), "end": STUDY_END.isoformat()},
        "units": {"temperature": "degrees_fahrenheit", "precipitation": "inches", "probability": "percent"},
        "stations": station_metadata(),
        "method": "Fetch a reproducible station-point CSV extracted from NCEI NDFD GRIB-2 files, then normalize.",
    }
    return frame, metadata


def normalize_ndfd_forecasts(raw: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(raw).copy()
    if frame.empty:
        return pd.DataFrame(columns=FORECAST_COLUMNS)

    rename_map = {
        "code": "station",
        "forecast_date": "valid_date",
        "target_date": "valid_date",
        "max_temp_f": "forecast_high_f",
        "min_temp_f": "forecast_low_f",
        "qpf_in": "forecast_precip_in",
        "pop_pct": "forecast_pop_pct",
    }
    frame = frame.rename(columns={key: value for key, value in rename_map.items() if key in frame.columns})
    for column in FORECAST_COLUMNS:
        if column not in frame:
            frame[column] = pd.NA

    frame["issue_date"] = pd.to_datetime(frame["issue_date"]).dt.date.astype(str)
    frame["valid_date"] = pd.to_datetime(frame["valid_date"]).dt.date.astype(str)
    frame["lead_day"] = pd.to_numeric(frame["lead_day"], errors="coerce").astype("Int64")
    frame["issue_cycle"] = frame["issue_cycle"].fillna(ISSUE_CYCLE)
    for column in ["forecast_high_f", "forecast_low_f", "forecast_precip_in", "forecast_pop_pct"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame[frame["lead_day"].isin(LEAD_DAYS)]
    frame = frame[(frame["valid_date"] >= STUDY_START.isoformat()) & (frame["valid_date"] <= STUDY_END.isoformat())]
    return frame[FORECAST_COLUMNS].sort_values(["station", "valid_date", "lead_day"]).reset_index(drop=True)

