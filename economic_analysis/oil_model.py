from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from economic_analysis.io import ensure_dir

DEFAULT_OIL_PRICE_SCENARIOS = [40.0, 60.0, 80.0, 100.0, 120.0, 140.0]
DEFAULT_SUPPLY_SHOCK_SCENARIOS_MBD = [1.0, 3.0, 5.0, 8.0, 10.0]
DEFAULT_BASELINE_SUPPLY_MBD = 100.0
DEFAULT_CRUDE_DEMAND_ELASTICITY = -0.10
FUEL_BURDEN_ITEM = "Gasoline and other fuels"
TOTAL_EXPENDITURE_ITEM = "Average annual expenditures"
WTI_MEASURE = "wti_crude_oil_price"
GASOLINE_MEASURE = "regular_gasoline_price"
OUTPUT_FILENAME = "oil_consumer_burden_scenarios.csv"
QUINTILE_ORDER = {
    "Lowest 20 percent income quintile": 1,
    "Second 20 percent income quintile": 2,
    "Third 20 percent income quintile": 3,
    "Fourth 20 percent income quintile": 4,
    "Highest 20 percent income quintile": 5,
}


@dataclass(frozen=True)
class OilScenario:
    oil_price: float
    supply_gap_mbd: float | None = None
    baseline_supply_mbd: float | None = None
    supply_gap_share: float | None = None
    crude_demand_elasticity: float | None = None
    baseline_oil_price: float | None = None

    @property
    def is_supply_shock(self) -> bool:
        return self.supply_gap_mbd is not None


def parse_oil_price_scenarios(value: str | None) -> list[float]:
    if value is None or not value.strip():
        return DEFAULT_OIL_PRICE_SCENARIOS.copy()
    prices = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not prices:
        raise ValueError("At least one oil price scenario is required.")
    if any(price <= 0 for price in prices):
        raise ValueError("Oil price scenarios must be positive.")
    return prices


def parse_supply_shock_scenarios(value: str | None) -> list[float]:
    if value is None or not value.strip():
        return DEFAULT_SUPPLY_SHOCK_SCENARIOS_MBD.copy()
    shocks = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not shocks:
        raise ValueError("At least one supply shock scenario is required.")
    if any(shock <= 0 for shock in shocks):
        raise ValueError("Supply shock scenarios must be positive.")
    return shocks


def validate_baseline_supply_mbd(value: float) -> float:
    if value <= 0:
        raise ValueError("Baseline supply must be positive.")
    return float(value)


def validate_crude_demand_elasticity(value: float) -> float:
    if value >= 0:
        raise ValueError("Crude demand elasticity must be negative.")
    return float(value)


def validate_baseline_oil_price(value: float | None) -> float | None:
    if value is None:
        return None
    if value <= 0:
        raise ValueError("Baseline oil price must be positive.")
    return float(value)


def run_oil_consumer_burden_model(
    data_dir: Path,
    output_dir: Path,
    oil_prices: Sequence[float] | None = None,
    supply_shocks_mbd: Sequence[float] | None = None,
    baseline_supply_mbd: float = DEFAULT_BASELINE_SUPPLY_MBD,
    crude_demand_elasticity: float = DEFAULT_CRUDE_DEMAND_ELASTICITY,
    baseline_oil_price: float | None = None,
) -> tuple[pd.DataFrame, Path]:
    if oil_prices is not None and supply_shocks_mbd is not None:
        raise ValueError("Use either direct oil price scenarios or supply shock scenarios, not both.")

    oil_prices = list(oil_prices or DEFAULT_OIL_PRICE_SCENARIOS) if supply_shocks_mbd is None else None
    cex = _read_processed_csv(data_dir, "bls_cex_consumption")
    prices = _read_processed_csv(data_dir, "fred_oil_energy_prices")

    frame = build_oil_consumer_burden_scenarios(
        cex,
        prices,
        oil_prices=oil_prices,
        supply_shocks_mbd=supply_shocks_mbd,
        baseline_supply_mbd=baseline_supply_mbd,
        crude_demand_elasticity=crude_demand_elasticity,
        baseline_oil_price=baseline_oil_price,
    )

    ensure_dir(output_dir)
    output_path = output_dir / OUTPUT_FILENAME
    frame.to_csv(output_path, index=False)
    return frame, output_path


