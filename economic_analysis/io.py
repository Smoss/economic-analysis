from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    ensure_dir(path.parent)
    path.write_text(payload, encoding="utf-8")


def write_dataset(data_dir: Path, dataset: str, frame: pd.DataFrame, metadata: dict[str, Any]) -> dict[str, str]:
    processed_dir = data_dir / "processed" / dataset
    ensure_dir(processed_dir)
    csv_path = processed_dir / f"{dataset}.csv"
    parquet_path = processed_dir / f"{dataset}.parquet"
    metadata_path = processed_dir / "metadata.json"

    frame.to_csv(csv_path, index=False)
    frame.to_parquet(parquet_path, index=False)
    write_json(metadata_path, metadata)

    return {
        "csv": str(csv_path),
        "parquet": str(parquet_path),
        "metadata": str(metadata_path),
    }
