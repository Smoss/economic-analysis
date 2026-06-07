from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from economic_analysis.config import Settings
from economic_analysis.io import utc_now_iso, write_json
from economic_analysis.sources.models import BlsLaborResponse, NormalizedLaborRow

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_MAX_YEARS_PER_REQUEST = 10

BLS_LABOR_SERIES: dict[str, dict[str, str]] = {
    "LNS11000000": {"measure": "labor_force", "survey": "CPS", "frequency": "monthly", "unit": "thousands of persons"},
    "LNS12000000": {
        "measure": "household_employment",
        "survey": "CPS",
        "frequency": "monthly",
        "unit": "thousands of persons",
    },
    "LNS13000000": {"measure": "unemployment", "survey": "CPS", "frequency": "monthly", "unit": "thousands of persons"},
    "LNS14000000": {"measure": "unemployment_rate", "survey": "CPS", "frequency": "monthly", "unit": "percent"},
    "LNS11300000": {
        "measure": "labor_force_participation_rate",
        "survey": "CPS",
        "frequency": "monthly",
        "unit": "percent",
    },
    "LNS12300000": {
        "measure": "employment_population_ratio",
        "survey": "CPS",
        "frequency": "monthly",
        "unit": "percent",
    },
    "CES0000000001": {
        "measure": "total_nonfarm_payroll_employment",
        "survey": "CES",
        "frequency": "monthly",
        "unit": "thousands of employees",
    },
}

BLS_SECTOR_EMPLOYMENT_SERIES: dict[str, dict[str, str]] = {
    "CES0000000001": {"sector": "Total nonfarm", "sector_code": "00"},
    "CES0500000001": {"sector": "Total private", "sector_code": "05"},
    "CES1000000001": {"sector": "Mining and logging", "sector_code": "10"},
    "CES2000000001": {"sector": "Construction", "sector_code": "20"},
    "CES3000000001": {"sector": "Manufacturing", "sector_code": "30"},
    "CES4000000001": {"sector": "Trade, transportation, and utilities", "sector_code": "40"},
    "CES5000000001": {"sector": "Information", "sector_code": "50"},
    "CES5500000001": {"sector": "Financial activities", "sector_code": "55"},
    "CES6000000001": {"sector": "Professional and business services", "sector_code": "60"},
    "CES6500000001": {"sector": "Private education and health services", "sector_code": "65"},
    "CES7000000001": {"sector": "Leisure and hospitality", "sector_code": "70"},
    "CES8000000001": {"sector": "Other services", "sector_code": "80"},
    "CES9000000001": {"sector": "Government", "sector_code": "90"},
}


def labor_year_windows(start_year: int = 1990, end_year: int | None = None) -> list[tuple[int, int]]:
    end_year = end_year or pd.Timestamp.utcnow().year
    if start_year > end_year:
        raise ValueError("start_year must be less than or equal to end_year")

    windows: list[tuple[int, int]] = []
    window_start = start_year
    while window_start <= end_year:
        window_end = min(window_start + BLS_MAX_YEARS_PER_REQUEST - 1, end_year)
        windows.append((window_start, window_end))
        window_start = window_end + 1
    return windows


def build_labor_request(
    api_key: str | None = None, start_year: int = 1990, end_year: int | None = None
) -> dict[str, Any]:
    end_year = end_year or pd.Timestamp.utcnow().year
    payload: dict[str, Any] = {
        "seriesid": list(BLS_LABOR_SERIES),
        "startyear": str(start_year),
        "endyear": str(end_year),
        "annualaverage": False,
        "calculations": False,
    }
    if api_key:
        payload["registrationkey"] = api_key
    return payload


def build_sector_employment_request(
    api_key: str | None = None, start_year: int = 2020, end_year: int | None = None
) -> dict[str, Any]:
    end_year = end_year or pd.Timestamp.utcnow().year
    payload: dict[str, Any] = {
        "seriesid": list(BLS_SECTOR_EMPLOYMENT_SERIES),
        "startyear": str(start_year),
        "endyear": str(end_year),
        "annualaverage": False,
        "calculations": False,
    }
    if api_key:
        payload["registrationkey"] = api_key
    return payload


