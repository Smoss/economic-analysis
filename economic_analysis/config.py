from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    bea_api_key: str | None
    bls_api_key: str | None


def load_settings(data_dir: Path | None = None) -> Settings:
    return Settings(
        data_dir=data_dir or Path("data"),
        bea_api_key=os.getenv("BEA_API_KEY") or None,
        bls_api_key=os.getenv("BLS_API_KEY") or None,
    )
