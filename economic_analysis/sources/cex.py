from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from economic_analysis.config import Settings
from economic_analysis.io import ensure_dir, utc_now_iso
from economic_analysis.sources.models import NormalizedCexConsumptionRow

CEX_BASE_URL = "https://download.bls.gov/pub/time.series/CX/"
CEX_DOWNLOAD_HEADERS = {
    "User-Agent": "economic-analysis/0.1 (+https://www.bls.gov/cex/)",
    "Accept": "text/plain,*/*",
}
CEX_FILES = {
    "series": "cx.series",
    "aspect": "cx.aspect",
    "all_data": "cx.data.1.AllData",
    "item": "cx.item",
    "subcategory": "cx.subcategory",
    "demographics": "cx.demographics",
    "characteristics": "cx.characteristics",
}
CEX_INCOME_QUINTILE_DEMOGRAPHICS_CODE = "LB01"
CEX_ALL_CONSUMERS_CHARACTERISTIC_CODE = "01"
CEX_INCOME_QUINTILE_CHARACTERISTIC_CODES = {"02", "03", "04", "05", "06"}
CEX_AGGREGATE_ASPECT_TYPE = "AG"
CEX_TOTAL_ITEM_CODES = {"TOTALEXP", "TOTEXP", "TOTEXPCQ"}
CEX_DETAILED_CONSUMER_BURDEN_ITEM_CODES = {"GASFUEL"}


