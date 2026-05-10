from economic_analysis.sources.bea import (
    build_bea_gdp_industry_params,
    build_bea_pce_params,
    normalize_gdp_industry,
    normalize_pce,
)


def test_build_bea_pce_params_uses_monthly_pce_table():
    params = build_bea_pce_params("key")

    assert params["datasetname"] == "NIPA"
    assert params["TableName"] == "T20805"
    assert params["Frequency"] == "M"
    assert params["UserID"] == "key"


def test_build_bea_gdp_industry_params_uses_industry_dataset():
    params = build_bea_gdp_industry_params("key", "1")

    assert params["datasetname"] == "GDPbyIndustry"
    assert params["TableID"] == "1"
    assert params["Industry"] == "ALL"
    assert params["Frequency"] == "A,Q"


def test_normalize_pce_long_format():
    raw = {
        "BEAAPI": {
            "Results": {
                "Data": [
                    {
                        "TimePeriod": "2024M01",
                        "LineNumber": "1",
                        "LineDescription": "Personal consumption expenditures",
                        "DataValue": "19,000.5",
                        "Unit": "Billions of dollars",
                        "TableName": "T20805",
                    }
                ]
            }
        }
    }

    frame = normalize_pce(raw)

    assert list(frame.columns) == ["date", "frequency", "line_code", "category", "value", "unit", "source_table"]
    assert frame.loc[0, "date"] == "2024-01-01"
    assert frame.loc[0, "value"] == 19000.5


def test_normalize_gdp_industry_quarterly_rows():
    raw = {
        "BEAAPI": {
            "Results": {
                "Data": [
                    {
                        "Year": "2024Q2",
                        "Frequency": "Q",
                        "Industry": "11",
                        "IndustrYDescription": "Agriculture, forestry, fishing, and hunting",
                        "DataValue": "245.2",
                        "Unit": "Billions of chained dollars",
                    }
                ]
            }
        }
    }

    frame = normalize_gdp_industry(raw, "RG", "real_value_added_chained_dollars")

    assert frame.loc[0, "year"] == 2024
    assert frame.loc[0, "quarter"] == 2
    assert frame.loc[0, "frequency"] == "quarterly"
    assert frame.loc[0, "metric"] == "real_value_added_chained_dollars"


def test_normalize_gdp_industry_bea_quarter_field():
    raw = {
        "BEAAPI": {
            "Results": {
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
        }
    }

    frame = normalize_gdp_industry(raw, "10", "real_value_added_chained_dollars")

    assert frame.loc[0, "period"] == "2024Q2"
    assert frame.loc[0, "quarter"] == 2
    assert frame.loc[0, "frequency"] == "quarterly"
