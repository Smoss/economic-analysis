from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from economic_analysis.config import Settings
from economic_analysis.io import ensure_dir, utc_now_iso
from economic_analysis.sources.noaa_common import (
    BASELINE_END,
    ISSUE_CYCLE,
    LEAD_DAYS,
    PRECIP_OCCURRENCE_THRESHOLD_IN,
    RECENT_START,
    STUDY_END,
    STUDY_START,
    period_bucket,
    station_metadata,
)


def fetch_forecast_accuracy(settings: Settings) -> tuple[pd.DataFrame, dict[str, Any]]:
    forecasts_path = settings.data_dir / "processed" / "noaa_ndfd_forecasts" / "noaa_ndfd_forecasts.csv"
    observations_path = settings.data_dir / "processed" / "noaa_station_observations" / "noaa_station_observations.csv"
    if not forecasts_path.exists() or not observations_path.exists():
        raise RuntimeError(
            "Run `fetch noaa-ndfd-forecasts` and `fetch noaa-station-observations` before "
            "`fetch nws-forecast-accuracy`."
        )

    forecasts = pd.read_csv(forecasts_path)
    observations = pd.read_csv(observations_path)
    detail = score_forecasts(forecasts, observations)
    summary = summarize_accuracy(detail)
    report_outputs = write_accuracy_report(settings.data_dir, summary)
    metadata = {
        "source": "Derived NOAA/NWS NDFD forecast accuracy against NOAA/NCEI station daily observations",
        "source_url": "https://www.ncei.noaa.gov/products/weather-climate-models/national-digital-forecast-database",
        "input_paths": {"forecasts": str(forecasts_path), "observations": str(observations_path)},
        "report_outputs": report_outputs,
        "fetched_at": utc_now_iso(),
        "frequency": "daily",
        "period": {"start": STUDY_START.isoformat(), "end": STUDY_END.isoformat()},
        "comparison": {
            "baseline": {"start": STUDY_START.isoformat(), "end": BASELINE_END.isoformat()},
            "recent": {"start": RECENT_START.isoformat(), "end": STUDY_END.isoformat()},
        },
        "issue_cycle": ISSUE_CYCLE,
        "lead_days": list(LEAD_DAYS),
        "units": {"temperature_error": "degrees_fahrenheit", "precipitation_error": "inches"},
        "stations": station_metadata(),
        "method": "Join station-date NDFD forecasts to daily observations and summarize errors by station, lead, year, month, and period bucket.",
    }
    return detail, metadata


