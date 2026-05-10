from __future__ import annotations

from typing import Any, Literal

import pandas as pd
import requests

from economic_analysis.config import Settings
from economic_analysis.io import utc_now_iso, write_json
from economic_analysis.sources.models import (
    BeaGdpIndustryDataRow,
    BeaPceDataRow,
    BeaResponse,
    NormalizedGdpIndustryRow,
    NormalizedPceRow,
)

BEA_API_URL = "https://apps.bea.gov/api/data/"
PCE_TABLE = "T20805"
GDP_INDUSTRY_TABLES = {
    "1": "value_added_current_dollars",
    "5": "value_added_percent_of_gdp",
    "10": "real_value_added_chained_dollars",
}


def require_bea_key(settings: Settings) -> str:
    if not settings.bea_api_key:
        raise RuntimeError("BEA_API_KEY is required for BEA fetches.")
    return settings.bea_api_key


def build_bea_pce_params(api_key: str, year: str = "X") -> dict[str, str]:
    return {
        "UserID": api_key,
        "method": "GetData",
        "datasetname": "NIPA",
        "TableName": PCE_TABLE,
        "Frequency": "M",
        "Year": year,
        "ResultFormat": "JSON",
    }


def build_bea_gdp_industry_params(api_key: str, table_id: str, year: str = "ALL") -> dict[str, str]:
    return {
        "UserID": api_key,
        "method": "GetData",
        "datasetname": "GDPbyIndustry",
        "TableID": table_id,
        "Frequency": "A,Q",
        "Year": year,
        "Industry": "ALL",
        "ResultFormat": "JSON",
    }


