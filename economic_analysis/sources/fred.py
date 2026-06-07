from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from io import StringIO
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests

from economic_analysis.config import Settings
from economic_analysis.io import utc_now_iso, write_text

FRED_GRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_BASE_URL = "https://fred.stlouisfed.org"
INDEED_SECTOR_TABLE_URL = "https://fred.stlouisfed.org/release/tables?eid=1233635&rid=476"
INDEED_JOB_POSTINGS_UNIT = "index Feb, 1 2020=100"
INDEED_JOB_POSTINGS_NOTES = (
    "Indeed 7-day job-postings index, set to 100 on February 1, 2020. "
    "FRED/Indeed data are copyrighted and require pre-approval for redistribution."
)
INDEED_US_SECTOR_TITLE_RE = re.compile(r"^(?P<sector>.+) Job Postings on Indeed in the United States$")
EXCLUDED_INDEED_SECTORS = {"New"}


@dataclass(frozen=True)
class FredSeriesInfo:
    title: str
    measure: str
    unit: str
    frequency: str
    seasonality: str
    source: str
    is_proxy: bool
    notes: str


@dataclass(frozen=True)
class FredIndeedJobPostingsSeries:
    series_id: str
    title: str
    measure: str
    series_group: str
    country: str
    state_code: str | None
    state_name: str | None
    sector_occupation: str | None
    series_status: str


SELECTED_INDEED_STATE_SERIES: dict[str, tuple[str, str]] = {
    "MA": ("IHLIDXUSMA", "Massachusetts"),
    "NJ": ("IHLIDXUSNJ", "New Jersey"),
    "NY": ("IHLIDXUSNY", "New York"),
    "CA": ("IHLIDXUSCA", "California"),
    "WA": ("IHLIDXUSWA", "Washington"),
    "TX": ("IHLIDXUSTX", "Texas"),
    "FL": ("IHLIDXUSFL", "Florida"),
}


FRED_SERIES: dict[str, FredSeriesInfo] = {
    "LEU0254477200A": FredSeriesInfo(
        title=(
            "Employed full time: Wage and salary workers: Software developers, applications and systems software "
            "occupations: 16 years and over"
        ),
        measure="software_developers_employed_full_time",
        unit="thousands of persons",
        frequency="annual",
        seasonality="not_seasonally_adjusted",
        source="U.S. Bureau of Labor Statistics via FRED",
        is_proxy=False,
        notes="Exact software-developer occupation series; latest observations stop at 2019 in FRED.",
    ),
    "LEU0254476900A": FredSeriesInfo(
        title="Employed full time: Wage and salary workers: Computer and mathematical occupations: 16 years and over",
        measure="computer_mathematical_employed_full_time_proxy",
        unit="thousands of persons",
        frequency="annual",
        seasonality="not_seasonally_adjusted",
        source="U.S. Bureau of Labor Statistics via FRED",
        is_proxy=True,
        notes="Broader current proxy for SWE employment because the exact software-developer series is stale.",
    ),
    "IHLIDXUSTPSOFTDEVE": FredSeriesInfo(
        title="Software Development Job Postings on Indeed in the United States",
        measure="software_development_job_postings_index",
        unit="index Feb, 1 2020=100",
        frequency="daily_7_day",
        seasonality="seasonally_adjusted",
        source="Indeed via FRED",
        is_proxy=False,
        notes="Indeed 7-day job-postings index for software development.",
    ),
    "IHLIDXUS": FredSeriesInfo(
        title="Job Postings on Indeed in the United States",
        measure="general_job_postings_index",
        unit="index Feb, 1 2020=100",
        frequency="daily_7_day",
        seasonality="seasonally_adjusted",
        source="Indeed via FRED",
        is_proxy=False,
        notes="Seasonally adjusted Indeed 7-day national job-postings index.",
    ),
}

CONSUMER_SENTIMENT_SERIES: dict[str, FredSeriesInfo] = {
    "UMCSENT": FredSeriesInfo(
        title="University of Michigan: Consumer Sentiment",
        measure="consumer_sentiment_index",
        unit="index 1966:Q1=100",
        frequency="monthly",
        seasonality="not_seasonally_adjusted",
        source="University of Michigan via FRED",
        is_proxy=False,
        notes="Monthly University of Michigan consumer sentiment index distributed through FRED.",
    ),
}

OIL_ENERGY_PRICE_SERIES: dict[str, FredSeriesInfo] = {
    "MCOILWTICO": FredSeriesInfo(
        title="Crude Oil Prices: West Texas Intermediate (WTI) - Cushing, Oklahoma",
        measure="wti_crude_oil_price",
        unit="dollars_per_barrel",
        frequency="monthly",
        seasonality="not_seasonally_adjusted",
        source="U.S. Energy Information Administration via FRED",
        is_proxy=False,
        notes="Monthly WTI crude oil spot price used as the oil scenario anchor.",
    ),
    "GASREGW": FredSeriesInfo(
        title="US Regular All Formulations Gas Price",
        measure="regular_gasoline_price",
        unit="dollars_per_gallon",
        frequency="weekly",
        seasonality="not_seasonally_adjusted",
        source="U.S. Energy Information Administration via FRED",
        is_proxy=False,
        notes="Weekly U.S. regular retail gasoline price used to estimate oil-to-gasoline pass-through.",
    ),
}

