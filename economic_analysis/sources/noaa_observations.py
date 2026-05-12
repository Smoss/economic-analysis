from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import requests

from economic_analysis.config import Settings
from economic_analysis.io import utc_now_iso, write_json
from economic_analysis.sources.noaa_common import NORTHEAST_AIRPORT_STATIONS, STUDY_END, STUDY_START, station_metadata

CDO_API_URL = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"
CDO_DATASET = "GHCND"
CDO_DATATYPES = ("TMAX", "TMIN", "PRCP")
CDO_LIMIT = 1000


def observation_year_windows(start: date = STUDY_START, end: date = STUDY_END) -> list[tuple[date, date]]:
    if start > end:
        raise ValueError("start must be less than or equal to end")
    windows: list[tuple[date, date]] = []
    year = start.year
    while year <= end.year:
        window_start = max(start, date(year, 1, 1))
        window_end = min(end, date(year, 12, 31))
        windows.append((window_start, window_end))
        year += 1
    return windows


def build_cdo_params(station_id: str, start: date, end: date, offset: int = 1) -> dict[str, Any]:
    return {
        "datasetid": CDO_DATASET,
        "stationid": station_id,
        "datatypeid": list(CDO_DATATYPES),
        "startdate": start.isoformat(),
        "enddate": end.isoformat(),
        "units": "standard",
        "limit": CDO_LIMIT,
        "offset": offset,
    }


def fetch_station_observations(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not settings.noaa_cdo_token:
        raise RuntimeError("NOAA_CDO_TOKEN is required for NOAA CDO station observation fetches.")

    headers = {"token": settings.noaa_cdo_token}
    raw_requests: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []

    for station in NORTHEAST_AIRPORT_STATIONS:
        for start, end in observation_year_windows():
            offset = 1
            while True:
                params = build_cdo_params(station.station_id, start, end, offset)
                response = requests.get(CDO_API_URL, params=params, headers=headers, timeout=60)
                response.raise_for_status()
                payload = response.json()
                results = payload.get("results", [])
                raw_requests.append(
                    {
                        "station": station.code,
                        "station_id": station.station_id,
                        "api_params": params,
                        "response": payload,
                    }
                )
                all_results.extend(results)
                result_count = int(payload.get("metadata", {}).get("resultset", {}).get("count", len(results)))
                if offset + CDO_LIMIT > result_count:
                    break
                offset += CDO_LIMIT

    raw_path = settings.data_dir / "raw" / "noaa" / "observations" / "cdo_daily_observations.json"
    write_json(raw_path, {"requests": raw_requests})

    frame = normalize_station_observations(all_results)
    metadata = {
        "source": "NOAA/NCEI Climate Data Online daily summaries",
        "source_url": CDO_API_URL,
        "dataset": CDO_DATASET,
        "api_params": {
            "datasetid": CDO_DATASET,
            "datatypeid": list(CDO_DATATYPES),
            "startdate": STUDY_START.isoformat(),
            "enddate": STUDY_END.isoformat(),
            "units": "standard",
        },
        "raw_path": str(raw_path),
        "fetched_at": utc_now_iso(),
        "frequency": "daily",
        "units": {"temperature": "degrees_fahrenheit", "precipitation": "inches"},
        "stations": station_metadata(),
    }
    return frame, metadata


def normalize_station_observations(raw_results: list[dict[str, Any]]) -> pd.DataFrame:
    if not raw_results:
        return pd.DataFrame(
            columns=[
                "station",
                "station_id",
                "date",
                "observed_high_f",
                "observed_low_f",
                "observed_precip_in",
            ]
        )

    rows = pd.DataFrame(raw_results)
    rows["date"] = pd.to_datetime(rows["date"], utc=True).dt.date.astype(str)
    rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
    pivot = (
        rows.pivot_table(
            index=["station"],
            columns="datatype",
            values="value",
            aggfunc="first",
        )
        if "date" not in rows.columns
        else rows.pivot_table(
            index=["station", "date"],
            columns="datatype",
            values="value",
            aggfunc="first",
        )
    )
    frame = pivot.reset_index().rename(
        columns={
            "TMAX": "observed_high_f",
            "TMIN": "observed_low_f",
            "PRCP": "observed_precip_in",
            "station": "station_id",
        }
    )
    id_map = {station.station_id: station.code for station in NORTHEAST_AIRPORT_STATIONS}
    frame["station"] = frame["station_id"].map(id_map).fillna(frame["station_id"])
    columns = ["station", "station_id", "date", "observed_high_f", "observed_low_f", "observed_precip_in"]
    for column in columns:
        if column not in frame:
            frame[column] = pd.NA
    return frame[columns].sort_values(["station", "date"]).reset_index(drop=True)

