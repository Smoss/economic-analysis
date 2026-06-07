from __future__ import annotations

import csv
import zipfile
from collections.abc import Iterable
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from economic_analysis.config import Settings
from economic_analysis.io import utc_now_iso, write_text

ACS_PUMS_YEAR_START = 2015
ACS_PUMS_YEAR_END = 2024
ACS_PUMS_YEARS = tuple(range(ACS_PUMS_YEAR_START, ACS_PUMS_YEAR_END + 1))
ACS_PUMS_SOURCE_ROOT = "https://www2.census.gov/programs-surveys/acs"
ACS_PUMS_CHUNKSIZE = 200_000

PERSON_COLUMNS = ["AGEP", "SCHL", "ESR", "FOD1P", "PWGTP"]
EMPLOYED_ESR_CODES = {"1", "2", "4", "5"}
RECENT_GRAD_MIN_AGE = 22
RECENT_GRAD_MAX_AGE = 27
BACHELORS_OR_HIGHER_SCHL_MIN = 21
LATEST_STANDARD_LABEL_YEAR = 2024


def fetch_major_employment(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw_dir = settings.data_dir / "raw" / "census_acs_pums"
    raw_dir.mkdir(parents=True, exist_ok=True)

    major_labels = _fetch_fod_labels(raw_dir)

    yearly_frames: list[pd.DataFrame] = []
    raw_paths: list[str] = []
    source_urls: dict[str, str] = {}
    for year in ACS_PUMS_YEARS:
        url = build_person_zip_url(year)
        raw_path = raw_dir / f"acs_{year}_1yr_pums_person_us.zip"
        _download_file(url, raw_path)
        raw_paths.append(str(raw_path))
        source_urls[str(year)] = url
        yearly_frames.append(normalize_person_zip(raw_path, year, major_labels))

    frame = _combine_yearly_frames(yearly_frames)
    metadata = {
        "source": "U.S. Census Bureau American Community Survey 1-year PUMS person records",
        "source_url": source_urls,
        "api_params": {
            "years": list(ACS_PUMS_YEARS),
            "columns": PERSON_COLUMNS,
            "filters": {
                "age": [RECENT_GRAD_MIN_AGE, RECENT_GRAD_MAX_AGE],
                "education": "SCHL >= 21, bachelor's degree or higher",
                "major": "FOD1P nonblank",
            },
            "employed_esr_codes": sorted(EMPLOYED_ESR_CODES),
        },
        "raw_paths": raw_paths,
        "label_metadata_raw_path": str(raw_dir / f"pums_data_dictionary_{LATEST_STANDARD_LABEL_YEAR}.csv"),
        "fetched_at": utc_now_iso(),
        "frequency": "annual",
        "units": ["persons", "share"],
        "method": (
            "Weighted employment-to-population rate by ACS bachelor's field of degree for ages 22-27 with a "
            "bachelor's degree or higher. 2020 uses the Census experimental ACS 1-year PUMS release."
        ),
        "release_notes": [
            "The Census Bureau did not release a standard 2020 ACS 1-year PUMS; this pipeline uses the experimental "
            "2020 release to preserve a continuous 2015-2024 calendar-year series."
        ],
    }
    return frame, metadata


def build_person_zip_url(year: int) -> str:
    if year == 2020:
        return f"{ACS_PUMS_SOURCE_ROOT}/experimental/2020/data/pums/1-Year/csv_pus.zip"
    return f"{ACS_PUMS_SOURCE_ROOT}/data/pums/{year}/1-Year/csv_pus.zip"


def build_fod_label_url(year: int = LATEST_STANDARD_LABEL_YEAR) -> str:
    return f"{ACS_PUMS_SOURCE_ROOT}/tech_docs/pums/data_dict/PUMS_Data_Dictionary_{year}.csv"


def normalize_person_zip(raw_path: Path, year: int, major_labels: dict[str, str] | None = None) -> pd.DataFrame:
    yearly_chunks: list[pd.DataFrame] = []
    with zipfile.ZipFile(raw_path) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".csv"):
                continue
            with archive.open(name) as member:
                for chunk in pd.read_csv(
                    member,
                    usecols=PERSON_COLUMNS,
                    dtype={column: "string" for column in PERSON_COLUMNS},
                    chunksize=ACS_PUMS_CHUNKSIZE,
                    low_memory=False,
                ):
                    normalized = normalize_person_records(chunk, year, major_labels)
                    if not normalized.empty:
                        yearly_chunks.append(normalized)
    return _combine_yearly_frames(yearly_chunks)


