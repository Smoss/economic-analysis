import json

from economic_analysis.config import Settings
from economic_analysis.sources import fred
from economic_analysis.sources.fred import FredSeriesInfo, normalize_series


def test_normalize_annual_employment_series():
    csv_text = "observation_date,LEU0254477200A\n2018-01-01,1611\n2019-01-01,1714\n"

    frame = normalize_series(csv_text, "LEU0254477200A")

    assert list(frame["date"]) == ["2018-01-01", "2019-01-01"]
    assert list(frame["value"]) == [1611, 1714]
    assert frame.loc[0, "measure"] == "software_developers_employed_full_time"
    assert frame.loc[0, "unit"] == "thousands of persons"
    assert frame.loc[0, "frequency"] == "annual"
    assert frame.loc[0, "seasonality"] == "not_seasonally_adjusted"
    assert bool(frame.loc[0, "is_proxy"]) is False


def test_normalize_daily_postings_series_with_missing_value():
    csv_text = "observation_date,IHLIDXUSTPSOFTDEVE\n2026-04-30,71.81\n2026-05-01,.\n"

    frame = normalize_series(csv_text, "IHLIDXUSTPSOFTDEVE")

    assert list(frame["date"]) == ["2026-04-30", "2026-05-01"]
    assert frame.loc[0, "value"] == 71.81
    assert frame.loc[1, "value"] != frame.loc[1, "value"]
    assert frame.loc[0, "measure"] == "software_development_job_postings_index"
    assert frame.loc[0, "frequency"] == "daily_7_day"
    assert frame.loc[0, "seasonality"] == "seasonally_adjusted"


def test_fetch_swe_labor_market_writes_raw_files_and_metadata(monkeypatch, tmp_path):
    series = {
        "EXACT": FredSeriesInfo(
            title="Exact SWE count",
            measure="exact_swe_count",
            unit="thousands of persons",
            frequency="annual",
            seasonality="not_seasonally_adjusted",
            source="BLS via FRED",
            is_proxy=False,
            notes="Exact series.",
        ),
        "POSTINGS": FredSeriesInfo(
            title="SWE postings",
            measure="swe_postings",
            unit="index Feb, 1 2020=100",
            frequency="daily_7_day",
            seasonality="seasonally_adjusted",
            source="Indeed via FRED",
            is_proxy=False,
            notes="Posting series.",
        ),
    }
    csv_by_id = {
        "EXACT": "observation_date,EXACT\n2019-01-01,1714\n",
        "POSTINGS": "observation_date,POSTINGS\n2026-05-01,72.15\n",
    }
    gets: list[str] = []

    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int) -> FakeResponse:
        assert timeout == 60
        series_id = url.rsplit("=", maxsplit=1)[1]
        gets.append(series_id)
        return FakeResponse(csv_by_id[series_id])

    monkeypatch.setattr(fred, "FRED_SERIES", series)
    monkeypatch.setattr(fred, "requests", type("Requests", (), {"get": staticmethod(fake_get)}))

    settings = Settings(data_dir=tmp_path, bea_api_key=None, bls_api_key=None)
    frame, metadata = fred.fetch_swe_labor_market(settings)

    assert gets == ["EXACT", "POSTINGS"]
    assert list(frame["series_id"]) == ["EXACT", "POSTINGS"]
    assert list(frame["value"]) == [1714.0, 72.15]
    assert (tmp_path / "raw" / "fred" / "EXACT.csv").read_text() == csv_by_id["EXACT"]
    assert (tmp_path / "raw" / "fred" / "POSTINGS.csv").read_text() == csv_by_id["POSTINGS"]
    assert metadata["source"] == "FRED, Federal Reserve Bank of St. Louis"
    assert set(metadata["raw_paths"]) == {"EXACT", "POSTINGS"}
    assert metadata["series"]["EXACT"]["measure"] == "exact_swe_count"
    json.dumps(metadata)


