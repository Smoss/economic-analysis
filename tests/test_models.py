import json
from pathlib import Path

import pytest

from economic_analysis.sources.bls import normalize_labor
from economic_analysis.sources.models import (
    BeaGdpIndustryDataRow,
    BeaPceDataRow,
    BeaResponse,
    BlsLaborResponse,
    ScfHomeAssetRow,
)


def test_bls_response_model_accepts_labor_fixture():
    raw = {
        "status": "REQUEST_SUCCEEDED",
        "responseTime": 123,
        "message": [],
        "Results": {
            "series": [
                {
                    "seriesID": "LNS11000000",
                    "data": [{"year": "2024", "period": "M01", "periodName": "January", "value": "167276"}],
                }
            ]
        },
    }

    parsed = BlsLaborResponse.model_validate(raw)

    assert parsed.response_time == 123
    assert parsed.results.series[0].series_id == "LNS11000000"
    assert normalize_labor(raw).loc[0, "date"] == "2024-01-01"


def test_bea_response_model_accepts_dict_results_with_pce_rows():
    raw = {
        "BEAAPI": {
            "Results": {
                "Data": [
                    {
                        "TimePeriod": "2024M01",
                        "LineNumber": "1",
                        "LineDescription": "Personal consumption expenditures",
                        "DataValue": "19,000.5",
                        "UNIT_MULT": "6",
                        "TableName": "T20805",
                    }
                ],
                "Notes": [{"NoteRef": "T20805", "NoteText": "Example note"}],
            }
        }
    }

    response = BeaResponse.model_validate(raw)
    row = BeaPceDataRow.model_validate(response.data_rows()[0])

    assert row.time_period == "2024M01"
    assert row.line_number == "1"
    assert response.notes()[0].note_ref == "T20805"


def test_bea_response_model_accepts_list_results_with_gdp_rows():
    raw = {
        "BEAAPI": {
            "Results": [
                {
                    "Data": [
                        {
                            "Year": "2024",
                            "Quarter": "II",
                            "Frequency": "Q",
                            "Industry": "11",
                            "IndustrYDescription": "Agriculture, forestry, fishing, and hunting",
                            "DataValue": "245.2",
                        }
                    ]
                }
            ]
        }
    }

    response = BeaResponse.model_validate(raw)
    row = BeaGdpIndustryDataRow.model_validate(response.data_rows()[0])

    assert row.year == "2024"
    assert row.quarter == "II"
    assert row.industry == "11"


def test_scf_home_asset_model_constrains_standard_values():
    row = ScfHomeAssetRow(
        survey_year=2022,
        asset_component="primary_residence",
        group_type="income",
        group="Less than 20",
        statistic="median",
        value=120000,
        unit="2022_dollars",
    )

    assert row.asset_component == "primary_residence"


def test_cached_raw_payloads_validate_when_available():
    raw_dir = Path("data/raw")
    if not raw_dir.exists():
        pytest.skip("cached raw payloads are not present")

    bls_path = raw_dir / "bls" / "labor.json"
    pce_path = raw_dir / "bea" / "pce.json"
    gdp_path = raw_dir / "bea" / "gdp_industry.json"

    if bls_path.exists():
        BlsLaborResponse.model_validate(json.loads(bls_path.read_text()))

    if pce_path.exists():
        BeaResponse.model_validate(json.loads(pce_path.read_text()))

    if gdp_path.exists():
        for payload in json.loads(gdp_path.read_text()).values():
            BeaResponse.model_validate(payload)
