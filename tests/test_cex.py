from economic_analysis.sources import cex


def test_download_cex_files_uses_bls_friendly_headers(monkeypatch, tmp_path):
    requests: list[dict] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int):
            assert chunk_size == 1024 * 1024
            yield b"field\nvalue\n"

    def fake_get(url: str, headers: dict[str, str], stream: bool, timeout: int) -> FakeResponse:
        requests.append({"url": url, "headers": headers, "stream": stream, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(cex, "requests", type("Requests", (), {"get": staticmethod(fake_get)}))

    paths = cex.download_cex_files(tmp_path)

    assert set(paths) == set(cex.CEX_FILES)
    assert paths["all_data"] == tmp_path / "cx.data.1.AllData"
    assert all(request["url"].startswith("https://download.bls.gov/pub/time.series/CX/") for request in requests)
    assert any(request["url"].endswith("/CX/cx.data.1.AllData") for request in requests)
    assert all(request["headers"]["User-Agent"].startswith("economic-analysis/") for request in requests)
    assert all(request["stream"] is True for request in requests)
    assert all(request["timeout"] == 120 for request in requests)


def test_parse_tab_records_strips_fields():
    rows = list(cex.parse_tab_records(["series_id\tyear\tvalue\n", " CXUFOODLB0102M \t 2024 \t 12.5 \n"]))

    assert rows == [{"series_id": "CXUFOODLB0102M", "year": "2024", "value": "12.5"}]


def test_normalize_consumption_computes_income_quintile_aggregates():
    series_rows = [
        {
            "series_id": "CXUFOODLB0101M",
            "category_code": "EXPEND",
            "subcategory_code": "FOOD",
            "item_code": "FOOD",
            "demographics_code": "LB01",
            "characteristics_code": "01",
            "process_code": "M",
        },
        {
            "series_id": "CXUFOODLB0102M",
            "category_code": "EXPEND",
            "subcategory_code": "FOOD",
            "item_code": "FOOD",
            "demographics_code": "LB01",
            "characteristics_code": "02",
            "process_code": "M",
        },
        {
            "series_id": "CXUHOUSINGLB0102M",
            "category_code": "EXPEND",
            "subcategory_code": "HOUSING",
            "item_code": "HOUSING",
            "demographics_code": "LB01",
            "characteristics_code": "02",
            "process_code": "M",
        },
        {
            "series_id": "CXUFRSHFRUTLB0102M",
            "category_code": "EXPEND",
            "subcategory_code": "FOOD",
            "item_code": "FRSHFRUT",
            "demographics_code": "LB01",
            "characteristics_code": "02",
            "process_code": "M",
        },
    ]
    aspect_rows = [
        {
            "series_id": "CXUFOODLB0101M",
            "year": "2024",
            "period": "A01",
            "aspect_type": "AG",
            "value": "100,000",
            "footnote_code": "",
        },
        {
            "series_id": "CXUFOODLB0102M",
            "year": "2024",
            "period": "A01",
            "aspect_type": "AG",
            "value": "12.5",
            "footnote_code": "1",
        },
        {
            "series_id": "CXUFOODLB0102M",
            "year": "2024",
            "period": "A02",
            "aspect_type": "AG",
            "value": "99.0",
            "footnote_code": "",
        },
        {
            "series_id": "CXUFOODLB0102M",
            "year": "2024",
            "period": "A01",
            "aspect_type": "ES",
            "value": "20.0",
            "footnote_code": "",
        },
    ]
    item_rows = [
        {
            "subcategory_code": "FOOD",
            "item_code": "FOOD",
            "item_text": "Food",
            "display_level": "0",
            "selectable": "T",
        },
        {
            "subcategory_code": "HOUSING",
            "item_code": "HOUSING",
            "item_text": "Housing",
            "display_level": "0",
            "selectable": "T",
        },
        {
            "subcategory_code": "FOOD",
            "item_code": "FRSHFRUT",
            "item_text": "Fresh fruits",
            "display_level": "2",
            "selectable": "T",
        },
    ]
    subcategory_rows = [
        {"subcategory_code": "FOOD", "subcategory_text": "Food"},
        {"subcategory_code": "HOUSING", "subcategory_text": "Housing"},
    ]
    demographics_rows = [{"demographics_code": "LB01", "demographics_text": "Income quintiles"}]
    characteristics_rows = [
        {
            "demographics_code": "LB01",
            "characteristics_code": "01",
            "characteristics_text": "All Consumer Units",
        },
        {
            "demographics_code": "LB01",
            "characteristics_code": "02",
            "characteristics_text": "Lowest 20 percent income quintile",
        },
    ]

    frame = cex.normalize_consumption(
        series_rows=series_rows,
        aspect_rows=aspect_rows,
        item_rows=item_rows,
        subcategory_rows=subcategory_rows,
        demographics_rows=demographics_rows,
        characteristics_rows=characteristics_rows,
    )

    assert list(frame["series_id"]) == ["CXUFOODLB0102M"]
    assert frame.loc[0, "year"] == 2024
    assert frame.loc[0, "frequency"] == "annual"
    assert frame.loc[0, "item"] == "Food"
    assert frame.loc[0, "group"] == "Lowest 20 percent income quintile"
    assert frame.loc[0, "value"] == 12500.0
    assert frame.loc[0, "raw_aspect_value"] == 12.5
    assert frame.loc[0, "raw_aspect_unit"] == "percent_of_total_aggregate"
    assert frame.loc[0, "footnote_code"] == "1"


def test_normalize_consumption_includes_selected_detailed_fuel_item():
    series_rows = [
        {
            "series_id": "CXUGASFUELLB0101M",
            "category_code": "EXPEND",
            "subcategory_code": "TRANS",
            "item_code": "GASFUEL",
            "demographics_code": "LB01",
            "characteristics_code": "01",
            "process_code": "M",
        },
        {
            "series_id": "CXUGASFUELLB0102M",
            "category_code": "EXPEND",
            "subcategory_code": "TRANS",
            "item_code": "GASFUEL",
            "demographics_code": "LB01",
            "characteristics_code": "02",
            "process_code": "M",
        },
        {
            "series_id": "CXUFRSHFRUTLB0101M",
            "category_code": "EXPEND",
            "subcategory_code": "FOOD",
            "item_code": "FRSHFRUT",
            "demographics_code": "LB01",
            "characteristics_code": "01",
            "process_code": "M",
        },
        {
            "series_id": "CXUFRSHFRUTLB0102M",
            "category_code": "EXPEND",
            "subcategory_code": "FOOD",
            "item_code": "FRSHFRUT",
            "demographics_code": "LB01",
            "characteristics_code": "02",
            "process_code": "M",
        },
    ]
    aspect_rows = [
        {"series_id": "CXUGASFUELLB0101M", "year": "2024", "period": "A01", "aspect_type": "AG", "value": "2,000"},
        {"series_id": "CXUGASFUELLB0102M", "year": "2024", "period": "A01", "aspect_type": "AG", "value": "20"},
        {"series_id": "CXUFRSHFRUTLB0101M", "year": "2024", "period": "A01", "aspect_type": "AG", "value": "1,000"},
        {"series_id": "CXUFRSHFRUTLB0102M", "year": "2024", "period": "A01", "aspect_type": "AG", "value": "30"},
    ]
    item_rows = [
        {
            "subcategory_code": "TRANS",
            "item_code": "GASFUEL",
            "item_text": "Gasoline and other fuels",
            "display_level": "2",
            "selectable": "T",
        },
        {
            "subcategory_code": "FOOD",
            "item_code": "FRSHFRUT",
            "item_text": "Fresh fruits",
            "display_level": "2",
            "selectable": "T",
        },
    ]
    characteristics_rows = [
        {
            "demographics_code": "LB01",
            "characteristics_code": "01",
            "characteristics_text": "All Consumer Units",
        },
        {
            "demographics_code": "LB01",
            "characteristics_code": "02",
            "characteristics_text": "Lowest 20 percent income quintile",
        },
    ]

    frame = cex.normalize_consumption(
        series_rows=series_rows,
        aspect_rows=aspect_rows,
        item_rows=item_rows,
        subcategory_rows=[{"subcategory_code": "TRANS", "subcategory_text": "Transportation"}],
        demographics_rows=[],
        characteristics_rows=characteristics_rows,
    )

    assert list(frame["series_id"]) == ["CXUGASFUELLB0102M"]
    assert frame.loc[0, "item"] == "Gasoline and other fuels"
    assert frame.loc[0, "value"] == 400.0