INDEED_COPYRIGHT_NOTE = (
    "Indeed job-postings data in FRED are copyrighted and require pre-approval for redistribution. "
    "Use only in line with the FRED/Indeed series notes."
)


def fred_csv_url(series_id: str) -> str:
    return f"{FRED_GRAPH_CSV_URL}?id={series_id}"


def normalize_series(csv_text: str, series_id: str, info: FredSeriesInfo | None = None) -> pd.DataFrame:
    info = info or FRED_SERIES[series_id]
    raw = pd.read_csv(StringIO(csv_text))
    date_column, value_column = _csv_columns(raw, series_id)

    frame = raw[[date_column, value_column]].rename(columns={date_column: "date", value_column: "value"}).copy()
    frame["value"] = pd.to_numeric(frame["value"].replace(".", pd.NA), errors="coerce")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date.astype(str)
    frame = frame[frame["date"] != "NaT"].copy()

    frame["series_id"] = series_id
    frame["measure"] = info.measure
    frame["unit"] = info.unit
    frame["frequency"] = info.frequency
    frame["seasonality"] = info.seasonality
    frame["source"] = info.source
    frame["is_proxy"] = info.is_proxy
    frame["series_title"] = info.title
    frame["notes"] = info.notes

    return frame[
        [
            "date",
            "series_id",
            "measure",
            "value",
            "unit",
            "frequency",
            "seasonality",
            "source",
            "is_proxy",
            "series_title",
            "notes",
        ]
    ].sort_values(["series_id", "date"]).reset_index(drop=True)


