import pandas as pd
import pytest

from economic_analysis.oil_model import (
    build_oil_consumer_burden_scenarios,
    build_supply_shock_scenarios,
    parse_oil_price_scenarios,
    parse_supply_shock_scenarios,
    run_oil_consumer_burden_model,
    validate_baseline_supply_mbd,
    validate_crude_demand_elasticity,
)


def test_parse_oil_price_scenarios_defaults_and_validates():
    assert parse_oil_price_scenarios(None) == [40.0, 60.0, 80.0, 100.0, 120.0, 140.0]
    assert parse_oil_price_scenarios("45, 90") == [45.0, 90.0]


def test_parse_supply_shock_scenarios_defaults_and_validates():
    assert parse_supply_shock_scenarios(None) == [1.0, 3.0, 5.0, 8.0, 10.0]
    assert parse_supply_shock_scenarios("2, 4.5") == [2.0, 4.5]
    with pytest.raises(ValueError, match="positive"):
        parse_supply_shock_scenarios("1, 0")
    with pytest.raises(ValueError, match="positive"):
        validate_baseline_supply_mbd(0)
    with pytest.raises(ValueError, match="negative"):
        validate_crude_demand_elasticity(0)
    with pytest.raises(ValueError, match="negative"):
        validate_crude_demand_elasticity(0.1)


def test_build_supply_shock_scenarios_translates_gap_to_oil_price():
    annual_prices = pd.DataFrame(
        [
            {"year": 2023, "wti_crude_oil_price": 70.0, "regular_gasoline_price": 3.5},
            {"year": 2024, "wti_crude_oil_price": 80.0, "regular_gasoline_price": 4.0},
        ]
    )

    scenarios = build_supply_shock_scenarios(
        annual_prices,
        [5.0],
        baseline_supply_mbd=100.0,
        crude_demand_elasticity=-0.10,
        baseline_oil_price=80.0,
    )

    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.supply_gap_share == 0.05
    assert scenario.oil_price == pytest.approx(120.0)
    assert scenario.baseline_oil_price == 80.0


def test_build_oil_consumer_burden_scenarios_uses_latest_common_baseline_year():
    cex = pd.DataFrame(
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
            {
                "year": 2024,
                "item": "Gasoline and other fuels",
                "group": "Highest 20 percent income quintile",
                "value": 200.0,
            },
            {
                "year": 2024,
                "item": "Average annual expenditures",
                "group": "Highest 20 percent income quintile",
                "value": 2000.0,
            },
        ]
    )
    prices = pd.DataFrame(
        [
            {"date": "2023-01-01", "measure": "wti_crude_oil_price", "value": 50.0},
            {"date": "2023-01-01", "measure": "regular_gasoline_price", "value": 2.5},
            {"date": "2024-01-01", "measure": "wti_crude_oil_price", "value": 100.0},
            {"date": "2024-01-01", "measure": "regular_gasoline_price", "value": 4.0},
        ]
    )

    frame = build_oil_consumer_burden_scenarios(cex, prices, [50.0, 100.0])

    assert list(frame["scenario_oil_price_dollars_per_barrel"]) == [50.0, 50.0, 100.0, 100.0]
    low_50 = frame[
        (frame["income_quintile"] == "Lowest 20 percent income quintile")
        & (frame["scenario_oil_price_dollars_per_barrel"] == 50.0)
    ].iloc[0]
    assert low_50["baseline_year"] == 2024
    assert low_50["estimated_gasoline_price_dollars_per_gallon"] == 2.5
    assert low_50["scenario_fuel_spending_millions"] == 62.5
    assert low_50["baseline_burden_share"] == 0.1
    assert low_50["scenario_burden_share"] == 0.0625
    assert low_50["delta_burden_percentage_points"] == pytest.approx(-3.75)
    assert "scenario_supply_gap_mbd" not in frame.columns


def test_build_oil_consumer_burden_scenarios_includes_supply_shock_metadata():
    cex = pd.DataFrame(
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
    )
    prices = pd.DataFrame(
        [
            {"date": "2023-01-01", "measure": "wti_crude_oil_price", "value": 50.0},
            {"date": "2023-01-01", "measure": "regular_gasoline_price", "value": 2.5},
            {"date": "2024-01-01", "measure": "wti_crude_oil_price", "value": 80.0},
            {"date": "2024-01-01", "measure": "regular_gasoline_price", "value": 4.0},
        ]
    )

    frame = build_oil_consumer_burden_scenarios(
        cex,
        prices,
        supply_shocks_mbd=[5.0],
        baseline_supply_mbd=100.0,
        crude_demand_elasticity=-0.10,
        baseline_oil_price=80.0,
    )

    row = frame.iloc[0]
    assert row["scenario_supply_gap_mbd"] == 5.0
    assert row["baseline_supply_mbd"] == 100.0
    assert row["supply_gap_share"] == 0.05
    assert row["crude_demand_elasticity"] == -0.10
    assert row["baseline_oil_price_dollars_per_barrel"] == 80.0
    assert row["scenario_oil_price_dollars_per_barrel"] == pytest.approx(120.0)


def test_run_oil_consumer_burden_model_writes_output(tmp_path):
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

    frame, output_path = run_oil_consumer_burden_model(tmp_path, tmp_path / "outputs", [100.0])

    assert output_path == tmp_path / "outputs" / "oil_consumer_burden_scenarios.csv"
    assert output_path.exists()
    assert len(frame) == 1


def test_run_oil_consumer_burden_model_rejects_mixed_scenario_modes(tmp_path):
    with pytest.raises(ValueError, match="either direct oil price scenarios or supply shock scenarios"):
        run_oil_consumer_burden_model(
            tmp_path,
            tmp_path / "outputs",
            oil_prices=[100.0],
            supply_shocks_mbd=[5.0],
        )
