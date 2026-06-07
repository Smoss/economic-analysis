from io import BytesIO
from zipfile import ZipFile

import pandas as pd

from economic_analysis.config import Settings
from economic_analysis.sources import bls_oews


def test_normalize_oews_year_sums_legacy_software_developer_rows():
    raw = pd.DataFrame(
        [
            {"OCC_CODE": "00-0000", "OCC_TITLE": "All Occupations", "TOT_EMP": "140,400,000"},
            {"OCC_CODE": "15-1132", "OCC_TITLE": "Software Developers, Applications", "TOT_EMP": "849,230"},
            {"OCC_CODE": "15-1133", "OCC_TITLE": "Software Developers, Systems Software", "TOT_EMP": "425,000"},
        ]
    )

    frame = bls_oews.normalize_oews_year(raw, 2016)

    aggregate = frame[frame["measure"] == "software_developers_employment"].iloc[0]
    all_occupations = frame[frame["measure"] == "all_occupations_employment"].iloc[0]
    assert aggregate["date"] == "2016-05-01"
    assert aggregate["soc_code"] == "15-1132+15-1133"
    assert aggregate["value"] == 1274230
    assert aggregate["method"] == "sum_legacy_applications_and_systems_software_rows"
    assert bool(aggregate["is_proxy"]) is False
    assert all_occupations["value"] == 140400000


def test_normalize_oews_year_prefers_current_exact_software_developer_row():
    raw = pd.DataFrame(
        [
            {"occ_code": "00-0000", "occ_title": "All Occupations", "tot_emp": "150,000,000"},
            {"occ_code": "15-1252", "occ_title": "Software Developers", "tot_emp": "1,656,880"},
            {
                "occ_code": "15-1256",
                "occ_title": "Software Developers and Software Quality Assurance Analysts and Testers",
                "tot_emp": "1,800,000",
            },
        ]
    )

    frame = bls_oews.normalize_oews_year(raw, 2024)

    aggregate = frame[frame["measure"] == "software_developers_employment"].iloc[0]
    assert aggregate["soc_code"] == "15-1252"
    assert aggregate["value"] == 1656880
    assert aggregate["method"] == "published_oews_row"
    assert bool(aggregate["is_proxy"]) is False


def test_fetch_swe_employment_writes_raw_zips_and_metadata(monkeypatch, tmp_path):
    def zipped_xlsx(frame: pd.DataFrame) -> bytes:
        workbook = BytesIO()
        with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False)
        archive_bytes = BytesIO()
        with ZipFile(archive_bytes, "w") as archive:
            archive.writestr("national.xlsx", workbook.getvalue())
        return archive_bytes.getvalue()

    payloads = {
        2024: zipped_xlsx(
            pd.DataFrame(
                [
                    {"occ_code": "00-0000", "occ_title": "All Occupations", "tot_emp": "150,000,000"},
                    {"occ_code": "15-1252", "occ_title": "Software Developers", "tot_emp": "1,656,880"},
                ]
            )
        ),
        2025: zipped_xlsx(
            pd.DataFrame(
                [
                    {"occ_code": "00-0000", "occ_title": "All Occupations", "tot_emp": "151,000,000"},
                    {"occ_code": "15-1252", "occ_title": "Software Developers", "tot_emp": "1,700,000"},
                ]
            )
        ),
    }
    gets: list[int] = []

    class FakeResponse:
        def __init__(self, content: bytes):
            self.content = content

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, headers: dict[str, str], timeout: int) -> FakeResponse:
        assert headers == bls_oews.BLS_OEWS_HEADERS
        assert timeout == 60
        year = 2000 + int(url.rsplit("oesm", maxsplit=1)[1][:2])
        gets.append(year)
        return FakeResponse(payloads[year])

    monkeypatch.setattr(bls_oews, "requests", type("Requests", (), {"get": staticmethod(fake_get)}))
    monkeypatch.setattr(bls_oews, "oews_years", lambda: [2024, 2025])

    settings = Settings(data_dir=tmp_path, bea_api_key=None, bls_api_key=None)
    frame, metadata = bls_oews.fetch_swe_employment(settings)

    assert gets == [2024, 2025]
    assert (tmp_path / "raw" / "bls" / "oews" / "national_2024.zip").exists()
    assert (tmp_path / "raw" / "bls" / "oews" / "national_2025.zip").exists()
    assert list(frame[frame["measure"] == "software_developers_employment"]["value"]) == [1656880.0, 1700000.0]
    assert metadata["source"] == "BLS Occupational Employment and Wage Statistics national estimates"
    assert set(metadata["raw_paths"]) == {"2024", "2025"}