def fetch_consumption(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw_dir = settings.data_dir / "raw" / "bls" / "cex"
    raw_paths = download_cex_files(raw_dir)

    series_rows = list(iter_tab_records(raw_paths["series"]))
    item_rows = list(iter_tab_records(raw_paths["item"]))
    subcategory_rows = list(iter_tab_records(raw_paths["subcategory"]))
    demographics_rows = list(iter_tab_records(raw_paths["demographics"]))
    characteristics_rows = list(iter_tab_records(raw_paths["characteristics"]))

    frame = normalize_consumption(
        series_rows=series_rows,
        aspect_rows=iter_tab_records(raw_paths["aspect"]),
        item_rows=item_rows,
        subcategory_rows=subcategory_rows,
        demographics_rows=demographics_rows,
        characteristics_rows=characteristics_rows,
    )
    metadata = {
        "source": "BLS Consumer Expenditure Surveys LABSTAT",
        "source_url": CEX_BASE_URL,
        "raw_path": str(raw_dir),
        "raw_files": {key: str(path) for key, path in raw_paths.items()},
        "fetched_at": utc_now_iso(),
        "frequency": "annual",
        "units": ["millions_of_dollars"],
        "measure": "aggregate_expenditure",
        "demographic": "income_quintile",
        "detailed_items": sorted(CEX_DETAILED_CONSUMER_BURDEN_ITEM_CODES),
    }
    return frame, metadata


def download_cex_files(raw_dir: Path) -> dict[str, Path]:
    ensure_dir(raw_dir)
    paths: dict[str, Path] = {}
    for key, filename in CEX_FILES.items():
        path = raw_dir / filename
        url = f"{CEX_BASE_URL}{filename}"
        response = requests.get(url, headers=CEX_DOWNLOAD_HEADERS, stream=True, timeout=120)
        response.raise_for_status()
        with path.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
        paths[key] = path
    return paths


def iter_tab_records(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as input_file:
        yield from parse_tab_records(input_file)


def parse_tab_records(lines: Iterable[str]) -> Iterator[dict[str, str]]:
    reader = csv.DictReader(lines, delimiter="\t")
    for row in reader:
        yield {str(key).strip(): str(value).strip() for key, value in row.items() if key is not None}


def normalize_consumption(
    *,
    series_rows: Iterable[dict[str, str]],
    aspect_rows: Iterable[dict[str, str]],
    item_rows: Iterable[dict[str, str]],
    subcategory_rows: Iterable[dict[str, str]],
    demographics_rows: Iterable[dict[str, str]],
    characteristics_rows: Iterable[dict[str, str]],
) -> pd.DataFrame:
    item_rows = list(item_rows)
    subcategory_rows = list(subcategory_rows)
    characteristics_rows = list(characteristics_rows)

    item_lookup = _lookup(item_rows, "item_code", "item_text")
    major_item_codes = _major_item_codes(item_rows)
    subcategory_lookup = _lookup(subcategory_rows, "subcategory_code", "subcategory_text")
    characteristics_lookup = _characteristics_lookup(characteristics_rows)

    relevant_series = _relevant_series(series_rows, major_item_codes)
    all_consumer_series = {
        series_id
        for series_id, info in relevant_series.items()
        if info["characteristics_code"] == CEX_ALL_CONSUMERS_CHARACTERISTIC_CODE
    }
    quintile_series = {
        series_id
        for series_id, info in relevant_series.items()
        if info["characteristics_code"] in CEX_INCOME_QUINTILE_CHARACTERISTIC_CODES
    }

    total_aggregates: dict[tuple[str, int], float] = {}
    quintile_shares: list[dict[str, Any]] = []
    for row in aspect_rows:
        series_id = row.get("series_id", "")
        if row.get("aspect_type") != CEX_AGGREGATE_ASPECT_TYPE or row.get("period") != "A01":
            continue
        if series_id not in all_consumer_series and series_id not in quintile_series:
            continue

        value = _numeric(row.get("value"))
        if value is None:
            continue
        year = int(row["year"])
        info = relevant_series[series_id]
        if series_id in all_consumer_series:
            total_aggregates[(info["item_code"], year)] = value
        else:
            quintile_shares.append(
                {
                    "series_id": series_id,
                    "year": year,
                    "period": row["period"],
                    "share": value,
                    "footnote_code": row.get("footnote_code") or None,
                    "series": info,
                }
            )

    rows: list[NormalizedCexConsumptionRow] = []
    for share_row in quintile_shares:
        info = share_row["series"]
        total = total_aggregates.get((info["item_code"], share_row["year"]))
        value = None if total is None else total * share_row["share"] / 100
        group = characteristics_lookup.get(
            (info["demographics_code"], info["characteristics_code"]),
            info["characteristics_code"],
        )
        rows.append(
            NormalizedCexConsumptionRow(
                year=share_row["year"],
                period=share_row["period"],
                frequency="annual",
                series_id=share_row["series_id"],
                category="Expenditures",
                subcategory=subcategory_lookup.get(info["subcategory_code"], info["subcategory_code"]),
                item=item_lookup.get(info["item_code"], info["item_code"]),
                demographic="income_quintile",
                group=group,
                measure="aggregate_expenditure",
                value=value,
                unit="millions_of_dollars",
                raw_aspect_value=share_row["share"],
                raw_aspect_unit="percent_of_total_aggregate",
                footnote_code=share_row["footnote_code"],
            )
        )

    columns = [
        "year",
        "period",
        "frequency",
        "series_id",
        "category",
        "subcategory",
        "item",
        "demographic",
        "group",
        "measure",
        "value",
        "unit",
        "raw_aspect_value",
        "raw_aspect_unit",
        "footnote_code",
    ]
    frame = pd.DataFrame([row.model_dump() for row in rows], columns=columns)
    if frame.empty:
        return frame
    return frame.sort_values(["year", "item", "group"]).reset_index(drop=True)


def _relevant_series(series_rows: Iterable[dict[str, str]], major_item_codes: set[str]) -> dict[str, dict[str, str]]:
    series: dict[str, dict[str, str]] = {}
    allowed_characteristics = CEX_INCOME_QUINTILE_CHARACTERISTIC_CODES | {CEX_ALL_CONSUMERS_CHARACTERISTIC_CODE}
    for row in series_rows:
        if row.get("category_code") != "EXPEND":
            continue
        if row.get("demographics_code") != CEX_INCOME_QUINTILE_DEMOGRAPHICS_CODE:
            continue
        if row.get("characteristics_code") not in allowed_characteristics:
            continue
        if row.get("process_code") != "M":
            continue
        if row.get("item_code") not in major_item_codes:
            continue
        series[row["series_id"]] = row
    return series


def _major_item_codes(item_rows: Iterable[dict[str, str]]) -> set[str]:
    codes = set(CEX_TOTAL_ITEM_CODES) | CEX_DETAILED_CONSUMER_BURDEN_ITEM_CODES
    for row in item_rows:
        if row.get("display_level") == "0" and row.get("selectable", "T") == "T":
            codes.add(row["item_code"])
    return codes


def _lookup(rows: Iterable[dict[str, str]], key: str, value: str) -> dict[str, str]:
    return {row[key]: row[value] for row in rows if row.get(key) and row.get(value)}


def _characteristics_lookup(rows: Iterable[dict[str, str]]) -> dict[tuple[str, str], str]:
    return {
        (row["demographics_code"], row["characteristics_code"]): row["characteristics_text"]
        for row in rows
        if row.get("demographics_code") and row.get("characteristics_code") and row.get("characteristics_text")
    }


def _numeric(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    numeric = pd.to_numeric(str(value).replace(",", ""), errors="coerce")
    return None if pd.isna(numeric) else float(numeric)
