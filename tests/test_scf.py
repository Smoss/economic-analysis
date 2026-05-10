import zipfile
from io import BytesIO

from economic_analysis.sources.scf import normalize_home_assets_zip


def test_normalize_home_assets_zip_filters_standard_groups_and_home_assets():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "interactive_bulletin_charts_inccat_median.csv",
            "year,Category,Primary_Residence,Other_Residential_Real_Estate,Net_Worth\n"
            "2022,Less than 20,120000,15000,10000\n",
        )
        archive.writestr(
            "interactive_bulletin_charts_famstruct_median.csv",
            "year,Category,Primary_Residence\n2022,Single,90000\n",
        )

    frame = normalize_home_assets_zip(buffer.getvalue())

    assert len(frame) == 2
    assert set(frame["asset_component"]) == {"primary_residence", "other_residential_real_estate"}
    assert set(frame["group_type"]) == {"income"}
    assert set(frame["statistic"]) == {"median"}
    assert set(frame["unit"]) == {"2022_dollars"}
