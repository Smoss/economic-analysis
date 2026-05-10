from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from economic_analysis.config import Settings
from economic_analysis.io import utc_now_iso, write_json
from economic_analysis.sources.models import BlsLaborResponse, NormalizedLaborRow

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

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


def fetch_labor(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    payload = build_labor_request(settings.bls_api_key)
    response = requests.post(BLS_API_URL, json=payload, timeout=60)
    response.raise_for_status()
    raw = response.json()

    raw_path = settings.data_dir / "raw" / "bls" / "labor.json"
    write_json(raw_path, raw)

    parsed = BlsLaborResponse.model_validate(raw)
    frame = normalize_labor(raw)
    metadata = {
        "source": "BLS Public Data API v2",
        "source_url": BLS_API_URL,
        "api_params": {key: value for key, value in payload.items() if key != "registrationkey"},
        "raw_path": str(raw_path),
        "fetched_at": utc_now_iso(),
        "frequency": "monthly",
        "units": sorted({info["unit"] for info in BLS_LABOR_SERIES.values()}),
        "release_notes": parsed.message,
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
