import pandas as pd
import pytest

from economic_analysis.cli import main


def test_fetch_all_dry_run_has_no_network_or_credentials(capsys, tmp_path):
    exit_code = main(["fetch", "all", "--dry-run", "--data-dir", str(tmp_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "bls_labor" in output
    assert "bls_sector_employment" in output
    assert "bls_cex_consumption" in output
    assert "bls_oews_swe_employment" in output
    assert "bea_pce" in output
    assert "bea_gdp_components" in output
    assert "scf_home_assets" in output
    assert "acs_major_employment" in output
    assert "fred_swe_labor_market" in output
    assert "fred_consumer_sentiment" in output
    assert "fred_oil_energy_prices" in output
    assert "fred_indeed_job_postings" in output
    assert "bea_gdp_industry" in output
    assert "noaa_ndfd_forecasts" in output
    assert "noaa_station_observations" in output
    assert "nws_forecast_accuracy" in output
    assert "would write" in output


def test_fetch_all_requires_bea_key_before_live_writes(monkeypatch, tmp_path):
    monkeypatch.delenv("BEA_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="BEA_API_KEY is required"):
        main(["fetch", "all", "--data-dir", str(tmp_path)])


def test_oil_consumer_burden_model_command_writes_output(capsys, tmp_path):
    processed = tmp_path / "processed"
    cex_dir = processed / "bls_cex_consumption"
    prices_dir = processed / "fred_oil_energy_prices"
    cex_dir.mkdir(parents=True)
    prices_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "year": 2024,
                "item": "Gasoline and other fuels",
                "group": "Lowest 20 percent income quintile",
                "value": 100.0,
            },
            {
                "year": 2024,
                "item": "Average annual expenditures",
                "group": "Lowest 20 percent income quintile",
                "value": 1000.0,
            },
        ]
    ).to_csv(cex_dir / "bls_cex_consumption.csv", index=False)
    pd.DataFrame(
        [
            {"date": "2023-01-01", "measure": "wti_crude_oil_price", "value": 50.0},
            {"date": "2023-01-01", "measure": "regular_gasoline_price", "value": 2.5},
            {"date": "2024-01-01", "measure": "wti_crude_oil_price", "value": 100.0},
            {"date": "2024-01-01", "measure": "regular_gasoline_price", "value": 4.0},
        ]
    ).to_csv(prices_dir / "fred_oil_energy_prices.csv", index=False)

    exit_code = main(
        [
            "model",
            "oil-consumer-burden",
            "--data-dir",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "outputs"),
            "--oil-prices",
            "100",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "oil_consumer_burden: 1 rows" in output
    assert (tmp_path / "outputs" / "oil_consumer_burden_scenarios.csv").exists()


def test_oil_consumer_burden_model_command_writes_supply_shock_metadata(capsys, tmp_path):
    processed = tmp_path / "processed"
    cex_dir = processed / "bls_cex_consumption"
    prices_dir = processed / "fred_oil_energy_prices"
    cex_dir.mkdir(parents=True)
    prices_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "year": 2024,
                "item": "Gasoline and other fuels",
                "group": "Lowest 20 percent income quintile",
                "value": 100.0,
            },
            {
                "year": 2024,
                "item": "Average annual expenditures",
                "group": "Lowest 20 percent income quintile",
                "value": 1000.0,
            },
        ]
    ).to_csv(cex_dir / "bls_cex_consumption.csv", index=False)
    pd.DataFrame(
        [
            {"date": "2023-01-01", "measure": "wti_crude_oil_price", "value": 50.0},
            {"date": "2023-01-01", "measure": "regular_gasoline_price", "value": 2.5},
            {"date": "2024-01-01", "measure": "wti_crude_oil_price", "value": 80.0},
            {"date": "2024-01-01", "measure": "regular_gasoline_price", "value": 4.0},
        ]
    ).to_csv(prices_dir / "fred_oil_energy_prices.csv", index=False)

    exit_code = main(
        [
            "model",
            "oil-consumer-burden",
            "--data-dir",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "outputs"),
            "--supply-shocks-mbd",
            "5",
            "--crude-demand-elasticity",
            "-0.10",
            "--baseline-oil-price",
            "80",
        ]
    )

    output_path = tmp_path / "outputs" / "oil_consumer_burden_scenarios.csv"
    output = capsys.readouterr().out
    frame = pd.read_csv(output_path)
    assert exit_code == 0
    assert "oil_consumer_burden: 1 rows" in output
    assert output_path.exists()
    assert frame.loc[0, "scenario_supply_gap_mbd"] == 5.0
    assert frame.loc[0, "crude_demand_elasticity"] == -0.10
    assert frame.loc[0, "scenario_oil_price_dollars_per_barrel"] == 120.0
