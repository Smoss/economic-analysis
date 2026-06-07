from __future__ import annotations

import json

import pandas as pd
import pytest

from economic_analysis.config import Settings
from economic_analysis.sources import noaa_ndfd, noaa_observations, nws_accuracy
from economic_analysis.sources.noaa_common import (
    NORTHEAST_AIRPORT_STATIONS,
    PRECIP_OCCURRENCE_THRESHOLD_IN,
    period_bucket,
    station_codes,
)


def test_station_panel_has_unique_codes_and_ids():
    assert "BOS" in station_codes()
    assert len({station.code for station in NORTHEAST_AIRPORT_STATIONS}) == len(NORTHEAST_AIRPORT_STATIONS)
    assert len({station.station_id for station in NORTHEAST_AIRPORT_STATIONS}) == len(NORTHEAST_AIRPORT_STATIONS)


def test_period_bucket_splits_recent_hypothesis_period():
    assert period_bucket("2023-12-31") == "baseline_2016_2023"
    assert period_bucket("2024-01-01") == "recent_2024_2025"


def test_observation_year_windows_cover_study_period():
    windows = noaa_observations.observation_year_windows()

    assert windows[0][0].isoformat() == "2016-01-01"
    assert windows[-1][1].isoformat() == "2025-12-31"
    assert len(windows) == 10


def test_normalize_station_observations_pivots_daily_cdo_rows():
    frame = noaa_observations.normalize_station_observations(
        [
            {"station": "GHCND:USW00014739", "date": "2024-01-02T00:00:00", "datatype": "TMAX", "value": 42},
            {"station": "GHCND:USW00014739", "date": "2024-01-02T00:00:00", "datatype": "TMIN", "value": 29},
            {"station": "GHCND:USW00014739", "date": "2024-01-02T00:00:00", "datatype": "PRCP", "value": 0.2},
        ]
    )

    assert list(frame.columns) == [
        "station",
        "station_id",
        "date",
        "observed_high_f",
        "observed_low_f",
        "observed_precip_in",
    ]
    assert frame.loc[0, "station"] == "BOS"
    assert frame.loc[0, "observed_high_f"] == 42
    assert frame.loc[0, "observed_precip_in"] == 0.2


def test_fetch_station_observations_pages_and_writes_raw(monkeypatch, tmp_path):
    calls: list[dict] = []

    class FakeResponse:
        def __init__(self, params: dict):
            self.params = params

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            calls.append(self.params)
            return {
                "metadata": {"resultset": {"count": 1}},
                "results": [
                    {
                        "station": self.params["stationid"],
                        "date": f"{self.params['startdate']}T00:00:00",
                        "datatype": "TMAX",
                        "value": 40,
                    }
                ],
            }

    def fake_get(url: str, params: dict, headers: dict, timeout: int) -> FakeResponse:
        assert url == noaa_observations.CDO_API_URL
        assert headers == {"token": "token"}
        assert timeout == 60
        return FakeResponse(params)

    monkeypatch.setattr(noaa_observations.requests, "get", fake_get)
    monkeypatch.setattr(noaa_observations, "observation_year_windows", lambda: [])

    settings = Settings(data_dir=tmp_path, bea_api_key=None, bls_api_key=None, noaa_cdo_token="token")
    frame, metadata = noaa_observations.fetch_station_observations(settings)

    assert frame.empty
    assert metadata["source"].startswith("NOAA/NCEI")
    raw = json.loads((tmp_path / "raw" / "noaa" / "observations" / "cdo_daily_observations.json").read_text())
    assert raw == {"requests": []}
    assert calls == []


def test_fetch_station_observations_requires_token(tmp_path):
    settings = Settings(data_dir=tmp_path, bea_api_key=None, bls_api_key=None)

    with pytest.raises(RuntimeError, match="NOAA_CDO_TOKEN"):
        noaa_observations.fetch_station_observations(settings)