def fetch_pce(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    params = build_bea_pce_params(require_bea_key(settings))
    raw = _get_bea(params)
    raw_path = settings.data_dir / "raw" / "bea" / "pce.json"
    write_json(raw_path, raw)
    frame = normalize_pce(raw)
    metadata = _bea_metadata("BEA NIPA Personal Consumption Expenditures", params, raw_path, frame)
    return frame, metadata


def fetch_gdp_industry(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    api_key = require_bea_key(settings)
    raw_payloads: dict[str, Any] = {}
    frames: list[pd.DataFrame] = []
    safe_params: list[dict[str, str]] = []
    for table_id in GDP_INDUSTRY_TABLES:
        params = build_bea_gdp_industry_params(api_key, table_id)
        raw = _get_bea(params)
        raw_payloads[table_id] = raw
        safe_params.append({key: value for key, value in params.items() if key != "UserID"})
        frames.append(normalize_gdp_industry(raw, table_id, GDP_INDUSTRY_TABLES[table_id]))

    raw_path = settings.data_dir / "raw" / "bea" / "gdp_industry.json"
    write_json(raw_path, raw_payloads)
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    metadata = {
        "source": "BEA API GDPbyIndustry",
        "source_url": BEA_API_URL,
        "api_params": safe_params,
        "raw_path": str(raw_path),
        "fetched_at": utc_now_iso(),
        "frequency": sorted(frame["frequency"].dropna().unique().tolist())
        if not frame.empty
        else ["annual", "quarterly"],
        "units": sorted(frame["unit"].dropna().unique().tolist()) if not frame.empty else [],
        "release_notes": _bea_notes(raw_payloads),
    }
    return frame, metadata


def _get_bea(params: dict[str, str]) -> dict[str, Any]:
    response = requests.get(BEA_API_URL, params=params, timeout=90)
    response.raise_for_status()
    raw = response.json()
    try:
        BeaResponse.model_validate(raw)
    except ValueError as error:
        raise RuntimeError(str(error)) from error
    return raw


def normalize_pce(raw: dict[str, Any]) -> pd.DataFrame:
    rows = [BeaPceDataRow.model_validate(row) for row in _bea_data_rows(raw)]
    normalized: list[NormalizedPceRow] = []
    for row in rows:
        normalized.append(
            NormalizedPceRow(
                date=_bea_period_to_date(row.time_period),
                frequency="monthly",
                line_code=row.line_number,
                category=row.line_description,
                value=_numeric(row.data_value),
                unit=row.unit,
                source_table=row.table_name or PCE_TABLE,
            )
        )
    columns = ["date", "frequency", "line_code", "category", "value", "unit", "source_table"]
    frame = pd.DataFrame([row.model_dump() for row in normalized], columns=columns)
    return frame.sort_values(["line_code", "date"]).reset_index(drop=True) if not frame.empty else frame


def normalize_gdp_industry(raw: dict[str, Any], table_id: str, metric: str) -> pd.DataFrame:
    rows = [BeaGdpIndustryDataRow.model_validate(row) for row in _bea_data_rows(raw)]
    normalized: list[NormalizedGdpIndustryRow] = []
    for row in rows:
        raw_period = row.year or ""
        year = _period_year(raw_period)
        quarter = _bea_quarter(row.quarter) or _period_quarter(raw_period)
        period = f"{year}Q{quarter}" if year and quarter else str(raw_period)
        normalized.append(
            NormalizedGdpIndustryRow(
                period=period,
                year=year,
                quarter=quarter,
                frequency=_bea_frequency(row.frequency, period),
                industry=row.industry_description,
                industry_code=row.industry,
                metric=metric,
                value=_numeric(row.data_value),
                unit=row.unit,
                table_id=table_id,
            )
        )
    columns = [
        "period",
        "year",
        "quarter",
        "frequency",
        "industry",
        "industry_code",
        "metric",
        "value",
        "unit",
        "table_id",
    ]
    frame = pd.DataFrame([row.model_dump() for row in normalized], columns=columns)
    return (
        frame.sort_values(["table_id", "industry_code", "period"]).reset_index(drop=True) if not frame.empty else frame
    )


def _bea_data_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return BeaResponse.model_validate(raw).data_rows()


def _bea_metadata(source: str, params: dict[str, str], raw_path: Any, frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "source": source,
        "source_url": BEA_API_URL,
        "api_params": {key: value for key, value in params.items() if key != "UserID"},
        "raw_path": str(raw_path),
        "fetched_at": utc_now_iso(),
        "frequency": sorted(frame["frequency"].dropna().unique().tolist()) if not frame.empty else [],
        "units": sorted(frame["unit"].dropna().unique().tolist()) if not frame.empty else [],
    }


def _bea_notes(raw: dict[str, Any]) -> list[Any]:
    if "BEAAPI" in raw:
        return [
            note.model_dump() if hasattr(note, "model_dump") else note
            for note in BeaResponse.model_validate(raw).notes()
        ]
    notes: list[Any] = []
    for payload in raw.values():
        notes.extend(
            note.model_dump() if hasattr(note, "model_dump") else note
            for note in BeaResponse.model_validate(payload).notes()
        )
    return notes


def _numeric(value: Any) -> float | None:
    if value in (None, "", "(NA)"):
        return None
    numeric = pd.to_numeric(str(value).replace(",", ""), errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _bea_period_to_date(period: str) -> str | None:
    if not period:
        return None
    if "M" in period:
        year, month = period.split("M", 1)
        return f"{year}-{month.zfill(2)}-01"
    if "Q" in period:
        year, quarter = period.split("Q", 1)
        month = {"1": "01", "2": "04", "3": "07", "4": "10"}.get(quarter, "01")
        return f"{year}-{month}-01"
    return f"{period}-01-01"


def _period_year(period: Any) -> int | None:
    text = str(period)
    if len(text) < 4:
        return None
    return int(text[:4]) if text[:4].isdigit() else None


def _period_quarter(period: Any) -> int | None:
    text = str(period)
    if "Q" not in text:
        return None
    quarter = text.rsplit("Q", 1)[-1]
    return int(quarter) if quarter.isdigit() else None


def _bea_quarter(value: Any) -> int | None:
    if value in (None, "", "None"):
        return None
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return {"I": 1, "II": 2, "III": 3, "IV": 4, "Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}.get(text.upper())


def _bea_frequency(value: Any, period: Any) -> Literal["annual", "quarterly"]:
    text = str(value or "").upper()
    if text == "Q" or _period_quarter(period):
        return "quarterly"
    return "annual"