def fetch_swe_labor_market(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    return _fetch_series_dataset(
        settings,
        FRED_SERIES,
        copyright_notes={"indeed": INDEED_COPYRIGHT_NOTE},
    )


def fetch_consumer_sentiment(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    return _fetch_series_dataset(settings, CONSUMER_SENTIMENT_SERIES)


def fetch_oil_energy_prices(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    return _fetch_series_dataset(settings, OIL_ENERGY_PRICE_SERIES, timeout=120)


def fetch_indeed_job_postings(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    response = requests.get(INDEED_SECTOR_TABLE_URL, timeout=60)
    response.raise_for_status()
    release_table_html = response.text

    raw_dir = settings.data_dir / "raw" / "fred" / "indeed_job_postings"
    release_table_raw_path = raw_dir / "sector_release_table.html"
    write_text(release_table_raw_path, release_table_html)

    sector_series = discover_us_indeed_sector_series(release_table_html)
    state_series = selected_indeed_state_series()
    series_infos = {series.series_id: series for series in [*sector_series, *state_series]}

    raw_paths: dict[str, Any] = {
        "sector_release_table": str(release_table_raw_path),
        "series": {},
    }
    source_urls: dict[str, Any] = {
        "sector_release_table": INDEED_SECTOR_TABLE_URL,
        "series": {},
    }
    frames: list[pd.DataFrame] = []

    for series_id, series in series_infos.items():
        url = fred_csv_url(series_id)
        series_response = requests.get(url, timeout=60)
        series_response.raise_for_status()

        raw_path = raw_dir / f"{series_id}.csv"
        write_text(raw_path, series_response.text)
        raw_paths["series"][series_id] = str(raw_path)
        source_urls["series"][series_id] = url

        info = FredSeriesInfo(
            title=series.title,
            measure=series.measure,
            unit=INDEED_JOB_POSTINGS_UNIT,
            frequency="daily_7_day",
            seasonality="seasonally_adjusted",
            source="Indeed via FRED",
            is_proxy=False,
            notes=INDEED_JOB_POSTINGS_NOTES,
        )
        frame = normalize_series(series_response.text, series_id, info)
        frame["series_group"] = series.series_group
        frame["country"] = series.country
        frame["state_code"] = series.state_code
        frame["state_name"] = series.state_name
        frame["sector_occupation"] = series.sector_occupation
        frame["series_status"] = series.series_status
        frames.append(frame)

    frame = pd.concat(frames, ignore_index=True) if frames else _empty_indeed_job_postings_frame()
    if not frame.empty:
        frame = frame.sort_values(["series_group", "series_id", "date"]).reset_index(drop=True)
        frame = frame[_indeed_job_postings_columns()]

    metadata = {
        "source": "FRED, Federal Reserve Bank of St. Louis",
        "source_urls": source_urls,
        "raw_paths": raw_paths,
        "fetched_at": utc_now_iso(),
        "frequency": ["daily_7_day"],
        "units": [INDEED_JOB_POSTINGS_UNIT],
        "method": (
            "Downloaded the active FRED Indeed sector release table, discovered current U.S. sector/occupation "
            "series, added selected U.S. state series, stored raw CSVs, and normalized to long rows."
        ),
        "discovery_url": INDEED_SECTOR_TABLE_URL,
        "selected_states": {
            state_code: {"series_id": series_id, "state_name": state_name}
            for state_code, (series_id, state_name) in SELECTED_INDEED_STATE_SERIES.items()
        },
        "series": {series_id: series.__dict__ for series_id, series in series_infos.items()},
        "copyright_notes": {"indeed": INDEED_COPYRIGHT_NOTE},
    }
    return frame, metadata


def discover_us_indeed_sector_series(release_table_html: str) -> list[FredIndeedJobPostingsSeries]:
    parser = _FredReleaseSeriesLinkParser()
    parser.feed(release_table_html)

    series: dict[str, FredIndeedJobPostingsSeries] = {}
    for href, title in parser.series_links:
        if "DISCONTINUED" in title.upper():
            continue
        match = INDEED_US_SECTOR_TITLE_RE.match(title)
        if not match:
            continue

        sector = match.group("sector").strip()
        if sector in EXCLUDED_INDEED_SECTORS:
            continue

        series_id = _series_id_from_href(href)
        if not series_id:
            continue

        series[series_id] = FredIndeedJobPostingsSeries(
            series_id=series_id,
            title=title,
            measure=f"indeed_us_{_slugify(sector)}_job_postings_index",
            series_group="sector_occupation",
            country="United States",
            state_code=None,
            state_name=None,
            sector_occupation=sector,
            series_status="active",
        )

    return sorted(series.values(), key=lambda item: (item.sector_occupation or "", item.series_id))


def selected_indeed_state_series() -> list[FredIndeedJobPostingsSeries]:
    return [
        FredIndeedJobPostingsSeries(
            series_id=series_id,
            title=f"Job Postings on Indeed in {state_name}",
            measure=f"indeed_us_{state_code.lower()}_job_postings_index",
            series_group="state",
            country="United States",
            state_code=state_code,
            state_name=state_name,
            sector_occupation=None,
            series_status="active",
        )
        for state_code, (series_id, state_name) in SELECTED_INDEED_STATE_SERIES.items()
    ]


def _fetch_series_dataset(
    settings: Settings,
    series_infos: dict[str, FredSeriesInfo],
    copyright_notes: dict[str, str] | None = None,
    timeout: int = 60,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw_paths: dict[str, str] = {}
    source_urls: dict[str, str] = {}
    frames: list[pd.DataFrame] = []

    for series_id, info in series_infos.items():
        url = fred_csv_url(series_id)
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        raw_path = settings.data_dir / "raw" / "fred" / f"{series_id}.csv"
        write_text(raw_path, response.text)
        raw_paths[series_id] = str(raw_path)
        source_urls[series_id] = url
        frames.append(normalize_series(response.text, series_id, info))

    frame = pd.concat(frames, ignore_index=True) if frames else _empty_frame()
    if not frame.empty:
        frame = frame.sort_values(["series_id", "date"]).reset_index(drop=True)

    metadata = {
        "source": "FRED, Federal Reserve Bank of St. Louis",
        "source_urls": source_urls,
        "raw_paths": raw_paths,
        "fetched_at": utc_now_iso(),
        "frequency": sorted({info.frequency for info in series_infos.values()}),
        "units": sorted({info.unit for info in series_infos.values()}),
        "method": "Downloaded selected FRED graph CSV series, stored raw CSVs, and normalized to long rows.",
        "series": {series_id: info.__dict__ for series_id, info in series_infos.items()},
    }
    if copyright_notes:
        metadata["copyright_notes"] = copyright_notes
    return frame, metadata


def _csv_columns(frame: pd.DataFrame, series_id: str) -> tuple[str, str]:
    if "observation_date" in frame.columns:
        date_column = "observation_date"
    elif "DATE" in frame.columns:
        date_column = "DATE"
    else:
        raise ValueError("FRED CSV is missing an observation date column")

    if series_id in frame.columns:
        value_column = series_id
    elif "VALUE" in frame.columns:
        value_column = "VALUE"
    else:
        candidates = [column for column in frame.columns if column != date_column]
        if len(candidates) != 1:
            raise ValueError(f"FRED CSV is missing a value column for {series_id}")
        value_column = candidates[0]

    return date_column, value_column


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "date",
            "series_id",
            "measure",
            "value",
            "unit",
            "frequency",
            "seasonality",
            "source",
            "is_proxy",
            "series_title",
            "notes",
        ]
    )


def _empty_indeed_job_postings_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=_indeed_job_postings_columns())


def _indeed_job_postings_columns() -> list[str]:
    return [
        *_empty_frame().columns.tolist(),
        "series_group",
        "country",
        "state_code",
        "state_name",
        "sector_occupation",
        "series_status",
    ]


def _series_id_from_href(href: str) -> str | None:
    prefix = "/series/"
    if prefix not in href:
        return None
    return urljoin(FRED_BASE_URL, href).rstrip("/").rsplit("/", maxsplit=1)[-1]


def _slugify(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_")


class _FredReleaseSeriesLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.series_links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href and "/series/" in href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._current_href:
            return
        title = " ".join("".join(self._current_text).split())
        if title:
            self.series_links.append((self._current_href, title))
        self._current_href = None
        self._current_text = []
