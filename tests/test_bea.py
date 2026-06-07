import pandas as pd

from economic_analysis.sources.bea import (
    build_bea_gdp_components_params,
    build_bea_gdp_industry_params,
    build_bea_pce_params,
    normalize_gdp_components,
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


def test_build_bea_gdp_components_params_uses_nipa_gdp_table():
    params = build_bea_gdp_components_params("key")

    assert params["datasetname"] == "NIPA"
    assert params["TableName"] == "T10105"
    assert params["Frequency"] == "A,Q"
    assert params["UserID"] == "key"


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


def test_normalize_gdp_components_filters_selected_lines():
    raw = {
        "BEAAPI": {
            "Results": {
                "Data": [
                    {
                        "TimePeriod": "2024Q2",
                        "LineNumber": "1",
                        "LineDescription": "Gross domestic product",
                        "DataValue": "28,500.0",
                        "Unit": "Billions of dollars",
                        "TableName": "T10105",
                    },
                    {
                        "TimePeriod": "2024Q2",
                        "LineNumber": "2",
                        "LineDescription": "Personal consumption expenditures",
                        "DataValue": "19,000.5",
                        "Unit": "Billions of dollars",
                        "TableName": "T10105",
                    },
                    {
                        "TimePeriod": "2024Q2",
                        "LineNumber": "7",
                        "LineDescription": "Gross private domestic investment",
                        "DataValue": "5,100.1",
                        "Unit": "Billions of dollars",
                        "TableName": "T10105",
                    },
                    {
                        "TimePeriod": "2024Q2",
                        "LineNumber": "16",
                        "LineDescription": "Exports of goods and services",
                        "DataValue": "3,100.2",
                        "Unit": "Billions of dollars",
                        "TableName": "T10105",
                    },
                    {
                        "TimePeriod": "2024Q2",
                        "LineNumber": "19",
                        "LineDescription": "Imports of goods and services",
                        "DataValue": "4,000.3",
                        "Unit": "Billions of dollars",
                        "TableName": "T10105",
                    },
                    {
                        "TimePeriod": "2024Q2",
                        "LineNumber": "22",
                        "LineDescription": "Government consumption expenditures and gross investment",
                        "DataValue": "4,900.4",
                        "Unit": "Billions of dollars",
                        "TableName": "T10105",
                    },
                ]
            }
        }
    }

    frame = normalize_gdp_components(raw)

    assert list(frame["component_code"]) == ["16", "19", "2", "22", "7"]
    assert "Gross domestic product" not in set(frame["component"])
    assert frame.loc[frame["component_code"] == "19", "value"].item() == 4000.3


def test_normalize_gdp_components_parses_annual_and_quarterly_periods():
    raw = {
        "BEAAPI": {
            "Results": {
                "Data": [
                    {
                        "TimePeriod": "2024",
                        "LineNumber": "2",
                        "LineDescription": "Personal consumption expenditures",
                        "DataValue": "19,000.5",
                    },
                    {
                        "TimePeriod": "2024Q3",
                        "LineNumber": "16",
                        "LineDescription": "Exports of goods and services",
                        "DataValue": "3,100.2",
                    },
                ]
            }
        }
    }

    frame = normalize_gdp_components(raw)

    annual = frame.loc[frame["period"] == "2024"].iloc[0]
    quarterly = frame.loc[frame["period"] == "2024Q3"].iloc[0]
    assert annual["year"] == 2024
    assert pd.isna(annual["quarter"])
    assert annual["frequency"] == "annual"
    assert quarterly["year"] == 2024
    assert quarterly["quarter"] == 3
    assert quarterly["frequency"] == "quarterly"


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
