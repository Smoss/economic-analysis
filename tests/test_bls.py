import json

from economic_analysis.config import Settings
from economic_analysis.sources import bls
from economic_analysis.sources.bls import (
    BLS_LABOR_SERIES,
    BLS_SECTOR_EMPLOYMENT_SERIES,
    build_labor_request,
    build_sector_employment_request,
    labor_year_windows,
    normalize_labor,
    normalize_sector_employment,
)


def test_build_labor_request_contains_expected_series():
    request = build_labor_request(api_key="secret", start_year=2000, end_year=2024)

    assert request["startyear"] == "2000"
    assert request["endyear"] == "2024"
    assert request["registrationkey"] == "secret"
    assert set(request["seriesid"]) == set(BLS_LABOR_SERIES)


def test_build_sector_employment_request_contains_expected_series():
    request = build_sector_employment_request(api_key="secret", start_year=2020, end_year=2026)

    assert request["startyear"] == "2020"
    assert request["endyear"] == "2026"
    assert request["registrationkey"] == "secret"
    assert set(request["seriesid"]) == set(BLS_SECTOR_EMPLOYMENT_SERIES)


def test_labor_year_windows_keeps_exact_10_year_range_together():
    assert labor_year_windows(2000, 2009) == [(2000, 2009)]


def test_labor_year_windows_splits_11_year_range():
    assert labor_year_windows(2000, 2010) == [(2000, 2009), (2010, 2010)]


def test_labor_year_windows_splits_long_range_without_gaps_or_overlaps():
    windows = labor_year_windows(1990, 2026)

    assert windows == [(1990, 1999), (2000, 2009), (2010, 2019), (2020, 2026)]
    assert all(end_year - start_year + 1 <= 10 for start_year, end_year in windows)
    assert [year for start, end in windows for year in range(start, end + 1)] == list(range(1990, 2027))


def test_fetch_labor_splits_long_range_and_aggregates_responses(monkeypatch, tmp_path):
    posts: list[dict] = []

    class FakeResponse:
        def __init__(self, payload: dict):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            start_year = self.payload["startyear"]
            return {
                "message": [f"window {start_year}"],
                "Results": {
                    "series": [
                        {
                            "seriesID": "LNS11000000",
                            "data": [{"year": start_year, "period": "M01", "value": start_year}],
                        }
                    ]
                },
            }

    def fake_post(url: str, json: dict, timeout: int) -> FakeResponse:
        assert url == bls.BLS_API_URL
        assert timeout == 60
        posts.append(json)
        return FakeResponse(json)

    monkeypatch.setattr(bls, "requests", type("Requests", (), {"post": staticmethod(fake_post)}))
    monkeypatch.setattr(bls, "labor_year_windows", lambda: [(2000, 2009), (2010, 2010)])

    settings = Settings(data_dir=tmp_path, bea_api_key=None, bls_api_key="secret")
    frame, metadata = bls.fetch_labor(settings)

    assert [(post["startyear"], post["endyear"]) for post in posts] == [("2000", "2009"), ("2010", "2010")]
    assert all(int(post["endyear"]) - int(post["startyear"]) + 1 <= 10 for post in posts)
    assert all(post["registrationkey"] == "secret" for post in posts)
    assert list(frame["date"]) == ["2000-01-01", "2010-01-01"]
    assert list(frame["value"]) == [2000.0, 2010.0]

    raw = json.loads((tmp_path / "raw" / "bls" / "labor.json").read_text())
    assert [request["window"] for request in raw["requests"]] == [
        {"start_year": 2000, "end_year": 2009},
        {"start_year": 2010, "end_year": 2010},
    ]
    assert all("registrationkey" not in request["api_params"] for request in raw["requests"])
    assert metadata["api_params"] == {"requests": [request["api_params"] for request in raw["requests"]]}
    assert metadata["release_notes"] == ["window 2000", "window 2010"]


def test_fetch_sector_employment_writes_raw_and_metadata(monkeypatch, tmp_path):
    posts: list[dict] = []

    class FakeResponse:
        def __init__(self, payload: dict):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "message": ["ok"],
                "Results": {
                    "series": [
                        {
                            "seriesID": "CES5000000001",
                            "data": [{"year": "2026", "period": "M01", "value": "3102.5"}],
                        }
                    ]
                },
            }

    def fake_post(url: str, json: dict, timeout: int) -> FakeResponse:
        assert url == bls.BLS_API_URL
        assert timeout == 60
        posts.append(json)
        return FakeResponse(json)

    monkeypatch.setattr(bls, "requests", type("Requests", (), {"post": staticmethod(fake_post)}))
    monkeypatch.setattr(bls, "labor_year_windows", lambda start_year=2020: [(2020, 2026)])

    settings = Settings(data_dir=tmp_path, bea_api_key=None, bls_api_key="secret")
    frame, metadata = bls.fetch_sector_employment(settings)

    assert [(post["startyear"], post["endyear"]) for post in posts] == [("2020", "2026")]
    assert posts[0]["registrationkey"] == "secret"
    assert list(frame["date"]) == ["2026-01-01"]
    assert frame.loc[0, "sector"] == "Information"
    assert frame.loc[0, "value"] == 3102.5

    raw = json.loads((tmp_path / "raw" / "bls" / "sector_employment.json").read_text())
    assert raw["requests"][0]["window"] == {"start_year": 2020, "end_year": 2026}
    assert "registrationkey" not in raw["requests"][0]["api_params"]
    assert metadata["api_params"] == {"requests": [request["api_params"] for request in raw["requests"]]}
    assert metadata["method"] == "Monthly seasonally adjusted payroll employment by CES supersector."


def test_normalize_labor_to_long_monthly_rows():
    raw = {
        "Results": {
            "series": [
                {
                    "seriesID": "LNS11000000",
                    "data": [
                        {"year": "2024", "period": "M02", "value": "167436"},
                        {"year": "2024", "period": "M01", "value": "167276"},
                        {"year": "2024", "period": "M13", "value": "167356"},
                    ],
                }
            ]
        }
    }

    frame = normalize_labor(raw)

    assert list(frame["date"]) == ["2024-01-01", "2024-02-01"]
    assert frame.loc[0, "measure"] == "labor_force"
    assert frame.loc[0, "value"] == 167276
    assert frame.loc[0, "seasonality"] == "seasonally_adjusted"


def test_normalize_sector_employment_to_long_monthly_rows():
    raw = {
        "Results": {
            "series": [
                {
                    "seriesID": "CES5000000001",
                    "data": [
                        {"year": "2024", "period": "M02", "value": "3126"},
                        {"year": "2024", "period": "M01", "value": "3130"},
                        {"year": "2024", "period": "M13", "value": "3128"},
                    ],
                }
            ]
        }
    }

    frame = normalize_sector_employment(raw)

    assert list(frame["date"]) == ["2024-01-01", "2024-02-01"]
    assert frame.loc[0, "sector"] == "Information"
    assert frame.loc[0, "sector_code"] == "50"
    assert frame.loc[0, "measure"] == "payroll_employment"
    assert frame.loc[0, "value"] == 3130
