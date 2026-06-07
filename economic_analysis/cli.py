from __future__ import annotations

import argparse

from economic_analysis.config import load_settings
from economic_analysis.oil_model import (
    DEFAULT_BASELINE_SUPPLY_MBD,
    DEFAULT_CRUDE_DEMAND_ELASTICITY,
    parse_oil_price_scenarios,
    parse_supply_shock_scenarios,
    run_oil_consumer_burden_model,
)
from economic_analysis.pipeline import FETCHERS, fetch_all, normalize_data_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="economic-analysis")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch", help="Fetch and normalize economic datasets.")
    fetch.add_argument(
        "dataset",
        choices=[*FETCHERS.keys(), "all"],
        help="Dataset to fetch.",
    )
    fetch.add_argument("--data-dir", default=None, help="Output data directory. Defaults to ./data.")
    fetch.add_argument("--dry-run", action="store_true", help="Print intended outputs without network calls.")

    model = subparsers.add_parser("model", help="Run derived economic models.")
    model_subparsers = model.add_subparsers(dest="model_name", required=True)
    oil = model_subparsers.add_parser("oil-consumer-burden", help="Run oil-price consumer burden scenarios.")
    oil.add_argument("--data-dir", default=None, help="Input data directory. Defaults to ./data.")
    oil.add_argument("--output-dir", default="outputs", help="Output directory. Defaults to ./outputs.")
    oil.add_argument(
        "--oil-prices",
        default=None,
        help="Comma-separated oil price scenarios in dollars per barrel. Defaults to 40,60,80,100,120,140.",
    )
    oil.add_argument(
        "--supply-shocks-mbd",
        default=None,
        help="Comma-separated net crude supply gaps in million barrels/day. Defaults to 1,3,5,8,10 in shock mode.",
    )
    oil.add_argument(
        "--baseline-supply-mbd",
        type=float,
        default=None,
        help="Baseline crude market size in million barrels/day. Defaults to 100 in shock mode.",
    )
    oil.add_argument(
        "--crude-demand-elasticity",
        type=float,
        default=None,
        help="Short-run crude demand elasticity. Defaults to -0.10 in shock mode.",
    )
    oil.add_argument(
        "--baseline-oil-price",
        type=float,
        default=None,
        help="Baseline WTI oil price in dollars per barrel. Defaults to latest annual WTI in shock mode.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings(normalize_data_dir(args.data_dir))

    if args.command == "fetch":
        results = (
            fetch_all(settings, args.dry_run)
            if args.dataset == "all"
            else [FETCHERS[args.dataset](settings, args.dry_run)]
        )
        for result in results:
            prefix = "would write" if args.dry_run else "wrote"
            print(f"{result.dataset}: {result.rows} rows, {prefix} {result.outputs}")
        return 0

    if args.command == "model" and args.model_name == "oil-consumer-burden":
        settings = load_settings(normalize_data_dir(args.data_dir))
        output_dir = normalize_data_dir(args.output_dir)
        if output_dir is None:
            raise RuntimeError("Output directory is required.")
        supply_mode = any(
            value is not None
            for value in [
                args.supply_shocks_mbd,
                args.baseline_supply_mbd,
                args.crude_demand_elasticity,
                args.baseline_oil_price,
            ]
        )
        if args.oil_prices is not None and supply_mode:
            parser.error("Use either --oil-prices or supply-shock options, not both.")

        oil_prices = None if supply_mode else parse_oil_price_scenarios(args.oil_prices)
        supply_shocks_mbd = parse_supply_shock_scenarios(args.supply_shocks_mbd) if supply_mode else None
        baseline_supply_mbd = (
            args.baseline_supply_mbd if args.baseline_supply_mbd is not None else DEFAULT_BASELINE_SUPPLY_MBD
        )
        crude_demand_elasticity = (
            args.crude_demand_elasticity
            if args.crude_demand_elasticity is not None
            else DEFAULT_CRUDE_DEMAND_ELASTICITY
        )
        frame, output_path = run_oil_consumer_burden_model(
            settings.data_dir,
            output_dir,
            oil_prices=oil_prices,
            supply_shocks_mbd=supply_shocks_mbd,
            baseline_supply_mbd=baseline_supply_mbd,
            crude_demand_elasticity=crude_demand_elasticity,
            baseline_oil_price=args.baseline_oil_price,
        )
        print(f"oil_consumer_burden: {len(frame)} rows, wrote {output_path}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2
