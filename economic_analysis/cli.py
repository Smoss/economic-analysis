from __future__ import annotations

import argparse

from economic_analysis.config import load_settings
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

    parser.error(f"Unsupported command: {args.command}")
    return 2
