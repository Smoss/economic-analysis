from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any
from zipfile import ZipFile

import pandas as pd
import requests

from economic_analysis.config import Settings
from economic_analysis.io import ensure_dir, utc_now_iso

BLS_OEWS_NATIONAL_URL_TEMPLATE = "https://www.bls.gov/oes/special-requests/oesm{year_short:02d}nat.zip"
BLS_OEWS_START_YEAR = 2016
BLS_OEWS_HEADERS = {"User-Agent": "economic-analysis reproducible data pipeline (https://www.bls.gov/oes/)"}

ALL_OCCUPATIONS_CODE = "00-0000"
LEGACY_SOFTWARE_DEVELOPER_CODES = ("15-1132", "15-1133")
SOFTWARE_DEVELOPERS_CODE = "15-1252"
SOFTWARE_DEVELOPERS_QA_PROXY_CODE = "15-1256"
SELECTED_OCCUPATION_CODES = (
    ALL_OCCUPATIONS_CODE,
    *LEGACY_SOFTWARE_DEVELOPER_CODES,
    SOFTWARE_DEVELOPERS_CODE,
    SOFTWARE_DEVELOPERS_QA_PROXY_CODE,
)


@dataclass(frozen=True)
class OewsRawFile:
    year: int
    source_url: str
    raw_path: str


def oews_years(start_year: int = BLS_OEWS_START_YEAR, end_year: int | None = None) -> list[int]:
    end_year = end_year or max(2025, pd.Timestamp.utcnow().year - 1)
    if start_year > end_year:
        raise ValueError("start_year must be less than or equal to end_year")
    return list(range(start_year, end_year + 1))


def oews_national_url(year: int) -> str:
    return BLS_OEWS_NATIONAL_URL_TEMPLATE.format(year_short=year % 100)


