from __future__ import annotations

import os

import pytest

from economic_analysis.config import load_settings
from economic_analysis.sources import bea, bls, cex, scf

pytestmark = pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="live integration tests are opt-in")


def test_live_bls_labor_fetch(tmp_path):
    settings = load_settings(tmp_path)
    frame, metadata = bls.fetch_labor(settings)

    assert not frame.empty
    assert {"date", "series_id", "measure", "value"}.issubset(frame.columns)
    assert metadata["source"] == "BLS Public Data API v2"


def test_live_bls_sector_employment_fetch(tmp_path):
    settings = load_settings(tmp_path)
    frame, metadata = bls.fetch_sector_employment(settings)

    assert not frame.empty
    assert {"date", "series_id", "sector", "value"}.issubset(frame.columns)
    assert metadata["source"] == "BLS Current Employment Statistics, Public Data API v2"


def test_live_bls_cex_consumption_fetch(tmp_path):
    settings = load_settings(tmp_path)
    frame, metadata = cex.fetch_consumption(settings)

    assert not frame.empty
    assert {"year", "item", "group", "value", "raw_aspect_value"}.issubset(frame.columns)
    assert set(frame["demographic"]) == {"income_quintile"}
    assert set(frame["measure"]) == {"aggregate_expenditure"}
    assert metadata["source"] == "BLS Consumer Expenditure Surveys LABSTAT"


@pytest.mark.skipif(not os.getenv("BEA_API_KEY"), reason="BEA_API_KEY is required")
def test_live_bea_pce_fetch(tmp_path):
    settings = load_settings(tmp_path)
    frame, metadata = bea.fetch_pce(settings)

    assert not frame.empty
    assert {"date", "category", "value", "source_table"}.issubset(frame.columns)
    assert "BEA" in metadata["source"]


@pytest.mark.skipif(not os.getenv("BEA_API_KEY"), reason="BEA_API_KEY is required")
def test_live_bea_gdp_industry_fetch(tmp_path):
    settings = load_settings(tmp_path)
    frame, metadata = bea.fetch_gdp_industry(settings)

    assert not frame.empty
    assert {"period", "industry", "metric", "value", "table_id"}.issubset(frame.columns)
    assert "GDPbyIndustry" in metadata["source"]


@pytest.mark.skipif(not os.getenv("BEA_API_KEY"), reason="BEA_API_KEY is required")
def test_live_bea_gdp_components_fetch(tmp_path):
    settings = load_settings(tmp_path)
    frame, metadata = bea.fetch_gdp_components(settings)

    assert not frame.empty
    assert {"period", "component", "component_code", "value", "source_table"}.issubset(frame.columns)
    assert set(frame["component_code"]) == {"2", "7", "16", "19", "22"}
    assert "GDP Expenditure Components" in metadata["source"]


def test_live_scf_home_assets_fetch(tmp_path):
    settings = load_settings(tmp_path)
    frame, metadata = scf.fetch_home_assets(settings)

    assert {"survey_year", "asset_component", "group_type", "group", "value"}.issubset(frame.columns)
    assert metadata["source"].startswith("Federal Reserve")