def test_normalize_ndfd_forecasts_filters_to_study_leads_and_columns():
    frame = noaa_ndfd.normalize_ndfd_forecasts(
        [
            {
                "code": "BOS",
                "station_id": "GHCND:USW00014739",
                "issue_date": "2024-01-01",
                "target_date": "2024-01-02",
                "lead_day": 1,
                "max_temp_f": "41",
                "min_temp_f": "28",
                "qpf_in": "0.10",
                "pop_pct": "70",
            },
            {
                "code": "BOS",
                "station_id": "GHCND:USW00014739",
                "issue_date": "2024-01-01",
                "target_date": "2024-01-05",
                "lead_day": 4,
                "max_temp_f": "41",
            },
        ]
    )

    assert list(frame["lead_day"]) == [1]
    assert frame.loc[0, "issue_cycle"] == "12Z"
    assert frame.loc[0, "forecast_high_f"] == 41
    assert frame.loc[0, "forecast_pop_pct"] == 70


def test_fetch_ndfd_forecasts_requires_repeatable_extract_url(tmp_path):
    settings = Settings(data_dir=tmp_path, bea_api_key=None, bls_api_key=None)

    with pytest.raises(RuntimeError, match="NOAA_NDFD_FORECAST_CSV_URL"):
        noaa_ndfd.fetch_ndfd_forecasts(settings)


def test_score_forecasts_computes_errors_and_precip_metrics():
    forecasts = pd.DataFrame(
        [
            {
                "station": "BOS",
                "station_id": "GHCND:USW00014739",
                "issue_date": "2024-01-01",
                "issue_cycle": "12Z",
                "valid_date": "2024-01-02",
                "lead_day": 1,
                "forecast_high_f": 41,
                "forecast_low_f": 30,
                "forecast_precip_in": 0.0,
                "forecast_pop_pct": 25,
            }
        ]
    )
    observations = pd.DataFrame(
        [
            {
                "station": "BOS",
                "station_id": "GHCND:USW00014739",
                "date": "2024-01-02",
                "observed_high_f": 44,
                "observed_low_f": 29,
                "observed_precip_in": PRECIP_OCCURRENCE_THRESHOLD_IN,
            }
        ]
    )

    detail = nws_accuracy.score_forecasts(forecasts, observations)
    summary = nws_accuracy.summarize_accuracy(detail)

    assert detail.loc[0, "high_error_f"] == -3
    assert detail.loc[0, "low_error_f"] == 1
    assert detail.loc[0, "period_bucket"] == "recent_2024_2025"
    assert not bool(detail.loc[0, "precip_occurrence_correct"])
    assert summary.loc[0, "high_mae_f"] == 3
    assert summary.loc[0, "precip_brier"] == pytest.approx(0.5625)


def test_fetch_forecast_accuracy_reads_processed_inputs_and_writes_report(tmp_path):
    processed = tmp_path / "processed"
    forecasts_dir = processed / "noaa_ndfd_forecasts"
    observations_dir = processed / "noaa_station_observations"
    forecasts_dir.mkdir(parents=True)
    observations_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "station": "BOS",
                "station_id": "GHCND:USW00014739",
                "issue_date": "2024-01-01",
                "issue_cycle": "12Z",
                "valid_date": "2024-01-02",
                "lead_day": 1,
                "forecast_high_f": 41,
                "forecast_low_f": 30,
                "forecast_precip_in": 0.0,
                "forecast_pop_pct": 25,
            }
        ]
    ).to_csv(forecasts_dir / "noaa_ndfd_forecasts.csv", index=False)
    pd.DataFrame(
        [
            {
                "station": "BOS",
                "station_id": "GHCND:USW00014739",
                "date": "2024-01-02",
                "observed_high_f": 44,
                "observed_low_f": 29,
                "observed_precip_in": 0.0,
            }
        ]
    ).to_csv(observations_dir / "noaa_station_observations.csv", index=False)

    detail, metadata = nws_accuracy.fetch_forecast_accuracy(
        Settings(data_dir=tmp_path, bea_api_key=None, bls_api_key=None)
    )

    assert len(detail) == 1
    assert "summary_csv" in metadata["report_outputs"]
    assert (tmp_path / "outputs" / "nws_forecast_accuracy_summary.csv").exists()
    assert (tmp_path / "outputs" / "nws_forecast_accuracy_yearly_mae.svg").exists()