def test_fetch_consumer_sentiment_writes_raw_file_and_metadata(monkeypatch, tmp_path):
    csv_text = "observation_date,UMCSENT\n2020-01-01,99.8\n2020-02-01,101.0\n"
    gets: list[str] = []

    class FakeResponse:
        text = csv_text

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int) -> FakeResponse:
        assert timeout == 60
        gets.append(url.rsplit("=", maxsplit=1)[1])
        return FakeResponse()

    monkeypatch.setattr(fred, "requests", type("Requests", (), {"get": staticmethod(fake_get)}))

    settings = Settings(data_dir=tmp_path, bea_api_key=None, bls_api_key=None)
    frame, metadata = fred.fetch_consumer_sentiment(settings)

    assert gets == ["UMCSENT"]
    assert list(frame["series_id"]) == ["UMCSENT", "UMCSENT"]
    assert list(frame["value"]) == [99.8, 101.0]
    assert frame.loc[0, "measure"] == "consumer_sentiment_index"
    assert frame.loc[0, "frequency"] == "monthly"
    assert (tmp_path / "raw" / "fred" / "UMCSENT.csv").read_text() == csv_text
    assert metadata["series"]["UMCSENT"]["source"] == "University of Michigan via FRED"
    json.dumps(metadata)


def test_fetch_oil_energy_prices_writes_raw_files_and_metadata(monkeypatch, tmp_path):
    csv_by_id = {
        "MCOILWTICO": "observation_date,MCOILWTICO\n2024-01-01,72.1\n",
        "GASREGW": "observation_date,GASREGW\n2024-01-01,3.08\n",
    }
    gets: list[str] = []

    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int) -> FakeResponse:
        assert timeout == 120
        series_id = url.rsplit("=", maxsplit=1)[1]
        gets.append(series_id)
        return FakeResponse(csv_by_id[series_id])

    monkeypatch.setattr(fred, "requests", type("Requests", (), {"get": staticmethod(fake_get)}))

    settings = Settings(data_dir=tmp_path, bea_api_key=None, bls_api_key=None)
    frame, metadata = fred.fetch_oil_energy_prices(settings)

    assert gets == ["MCOILWTICO", "GASREGW"]
    assert set(frame["measure"]) == {"wti_crude_oil_price", "regular_gasoline_price"}
    assert (tmp_path / "raw" / "fred" / "MCOILWTICO.csv").read_text() == csv_by_id["MCOILWTICO"]
    assert (tmp_path / "raw" / "fred" / "GASREGW.csv").read_text() == csv_by_id["GASREGW"]
    assert metadata["series"]["MCOILWTICO"]["unit"] == "dollars_per_barrel"
    assert metadata["series"]["GASREGW"]["unit"] == "dollars_per_gallon"
    json.dumps(metadata)


def test_discover_us_indeed_sector_series_excludes_non_us_aggregate_and_discontinued():
    html = """
    <a href="/series/IHLIDXUSTPACCT">Accounting Job Postings on Indeed in the United States</a>
    <a href="/series/IHLIDXUSTPSOFTDEVE">Software Development Job Postings on Indeed in the United States</a>
    <a href="/series/IHLIDXCATPSOFTDEVE">Software Development Job Postings on Indeed in Canada</a>
    <a href="/series/IHLIDXUSNEW">New Job Postings on Indeed in the United States</a>
    <a href="/series/IHLCHGUSTPSOFTDEVE">
        Software Development Job Postings on Indeed in the United States (DISCONTINUED)
    </a>
    """

    series = fred.discover_us_indeed_sector_series(html)

    assert [item.series_id for item in series] == ["IHLIDXUSTPACCT", "IHLIDXUSTPSOFTDEVE"]
    assert [item.sector_occupation for item in series] == ["Accounting", "Software Development"]
    assert {item.series_group for item in series} == {"sector_occupation"}
    assert {item.series_status for item in series} == {"active"}


def test_selected_indeed_state_series_is_requested_state_set():
    series = fred.selected_indeed_state_series()

    assert {item.state_code for item in series} == {"MA", "NJ", "NY", "CA", "WA", "TX", "FL"}
    assert {item.series_id for item in series} == {
        "IHLIDXUSMA",
        "IHLIDXUSNJ",
        "IHLIDXUSNY",
        "IHLIDXUSCA",
        "IHLIDXUSWA",
        "IHLIDXUSTX",
        "IHLIDXUSFL",
    }
    assert {item.series_group for item in series} == {"state"}