def normalize_person_records(
    records: pd.DataFrame, year: int, major_labels: dict[str, str] | None = None
) -> pd.DataFrame:
    frame = records.copy()
    for column in PERSON_COLUMNS:
        if column not in frame.columns:
            raise ValueError(f"missing required ACS PUMS column: {column}")

    frame["age"] = pd.to_numeric(frame["AGEP"], errors="coerce")
    frame["education_code"] = pd.to_numeric(frame["SCHL"], errors="coerce")
    frame["person_weight"] = pd.to_numeric(frame["PWGTP"], errors="coerce")
    frame["major_code"] = frame["FOD1P"].map(_clean_major_code)
    frame["employment_status_code"] = frame["ESR"].astype("string").str.strip()

    eligible = frame[
        frame["age"].between(RECENT_GRAD_MIN_AGE, RECENT_GRAD_MAX_AGE)
        & (frame["education_code"] >= BACHELORS_OR_HIGHER_SCHL_MIN)
        & frame["major_code"].notna()
        & frame["person_weight"].notna()
    ].copy()
    if eligible.empty:
        return _empty_major_employment_frame()

    eligible["weighted_population"] = eligible["person_weight"].astype(float)
    eligible["weighted_employed"] = eligible["weighted_population"].where(
        eligible["employment_status_code"].isin(EMPLOYED_ESR_CODES),
        0.0,
    )
    grouped = (
        eligible.groupby("major_code", as_index=False)
        .agg(
            weighted_population=("weighted_population", "sum"),
            weighted_employed=("weighted_employed", "sum"),
            unweighted_records=("major_code", "size"),
        )
        .assign(year=year)
    )
    grouped["employment_rate"] = grouped["weighted_employed"] / grouped["weighted_population"]
    grouped["major_label"] = grouped["major_code"].map(major_labels or {})
    grouped["age_group"] = f"{RECENT_GRAD_MIN_AGE}-{RECENT_GRAD_MAX_AGE}"
    grouped["degree_scope"] = "bachelor_or_higher"
    grouped["unit"] = "share"
    return grouped[
        [
            "year",
            "age_group",
            "degree_scope",
            "major_code",
            "major_label",
            "weighted_population",
            "weighted_employed",
            "employment_rate",
            "unweighted_records",
            "unit",
        ]
    ].sort_values(["year", "major_code"], ignore_index=True)


def normalize_fod_labels(raw: str | dict[str, Any]) -> dict[str, str]:
    if isinstance(raw, dict):
        values = raw.get("values", {})
        items = values.get("item", {}) if isinstance(values, dict) else {}
        if not isinstance(items, dict):
            return {}
        return {
            major_code: str(label)
            for raw_code, label in items.items()
            if (major_code := _clean_major_code(raw_code)) is not None and str(label).strip()
        }

    labels: dict[str, str] = {}
    for row in csv.reader(StringIO(raw)):
        if len(row) < 7 or row[0] != "VAL" or row[1] != "FOD1P":
            continue
        major_code = _clean_major_code(row[4])
        label = row[6].strip()
        if major_code is not None and label:
            labels[major_code] = label
    return labels


def _combine_yearly_frames(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    nonempty = [frame for frame in frames if not frame.empty]
    if not nonempty:
        return _empty_major_employment_frame()
    combined = pd.concat(nonempty, ignore_index=True)
    grouped = (
        combined.groupby(["year", "age_group", "degree_scope", "major_code"], as_index=False)
        .agg(
            major_label=("major_label", "first"),
            weighted_population=("weighted_population", "sum"),
            weighted_employed=("weighted_employed", "sum"),
            unweighted_records=("unweighted_records", "sum"),
            unit=("unit", "first"),
        )
        .sort_values(["year", "major_code"], ignore_index=True)
    )
    grouped["employment_rate"] = grouped["weighted_employed"] / grouped["weighted_population"]
    return grouped[
        [
            "year",
            "age_group",
            "degree_scope",
            "major_code",
            "major_label",
            "weighted_population",
            "weighted_employed",
            "employment_rate",
            "unweighted_records",
            "unit",
        ]
    ]


def _fetch_fod_labels(raw_dir: Path) -> dict[str, str]:
    url = build_fod_label_url()
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    write_text(raw_dir / f"pums_data_dictionary_{LATEST_STANDARD_LABEL_YEAR}.csv", response.text)
    return normalize_fod_labels(response.text)


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def _clean_major_code(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "bbbb", "bbbbb"}:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(4)


def _empty_major_employment_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "year",
            "age_group",
            "degree_scope",
            "major_code",
            "major_label",
            "weighted_population",
            "weighted_employed",
            "employment_rate",
            "unweighted_records",
            "unit",
        ]
    )
