import pandas as pd

from economic_analysis.sources import acs_pums
from economic_analysis.sources.acs_pums import (
    ACS_PUMS_YEARS,
    build_person_zip_url,
    normalize_fod_labels,
    normalize_person_records,
)


def test_acs_years_cover_past_10_calendar_years_through_latest_pums():
    assert ACS_PUMS_YEARS == tuple(range(2015, 2025))


def test_person_zip_url_uses_experimental_2020_release():
    assert build_person_zip_url(2019).endswith("/data/pums/2019/1-Year/csv_pus.zip")
    assert build_person_zip_url(2020).endswith("/experimental/2020/data/pums/1-Year/csv_pus.zip")
    assert build_person_zip_url(2024).endswith("/data/pums/2024/1-Year/csv_pus.zip")


def test_normalize_fod_labels_reads_census_variable_metadata():
    labels = normalize_fod_labels({"values": {"item": {"1100": "General Agriculture", " 5200 ": "Psychology"}}})

    assert labels == {"1100": "General Agriculture", "5200": "Psychology"}


def test_normalize_fod_labels_reads_census_dictionary_csv():
    labels = normalize_fod_labels(
        'NAME,FOD1P,C,4,"Recoded field of degree - first entry"\n'
        'VAL,FOD1P,C,4,"bbbb","bbbb","N/A (less than bachelor\'s degree)"\n'
        'VAL,FOD1P,C,4,"1100","1100","General Agriculture"\n'
    )

    assert labels == {"1100": "General Agriculture"}


def test_normalize_person_records_filters_recent_grads_and_weights_employment():
    raw = pd.DataFrame(
        [
            {"AGEP": "22", "SCHL": "21", "ESR": "1", "FOD1P": "1100", "PWGTP": "10"},
            {"AGEP": "27", "SCHL": "22", "ESR": "3", "FOD1P": "1100", "PWGTP": "5"},
            {"AGEP": "24", "SCHL": "21", "ESR": "6", "FOD1P": "5200", "PWGTP": "8"},
            {"AGEP": "21", "SCHL": "21", "ESR": "1", "FOD1P": "1100", "PWGTP": "100"},
            {"AGEP": "24", "SCHL": "20", "ESR": "1", "FOD1P": "1100", "PWGTP": "100"},
            {"AGEP": "25", "SCHL": "21", "ESR": "1", "FOD1P": "", "PWGTP": "100"},
        ]
    )

    frame = normalize_person_records(raw, 2024, {"1100": "General Agriculture", "5200": "Psychology"})

    ag = frame.loc[frame["major_code"] == "1100"].iloc[0]
    psych = frame.loc[frame["major_code"] == "5200"].iloc[0]
    assert ag["major_label"] == "General Agriculture"
    assert ag["weighted_population"] == 15
    assert ag["weighted_employed"] == 10
    assert ag["employment_rate"] == 10 / 15
    assert ag["unweighted_records"] == 2
    assert psych["weighted_population"] == 8
    assert psych["weighted_employed"] == 0
    assert psych["employment_rate"] == 0
    assert set(frame["age_group"]) == {f"{acs_pums.RECENT_GRAD_MIN_AGE}-{acs_pums.RECENT_GRAD_MAX_AGE}"}
    assert set(frame["degree_scope"]) == {"bachelor_or_higher"}