def test_fetch_indeed_job_postings_discovers_series_writes_raw_files_and_metadata(monkeypatch, tmp_path):
    html = """
    <a href="/series/IHLIDXUSTPACCT">Accounting Job Postings on Indeed in the United States</a>
    <a href="/series/IHLIDXCATPSOFTDEVE">Software Development Job Postings on Indeed in Canada</a>
    <a href="/series/IHLIDXUSNEW">New Job Postings on Indeed in the United States</a>
    <a href="/series/IHLCHGUSTPACCT">Accounting Job Postings on Indeed in the United States (DISCONTINUED)</a>
    """
    csv_by_id = {
        "IHLIDXUSTPACCT": "observation_date,IHLIDXUSTPACCT\n2026-05-01,101.5\n",
        "IHLIDXUSMA": "observation_date,IHLIDXUSMA\n2026-05-01,84.73\n",
        "IHLIDXUSNJ": "observation_date,IHLIDXUSNJ\n2026-05-01,92.78\n",
        "IHLIDXUSNY": "observation_date,IHLIDXUSNY\n2026-05-01,88.86\n",
        "IHLIDXUSCA": "observation_date,IHLIDXUSCA\n2026-05-01,86.37\n",
        "IHLIDXUSWA": "observation_date,IHLIDXUSWA\n2026-05-01,77.61\n",
        "IHLIDXUSTX": "observation_date,IHLIDXUSTX\n2026-05-01,114.52\n",
        "IHLIDXUSFL": "observation_date,IHLIDXUSFL\n2026-05-01,104.97\n",
    }
    gets: list[str] = []

    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int) -> FakeResponse:
        assert timeout == 60
        if url == fred.INDEED_SECTOR_TABLE_URL:
            gets.append("sector_release_table")
            return FakeResponse(html)
        series_id = url.rsplit("=", maxsplit=1)[1]
        gets.append(series_id)
        return FakeResponse(csv_by_id[series_id])

    monkeypatch.setattr(fred, "requests", type("Requests", (), {"get": staticmethod(fake_get)}))

    settings = Settings(data_dir=tmp_path, bea_api_key=None, bls_api_key=None)
    frame, metadata = fred.fetch_indeed_job_postings(settings)

    assert gets == [
        "sector_release_table",
        "IHLIDXUSTPACCT",
        "IHLIDXUSMA",
        "IHLIDXUSNJ",
        "IHLIDXUSNY",
        "IHLIDXUSCA",
        "IHLIDXUSWA",
        "IHLIDXUSTX",
        "IHLIDXUSFL",
    ]
    assert set(frame["series_id"]) == set(csv_by_id)
    sector_row = frame[frame["series_id"] == "IHLIDXUSTPACCT"].iloc[0]
    assert sector_row["series_group"] == "sector_occupation"
    assert sector_row["sector_occupation"] == "Accounting"
    assert sector_row["state_code"] is None
    state_row = frame[frame["series_id"] == "IHLIDXUSMA"].iloc[0]
    assert state_row["series_group"] == "state"
    assert state_row["state_code"] == "MA"
    assert state_row["state_name"] == "Massachusetts"
    assert state_row["sector_occupation"] is None
    assert (tmp_path / "raw" / "fred" / "indeed_job_postings" / "sector_release_table.html").read_text() == html
    assert (tmp_path / "raw" / "fred" / "indeed_job_postings" / "IHLIDXUSTPACCT.csv").read_text() == csv_by_id[
        "IHLIDXUSTPACCT"
    ]
    assert metadata["source"] == "FRED, Federal Reserve Bank of St. Louis"
    assert metadata["discovery_url"] == fred.INDEED_SECTOR_TABLE_URL
    assert set(metadata["source_urls"]["series"]) == set(csv_by_id)
    assert set(metadata["raw_paths"]["series"]) == set(csv_by_id)
    assert metadata["selected_states"]["MA"]["series_id"] == "IHLIDXUSMA"
    assert metadata["series"]["IHLIDXUSTPACCT"]["sector_occupation"] == "Accounting"
    assert "indeed" in metadata["copyright_notes"]
    json.dumps(metadata)