def fetch_labor(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw_requests: list[dict[str, Any]] = []
    frames: list[pd.DataFrame] = []
    release_notes: list[str] = []

    for start_year, end_year in labor_year_windows():
        payload = build_labor_request(settings.bls_api_key, start_year=start_year, end_year=end_year)
        response = requests.post(BLS_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        raw = response.json()
        parsed = BlsLaborResponse.model_validate(raw)

        sanitized_payload = {key: value for key, value in payload.items() if key != "registrationkey"}
        raw_requests.append(
            {
                "window": {"start_year": start_year, "end_year": end_year},
                "api_params": sanitized_payload,
                "response": raw,
            }
        )
        frames.append(normalize_labor(raw))
        release_notes.extend(parsed.message)

    raw_path = settings.data_dir / "raw" / "bls" / "labor.json"
    write_json(raw_path, {"requests": raw_requests})

    frame = pd.concat(frames, ignore_index=True) if frames else normalize_labor({})
    if not frame.empty:
        frame = frame.sort_values(["series_id", "date"]).reset_index(drop=True)
    metadata = {
        "source": "BLS Public Data API v2",
        "source_url": BLS_API_URL,
        "api_params": {"requests": [request["api_params"] for request in raw_requests]},
        "raw_path": str(raw_path),
        "fetched_at": utc_now_iso(),
        "frequency": "monthly",
        "units": sorted({info["unit"] for info in BLS_LABOR_SERIES.values()}),
        "release_notes": release_notes,
    }
    return frame, metadata


def fetch_sector_employment(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw_requests: list[dict[str, Any]] = []
    frames: list[pd.DataFrame] = []
    release_notes: list[str] = []

    for start_year, end_year in labor_year_windows(start_year=2020):
        payload = build_sector_employment_request(settings.bls_api_key, start_year=start_year, end_year=end_year)
        response = requests.post(BLS_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        raw = response.json()
        parsed = BlsLaborResponse.model_validate(raw)

        sanitized_payload = {key: value for key, value in payload.items() if key != "registrationkey"}
        raw_requests.append(
            {
                "window": {"start_year": start_year, "end_year": end_year},
                "api_params": sanitized_payload,
                "response": raw,
            }
        )
        frames.append(normalize_sector_employment(raw))
        release_notes.extend(parsed.message)

    raw_path = settings.data_dir / "raw" / "bls" / "sector_employment.json"
    write_json(raw_path, {"requests": raw_requests})

    frame = pd.concat(frames, ignore_index=True) if frames else normalize_sector_employment({})
    if not frame.empty:
        frame = frame.sort_values(["series_id", "date"]).reset_index(drop=True)
    metadata = {
        "source": "BLS Current Employment Statistics, Public Data API v2",
        "source_url": BLS_API_URL,
        "api_params": {"requests": [request["api_params"] for request in raw_requests]},
        "raw_path": str(raw_path),
        "fetched_at": utc_now_iso(),
        "frequency": "monthly",
        "units": ["thousands of employees"],
        "method": "Monthly seasonally adjusted payroll employment by CES supersector.",
        "release_notes": release_notes,
    }
    return frame, metadata


def normalize_labor(raw: dict[str, Any]) -> pd.DataFrame:
    parsed = BlsLaborResponse.model_validate(raw)
    rows: list[NormalizedLaborRow] = []
    for series in parsed.results.series:
        series_id = series.series_id
        info = BLS_LABOR_SERIES.get(series_id, {})
        for item in series.data:
            period = item.period
            if not period.startswith("M") or not period[1:].isdigit() or not 1 <= int(period[1:]) <= 12:
                continue
            value = pd.to_numeric(item.value, errors="coerce")
            rows.append(
                NormalizedLaborRow(
                    date=f"{item.year}-{period[1:]}-01",
                    series_id=series_id,
                    survey=info.get("survey"),
                    measure=info.get("measure", series_id),
                    value=None if pd.isna(value) else float(value),
                    unit=info.get("unit"),
                    frequency="monthly",
                    seasonality="seasonally_adjusted",
                )
            )

    frame = pd.DataFrame([row.model_dump() for row in rows])
    if frame.empty:
        return pd.DataFrame(
            columns=["date", "series_id", "survey", "measure", "value", "unit", "frequency", "seasonality"]
        )
    frame["date"] = pd.to_datetime(frame["date"]).dt.date.astype(str)
    frame = frame.sort_values(["series_id", "date"]).reset_index(drop=True)
    return frame


def normalize_sector_employment(raw: dict[str, Any]) -> pd.DataFrame:
    parsed = BlsLaborResponse.model_validate(raw)
    rows: list[dict[str, Any]] = []
    for series in parsed.results.series:
        series_id = series.series_id
        info = BLS_SECTOR_EMPLOYMENT_SERIES.get(series_id, {})
        for item in series.data:
            period = item.period
            if not period.startswith("M") or not period[1:].isdigit() or not 1 <= int(period[1:]) <= 12:
                continue
            value = pd.to_numeric(item.value, errors="coerce")
            rows.append(
                {
                    "date": f"{item.year}-{period[1:]}-01",
                    "series_id": series_id,
                    "sector": info.get("sector", series_id),
                    "sector_code": info.get("sector_code"),
                    "measure": "payroll_employment",
                    "value": None if pd.isna(value) else float(value),
                    "unit": "thousands of employees",
                    "frequency": "monthly",
                    "seasonality": "seasonally_adjusted",
                }
            )

    columns = [
        "date",
        "series_id",
        "sector",
        "sector_code",
        "measure",
        "value",
        "unit",
        "frequency",
        "seasonality",
    ]
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"]).dt.date.astype(str)
    return frame.sort_values(["series_id", "date"]).reset_index(drop=True)
