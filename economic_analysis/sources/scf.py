from __future__ import annotations

import zipfile
from io import BytesIO
from typing import Any, Literal, cast

import pandas as pd
import requests

from economic_analysis.config import Settings
from economic_analysis.io import utc_now_iso
from economic_analysis.sources.models import ScfHomeAssetRow

SCF_CHARTBOOK_ZIP_URL = "https://www.federalreserve.gov/econres/scf/dataviz/download/zips/scf.zip"
HOME_ASSET_COLUMNS = {
    "Primary_Residence": "primary_residence",
    "Other_Residential_Real_Estate": "other_residential_real_estate",
}
STANDARD_GROUP_FILES = {
    "agecl": "age",
    "edcl": "education",
    "inccat": "income",
    "nwcat": "net_worth_percentile",
    "racecl4": "race_ethnicity",
}
STATISTIC_UNITS = {
    "have": "percent_holding",
    "mean": "2022_dollars",
    "median": "2022_dollars",
}


def fetch_home_assets(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    response = requests.get(SCF_CHARTBOOK_ZIP_URL, timeout=90)
    response.raise_for_status()
    raw_path = settings.data_dir / "raw" / "scf" / "scf_chartbook.zip"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(response.content)

    frame = normalize_home_assets_zip(response.content)
    metadata = {
        "source": "Federal Reserve Survey of Consumer Finances interactive chartbook CSV",
        "source_url": SCF_CHARTBOOK_ZIP_URL,
        "api_params": {},
        "raw_path": str(raw_path),
        "fetched_at": utc_now_iso(),
        "frequency": "triennial survey",
        "units": sorted(frame["unit"].dropna().unique().tolist()) if not frame.empty else [],
        "release_notes": (
            "SCF public chartbook data; primary residence and other residential real estate columns extracted from "
            "standard distribution CSVs."
        ),
    }
    return frame, metadata


def normalize_home_assets_zip(content: bytes) -> pd.DataFrame:
    archive = zipfile.ZipFile(BytesIO(content))
    frames: list[pd.DataFrame] = []
    for name in archive.namelist():
        group_type = _group_type_from_filename(name)
        statistic = _statistic_from_filename(name)
        if group_type is None or statistic is None:
            continue
        raw = pd.read_csv(archive.open(name))
        normalized = _normalize_csv(raw, group_type, statistic)
        if not normalized.empty:
            frames.append(normalized)
    columns = ["survey_year", "asset_component", "group_type", "group", "statistic", "value", "unit"]
    if not frames:
        return pd.DataFrame(columns=columns)
    frame = pd.concat(frames, ignore_index=True)[columns].drop_duplicates().reset_index(drop=True)
    return frame.sort_values(["group_type", "group", "asset_component", "statistic", "survey_year"]).reset_index(
        drop=True
    )


def _normalize_csv(raw: pd.DataFrame, group_type: str, statistic: str) -> pd.DataFrame:
    home_columns = [column for column in HOME_ASSET_COLUMNS if column in raw.columns]
    if not home_columns:
        return pd.DataFrame()

    melted = raw.melt(
        id_vars=["year", "Category"],
        value_vars=home_columns,
        var_name="asset_component",
        value_name="value",
    )
    melted["value"] = pd.to_numeric(melted["value"], errors="coerce")
    melted = melted.dropna(subset=["value"])
    if melted.empty:
        return pd.DataFrame()

    parsed_group_type = cast(
        Literal["age", "education", "income", "net_worth_percentile", "race_ethnicity"],
        group_type,
    )
    parsed_statistic = cast(Literal["have", "mean", "median"], statistic)
    rows = []
    for row in melted.itertuples(index=False):
        asset_component = cast(
            Literal["primary_residence", "other_residential_real_estate"],
            HOME_ASSET_COLUMNS[row.asset_component],
        )
        unit = cast(Literal["percent_holding", "2022_dollars"], STATISTIC_UNITS[statistic])
        rows.append(
            ScfHomeAssetRow(
                survey_year=int(row.year),
                asset_component=asset_component,
                group_type=parsed_group_type,
                group=str(row.Category),
                statistic=parsed_statistic,
                value=float(row.value),
                unit=unit,
            )
        )
    return pd.DataFrame([row.model_dump() for row in rows])


def _group_type_from_filename(name: str) -> str | None:
    for token, group_type in STANDARD_GROUP_FILES.items():
        if f"_{token}_" in name:
            return group_type
    return None


def _statistic_from_filename(name: str) -> str | None:
    stem = name.rsplit("/", 1)[-1].removesuffix(".csv")
    statistic = stem.rsplit("_", 1)[-1]
    return statistic if statistic in STATISTIC_UNITS else None