def build_oil_consumer_burden_scenarios(
    cex: pd.DataFrame,
    prices: pd.DataFrame,
    oil_prices: Sequence[float] | None = None,
    supply_shocks_mbd: Sequence[float] | None = None,
    baseline_supply_mbd: float = DEFAULT_BASELINE_SUPPLY_MBD,
    crude_demand_elasticity: float = DEFAULT_CRUDE_DEMAND_ELASTICITY,
    baseline_oil_price: float | None = None,
) -> pd.DataFrame:
    if oil_prices is not None and supply_shocks_mbd is not None:
        raise ValueError("Use either direct oil price scenarios or supply shock scenarios, not both.")

    annual_prices = _annual_energy_prices(prices)
    pass_through = _fit_oil_to_gasoline_pass_through(annual_prices)
    baseline = _baseline_cex_burden(cex, annual_prices)
    scenarios = (
        build_supply_shock_scenarios(
            annual_prices,
            supply_shocks_mbd or DEFAULT_SUPPLY_SHOCK_SCENARIOS_MBD,
            baseline_supply_mbd=baseline_supply_mbd,
            crude_demand_elasticity=crude_demand_elasticity,
            baseline_oil_price=baseline_oil_price,
        )
        if supply_shocks_mbd is not None
        else [OilScenario(oil_price=float(oil_price)) for oil_price in (oil_prices or DEFAULT_OIL_PRICE_SCENARIOS)]
    )

    rows: list[dict[str, float | int | str | None]] = []
    include_supply_columns = any(scenario.is_supply_shock for scenario in scenarios)
    for scenario in scenarios:
        estimated_gasoline_price = pass_through["intercept"] + pass_through["slope"] * scenario.oil_price
        for baseline_row in baseline.to_dict("records"):
            scenario_fuel_spending = (
                baseline_row["baseline_fuel_spending_millions"]
                * estimated_gasoline_price
                / baseline_row["baseline_gasoline_price"]
            )
            scenario_share = scenario_fuel_spending / baseline_row["total_expenditure_millions"]
            row: dict[str, float | int | str | None] = {
                "baseline_year": int(baseline_row["baseline_year"]),
                "income_quintile": baseline_row["group"],
                "scenario_oil_price_dollars_per_barrel": scenario.oil_price,
                "estimated_gasoline_price_dollars_per_gallon": estimated_gasoline_price,
                "baseline_gasoline_price_dollars_per_gallon": baseline_row["baseline_gasoline_price"],
                "baseline_fuel_spending_millions": baseline_row["baseline_fuel_spending_millions"],
                "scenario_fuel_spending_millions": scenario_fuel_spending,
                "total_expenditure_millions": baseline_row["total_expenditure_millions"],
                "baseline_burden_share": baseline_row["baseline_burden_share"],
                "scenario_burden_share": scenario_share,
                "delta_burden_percentage_points": (scenario_share - baseline_row["baseline_burden_share"]) * 100,
                "pass_through_intercept": pass_through["intercept"],
                "pass_through_slope": pass_through["slope"],
                "method": "constant_quantity_linear_oil_to_gasoline_pass_through",
            }
            if include_supply_columns:
                row.update(
                    {
                        "scenario_supply_gap_mbd": scenario.supply_gap_mbd,
                        "baseline_supply_mbd": scenario.baseline_supply_mbd,
                        "supply_gap_share": scenario.supply_gap_share,
                        "crude_demand_elasticity": scenario.crude_demand_elasticity,
                        "baseline_oil_price_dollars_per_barrel": scenario.baseline_oil_price,
                    }
                )
            rows.append(row)

    frame = pd.DataFrame(rows)
    frame["_quintile_order"] = frame["income_quintile"].map(QUINTILE_ORDER).fillna(99)
    sort_columns = (
        ["scenario_supply_gap_mbd", "_quintile_order"]
        if include_supply_columns
        else ["scenario_oil_price_dollars_per_barrel", "_quintile_order"]
    )
    frame = frame.sort_values(sort_columns).drop(columns=["_quintile_order"])
    return frame.reset_index(drop=True)


def build_supply_shock_scenarios(
    annual_prices: pd.DataFrame,
    supply_shocks_mbd: Sequence[float],
    baseline_supply_mbd: float = DEFAULT_BASELINE_SUPPLY_MBD,
    crude_demand_elasticity: float = DEFAULT_CRUDE_DEMAND_ELASTICITY,
    baseline_oil_price: float | None = None,
) -> list[OilScenario]:
    baseline_supply_mbd = validate_baseline_supply_mbd(float(baseline_supply_mbd))
    crude_demand_elasticity = validate_crude_demand_elasticity(float(crude_demand_elasticity))
    baseline_oil_price = validate_baseline_oil_price(baseline_oil_price)
    if baseline_oil_price is None:
        if annual_prices.empty or WTI_MEASURE not in annual_prices:
            raise ValueError("Baseline oil price cannot be inferred from oil/energy price data.")
        baseline_oil_price = float(annual_prices.sort_values("year")[WTI_MEASURE].dropna().iloc[-1])

    scenarios: list[OilScenario] = []
    for supply_gap_mbd in supply_shocks_mbd:
        if supply_gap_mbd <= 0:
            raise ValueError("Supply shock scenarios must be positive.")
        supply_gap_share = float(supply_gap_mbd) / baseline_supply_mbd
        price_change_share = supply_gap_share / abs(crude_demand_elasticity)
        scenarios.append(
            OilScenario(
                oil_price=baseline_oil_price * (1 + price_change_share),
                supply_gap_mbd=float(supply_gap_mbd),
                baseline_supply_mbd=baseline_supply_mbd,
                supply_gap_share=supply_gap_share,
                crude_demand_elasticity=crude_demand_elasticity,
                baseline_oil_price=baseline_oil_price,
            )
        )
    return scenarios