def score_forecasts(forecasts: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    joined = forecasts.merge(
        observations,
        left_on=["station", "valid_date"],
        right_on=["station", "date"],
        how="inner",
        suffixes=("", "_observed"),
    )
    if joined.empty:
        return pd.DataFrame(columns=_detail_columns())

    joined["valid_date"] = pd.to_datetime(joined["valid_date"]).dt.date.astype(str)
    joined["year"] = pd.to_datetime(joined["valid_date"]).dt.year
    joined["month"] = pd.to_datetime(joined["valid_date"]).dt.month
    joined["period_bucket"] = joined["valid_date"].map(period_bucket)
    joined["high_error_f"] = joined["forecast_high_f"] - joined["observed_high_f"]
    joined["low_error_f"] = joined["forecast_low_f"] - joined["observed_low_f"]
    joined["precip_error_in"] = joined["forecast_precip_in"] - joined["observed_precip_in"]
    joined["forecast_precip_occurrence"] = joined["forecast_precip_in"] >= PRECIP_OCCURRENCE_THRESHOLD_IN
    joined["observed_precip_occurrence"] = joined["observed_precip_in"] >= PRECIP_OCCURRENCE_THRESHOLD_IN
    joined["precip_occurrence_correct"] = joined["forecast_precip_occurrence"] == joined["observed_precip_occurrence"]
    joined["precip_brier"] = _brier_score(joined)
    return joined[_detail_columns()].sort_values(["station", "valid_date", "lead_day"]).reset_index(drop=True)


def summarize_accuracy(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame(columns=_summary_columns())

    groups = ["station", "lead_day", "year", "month", "period_bucket"]
    summary = detail.groupby(groups, dropna=False).apply(_summarize_group, include_groups=False).reset_index()
    return summary[_summary_columns()].sort_values(groups).reset_index(drop=True)


def write_accuracy_report(data_dir: Path, summary: pd.DataFrame) -> dict[str, str]:
    output_dir = data_dir.parent / "outputs" if data_dir.name == "data" else data_dir / "outputs"
    ensure_dir(output_dir)
    summary_path = output_dir / "nws_forecast_accuracy_summary.csv"
    chart_path = output_dir / "nws_forecast_accuracy_yearly_mae.svg"
    summary.to_csv(summary_path, index=False)
    chart_path.write_text(_yearly_mae_svg(summary), encoding="utf-8")
    return {"summary_csv": str(summary_path), "chart_svg": str(chart_path)}


def _summarize_group(group: pd.DataFrame) -> pd.Series:
    return pd.Series(
        {
            "rows": len(group),
            "high_mae_f": group["high_error_f"].abs().mean(),
            "high_rmse_f": _rmse(group["high_error_f"]),
            "high_bias_f": group["high_error_f"].mean(),
            "low_mae_f": group["low_error_f"].abs().mean(),
            "low_rmse_f": _rmse(group["low_error_f"]),
            "low_bias_f": group["low_error_f"].mean(),
            "precip_amount_mae_in": group["precip_error_in"].abs().mean(),
            "precip_occurrence_accuracy": group["precip_occurrence_correct"].mean(),
            "precip_brier": group["precip_brier"].mean(),
        }
    )


def _rmse(values: pd.Series) -> float:
    return float(math.sqrt((values.dropna() ** 2).mean()))


def _brier_score(frame: pd.DataFrame) -> pd.Series:
    observed = frame["observed_precip_occurrence"].astype(float)
    if "forecast_pop_pct" in frame and frame["forecast_pop_pct"].notna().any():
        probability = (pd.to_numeric(frame["forecast_pop_pct"], errors="coerce") / 100).clip(0, 1)
    else:
        probability = frame["forecast_precip_occurrence"].astype(float)
    return (probability - observed) ** 2


def _yearly_mae_svg(summary: pd.DataFrame) -> str:
    yearly = summary.groupby("year", dropna=True)[["high_mae_f", "low_mae_f"]].mean().reset_index()
    if yearly.empty:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="360"></svg>\n'

    width, height = 720, 360
    margin = 48
    values = ((yearly["high_mae_f"] + yearly["low_mae_f"]) / 2).fillna(0)
    max_value = max(float(values.max()), 1.0)
    bar_width = (width - 2 * margin) / len(yearly)
    bars: list[str] = []
    for index, row in yearly.iterrows():
        value = float(values.iloc[index])
        bar_height = (height - 2 * margin) * value / max_value
        x = margin + index * bar_width + 4
        y = height - margin - bar_height
        color = "#b23a48" if int(row["year"]) >= 2024 else "#2f6f73"
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width - 8:.1f}" height="{bar_height:.1f}" fill="{color}" />'
        )
        bars.append(
            f'<text x="{x + (bar_width - 8) / 2:.1f}" y="{height - 24}" text-anchor="middle" font-size="11">{int(row["year"])}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img" '
        f'aria-label="NWS forecast yearly mean absolute error">\n'
        '<rect width="100%" height="100%" fill="white" />\n'
        '<text x="48" y="28" font-size="18" font-family="sans-serif">NDFD yearly temperature MAE</text>\n'
        f'<line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" stroke="#333" />\n'
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" stroke="#333" />\n'
        + "\n".join(bars)
        + "\n</svg>\n"
    )


def _detail_columns() -> list[str]:
    return [
        "station",
        "station_id",
        "valid_date",
        "issue_date",
        "issue_cycle",
        "lead_day",
        "year",
        "month",
        "period_bucket",
        "forecast_high_f",
        "observed_high_f",
        "high_error_f",
        "forecast_low_f",
        "observed_low_f",
        "low_error_f",
        "forecast_precip_in",
        "observed_precip_in",
        "precip_error_in",
        "forecast_pop_pct",
        "forecast_precip_occurrence",
        "observed_precip_occurrence",
        "precip_occurrence_correct",
        "precip_brier",
    ]


def _summary_columns() -> list[str]:
    return [
        "station",
        "lead_day",
        "year",
        "month",
        "period_bucket",
        "rows",
        "high_mae_f",
        "high_rmse_f",
        "high_bias_f",
        "low_mae_f",
        "low_rmse_f",
        "low_bias_f",
        "precip_amount_mae_in",
        "precip_occurrence_accuracy",
        "precip_brier",
    ]