def fetch_swe_employment(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw_files: list[OewsRawFile] = []
    frames: list[pd.DataFrame] = []

    for year in oews_years():
        url = oews_national_url(year)
        response = requests.get(url, headers=BLS_OEWS_HEADERS, timeout=60)
        response.raise_for_status()

        raw_dir = settings.data_dir / "raw" / "bls" / "oews"
        ensure_dir(raw_dir)
        raw_path = raw_dir / f"national_{year}.zip"
        raw_path.write_bytes(response.content)

        raw_files.append(OewsRawFile(year=year, source_url=url, raw_path=str(raw_path)))
        frames.append(normalize_oews_year(read_national_zip(response.content), year))

    frame = pd.concat(frames, ignore_index=True) if frames else _empty_frame()
    if not frame.empty:
        frame = frame.sort_values(["measure", "date", "soc_code"]).reset_index(drop=True)

    metadata = {
        "source": "BLS Occupational Employment and Wage Statistics national estimates",
        "source_url_template": BLS_OEWS_NATIONAL_URL_TEMPLATE,
        "raw_paths": {str(raw.year): raw.raw_path for raw in raw_files},
        "source_urls": {str(raw.year): raw.source_url for raw in raw_files},
        "fetched_at": utc_now_iso(),
        "frequency": "annual",
        "units": ["employees"],
        "method": (
            "Downloaded annual BLS OEWS national ZIP files, retained all-occupations and software-developer SOC "
            "rows, and created a harmonized SWE employment row across SOC changes."
        ),
        "selected_occupation_codes": list(SELECTED_OCCUPATION_CODES),
        "soc_harmonization": {
            "2016_2019_exact": (
                "Sum 15-1132 Software Developers, Applications and 15-1133 Software Developers, Systems Software "
                "when 15-1252 is unavailable."
            ),
            "current_exact": "Use 15-1252 Software Developers when available.",
            "proxy_fallback": (
                "Use 15-1256 Software Developers and Software Quality Assurance Analysts and Testers only if exact "
                "software-developer rows are unavailable."
            ),
        },
    }
    return frame, metadata


def read_national_zip(content: bytes) -> pd.DataFrame:
    with ZipFile(BytesIO(content)) as archive:
        member = _national_member_name(archive)
        with archive.open(member) as file:
            suffix = member.rsplit(".", maxsplit=1)[-1].lower()
            if suffix in {"xlsx", "xls"}:
                return pd.read_excel(file)
            if suffix in {"txt", "csv"}:
                return pd.read_csv(file, sep=None, engine="python")
    raise ValueError("Unsupported OEWS national file")


def normalize_oews_year(raw: pd.DataFrame, year: int) -> pd.DataFrame:
    frame = raw.rename(columns={column: str(column).strip().lower() for column in raw.columns}).copy()
    required = {"occ_code", "occ_title", "tot_emp"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"OEWS file is missing required columns: {sorted(missing)}")

    selected = frame[frame["occ_code"].astype("string").isin(SELECTED_OCCUPATION_CODES)].copy()
    selected["employment"] = selected["tot_emp"].map(_parse_employment)
    selected = selected.dropna(subset=["employment"])

    rows: list[dict[str, Any]] = []
    for row in selected.itertuples(index=False):
        soc_code = str(row.occ_code).strip()
        occupation_title = str(row.occ_title).strip()
        employment = float(row.employment)
        rows.append(
            {
                "date": f"{year}-05-01",
                "year": year,
                "soc_code": soc_code,
                "occupation_title": occupation_title,
                "measure": _component_measure(soc_code),
                "value": employment,
                "unit": "employees",
                "frequency": "annual",
                "source": "BLS OEWS",
                "is_proxy": soc_code == SOFTWARE_DEVELOPERS_QA_PROXY_CODE,
                "method": "published_oews_row",
            }
        )

    aggregate = _software_developer_aggregate(selected, year)
    if aggregate:
        rows.append(aggregate)

    if not rows:
        return _empty_frame()
    return pd.DataFrame(rows, columns=_empty_frame().columns)


def _national_member_name(archive: ZipFile) -> str:
    candidates = [
        name
        for name in archive.namelist()
        if not name.endswith("/") and name.rsplit(".", maxsplit=1)[-1].lower() in {"xlsx", "xls", "txt", "csv"}
    ]
    if not candidates:
        raise ValueError("OEWS ZIP does not contain a readable data file")
    data_candidates = [
        name
        for name in candidates
        if "field_description" not in name.lower() and ("national" in name.lower() or "nat" in name.lower())
    ]
    if data_candidates:
        return sorted(data_candidates)[0]
    return sorted(candidates)[0]


def _parse_employment(value: Any) -> float | None:
    if pd.isna(value):
        return None
    cleaned = str(value).replace(",", "").strip()
    if cleaned in {"", "*", "**", "#"}:
        return None
    parsed = pd.to_numeric(cleaned, errors="coerce")
    if pd.isna(parsed):
        return None
    return float(parsed)


def _component_measure(soc_code: str) -> str:
    if soc_code == ALL_OCCUPATIONS_CODE:
        return "all_occupations_employment"
    if soc_code == SOFTWARE_DEVELOPERS_CODE:
        return "software_developers_employment_component"
    if soc_code == SOFTWARE_DEVELOPERS_QA_PROXY_CODE:
        return "software_developers_qa_employment_proxy_component"
    return "legacy_software_developers_employment_component"


def _software_developer_aggregate(selected: pd.DataFrame, year: int) -> dict[str, Any] | None:
    exact = selected[selected["occ_code"].astype("string") == SOFTWARE_DEVELOPERS_CODE]
    if not exact.empty:
        row = exact.iloc[0]
        return _aggregate_row(
            year=year,
            soc_code=SOFTWARE_DEVELOPERS_CODE,
            occupation_title="Software Developers",
            value=float(row["employment"]),
            is_proxy=False,
            method="published_oews_row",
        )

    legacy = selected[selected["occ_code"].astype("string").isin(LEGACY_SOFTWARE_DEVELOPER_CODES)]
    if not legacy.empty:
        return _aggregate_row(
            year=year,
            soc_code="+".join(LEGACY_SOFTWARE_DEVELOPER_CODES),
            occupation_title="Software Developers, Applications + Systems Software",
            value=float(legacy["employment"].sum()),
            is_proxy=False,
            method="sum_legacy_applications_and_systems_software_rows",
        )

    proxy = selected[selected["occ_code"].astype("string") == SOFTWARE_DEVELOPERS_QA_PROXY_CODE]
    if not proxy.empty:
        row = proxy.iloc[0]
        return _aggregate_row(
            year=year,
            soc_code=SOFTWARE_DEVELOPERS_QA_PROXY_CODE,
            occupation_title="Software Developers and Software Quality Assurance Analysts and Testers",
            value=float(row["employment"]),
            is_proxy=True,
            method="proxy_published_combined_software_developers_and_qa_row",
        )
    return None


def _aggregate_row(
    year: int, soc_code: str, occupation_title: str, value: float, is_proxy: bool, method: str
) -> dict[str, Any]:
    return {
        "date": f"{year}-05-01",
        "year": year,
        "soc_code": soc_code,
        "occupation_title": occupation_title,
        "measure": "software_developers_employment",
        "value": value,
        "unit": "employees",
        "frequency": "annual",
        "source": "BLS OEWS",
        "is_proxy": is_proxy,
        "method": method,
    }


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "date",
            "year",
            "soc_code",
            "occupation_title",
            "measure",
            "value",
            "unit",
            "frequency",
            "source",
            "is_proxy",
            "method",
        ]
    )