def _read_processed_csv(data_dir: Path, dataset: str) -> pd.DataFrame:
    path = data_dir / "processed" / dataset / f"{dataset}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing processed dataset: {path}")
    return pd.read_csv(path)


def _annual_energy_prices(prices: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "measure", "value"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"Oil/energy price data is missing columns: {sorted(missing)}")

    frame = prices[prices["measure"].isin([WTI_MEASURE, GASOLINE_MEASURE])].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["year"] = frame["date"].dt.year
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["year", "value"])
    annual = frame.pivot_table(index="year", columns="measure", values="value", aggfunc="mean").reset_index()
    annual["year"] = annual["year"].astype(int)
    return annual.dropna(subset=[WTI_MEASURE, GASOLINE_MEASURE]).sort_values("year").reset_index(drop=True)


def _fit_oil_to_gasoline_pass_through(annual_prices: pd.DataFrame) -> dict[str, float]:
    if len(annual_prices) < 2:
        raise ValueError("At least two overlapping annual oil and gasoline price observations are required.")

    x = annual_prices[WTI_MEASURE].astype(float)
    y = annual_prices[GASOLINE_MEASURE].astype(float)
    x_mean = x.mean()
    y_mean = y.mean()
    denominator = ((x - x_mean) ** 2).sum()
    if denominator == 0:
        raise ValueError("Oil price observations have no variation; pass-through cannot be estimated.")

    slope = ((x - x_mean) * (y - y_mean)).sum() / denominator
    intercept = y_mean - slope * x_mean
    return {"intercept": float(intercept), "slope": float(slope)}


def _baseline_cex_burden(cex: pd.DataFrame, annual_prices: pd.DataFrame) -> pd.DataFrame:
    required = {"year", "item", "group", "value"}
    missing = required - set(cex.columns)
    if missing:
        raise ValueError(f"CEX data is missing columns: {sorted(missing)}")

    cex = cex.copy()
    cex["year"] = pd.to_numeric(cex["year"], errors="coerce")
    cex["value"] = pd.to_numeric(cex["value"], errors="coerce")
    available_years = (
        set(cex.loc[cex["item"] == FUEL_BURDEN_ITEM, "year"].dropna().astype(int))
        & set(cex.loc[cex["item"] == TOTAL_EXPENDITURE_ITEM, "year"].dropna().astype(int))
        & set(annual_prices["year"].astype(int))
    )
    if not available_years:
        raise ValueError("No common baseline year exists across CEX fuel, CEX total spending, and price data.")

    baseline_year = max(available_years)
    cex_year = cex[cex["year"] == baseline_year]
    fuel = cex_year[cex_year["item"] == FUEL_BURDEN_ITEM][["group", "value"]].rename(
        columns={"value": "baseline_fuel_spending_millions"}
    )
    total = cex_year[cex_year["item"] == TOTAL_EXPENDITURE_ITEM][["group", "value"]].rename(
        columns={"value": "total_expenditure_millions"}
    )
    baseline = fuel.merge(total, on="group", how="inner")
    if baseline.empty:
        raise ValueError(f"No income-quintile fuel burden rows found for baseline year {baseline_year}.")

    gasoline_price = annual_prices.loc[annual_prices["year"] == baseline_year, GASOLINE_MEASURE].iloc[0]
    baseline["baseline_year"] = baseline_year
    baseline["baseline_gasoline_price"] = float(gasoline_price)
    baseline["baseline_burden_share"] = (
        baseline["baseline_fuel_spending_millions"] / baseline["total_expenditure_millions"]
    )
    baseline["_quintile_order"] = baseline["group"].map(QUINTILE_ORDER).fillna(99)
    return baseline.sort_values("_quintile_order").drop(columns=["_quintile_order"]).reset_index(drop=True)
