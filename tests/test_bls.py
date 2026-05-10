from economic_analysis.sources.bls import BLS_LABOR_SERIES, build_labor_request, normalize_labor


def test_build_labor_request_contains_expected_series():
    request = build_labor_request(api_key="secret", start_year=2000, end_year=2024)

    assert request["startyear"] == "2000"
    assert request["endyear"] == "2024"
    assert request["registrationkey"] == "secret"
    assert set(request["seriesid"]) == set(BLS_LABOR_SERIES)


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
