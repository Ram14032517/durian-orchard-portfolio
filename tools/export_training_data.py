"""Export Farm IoT Google Sheets snapshots into model-friendly CSV files.

The input is an .xlsx export of the Google Sheets workbook. The script keeps
the source tables separate to avoid accidental time leakage between sensor
readings and forecasts.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


SENSOR_SHEET = "readings_15min"
SOURCE_SHEETS = ("readings_15min", "forecast_hourly", "forecast_daily", "ndvi_daily")
SENSOR_ID_COLUMNS = ("event_id", "recorded_at", "recorded_at_th", "device_id")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_xlsx", type=Path, help="Downloaded Google Sheets .xlsx file")
    parser.add_argument("output_dir", type=Path, help="Directory for CSV files and report")
    return parser.parse_args()


def clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame.replace([np.inf, -np.inf], np.nan)


def load_source_tables(path: Path) -> dict[str, pd.DataFrame]:
    workbook = pd.ExcelFile(path)
    missing = [sheet for sheet in SOURCE_SHEETS if sheet not in workbook.sheet_names]
    if missing:
        raise ValueError(f"Workbook is missing sheets: {', '.join(missing)}")
    return {sheet: clean_frame(pd.read_excel(path, sheet_name=sheet)) for sheet in SOURCE_SHEETS}


def prepare_sensor_training(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in SENSOR_ID_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{SENSOR_SHEET} is missing columns: {', '.join(missing)}")

    output = frame.drop_duplicates(subset=["event_id"], keep="last").copy()
    output["recorded_at"] = pd.to_datetime(output["recorded_at"], utc=True, errors="coerce")
    output["recorded_at_th"] = pd.to_datetime(output["recorded_at_th"], errors="coerce")
    output = output.dropna(subset=["event_id", "recorded_at", "device_id"])
    output = output.sort_values(["device_id", "recorded_at"]).reset_index(drop=True)

    local_time = output["recorded_at"].dt.tz_convert("Asia/Bangkok")
    hour = local_time.dt.hour + local_time.dt.minute / 60.0
    day_of_year = local_time.dt.dayofyear
    output["hour_sin"] = np.sin(2 * math.pi * hour / 24.0)
    output["hour_cos"] = np.cos(2 * math.pi * hour / 24.0)
    output["day_of_year_sin"] = np.sin(2 * math.pi * day_of_year / 365.25)
    output["day_of_year_cos"] = np.cos(2 * math.pi * day_of_year / 365.25)
    return output


def table_report(frame: pd.DataFrame) -> dict[str, object]:
    return {
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "duplicate_rows": int(frame.duplicated().sum()),
        "missing_percent": {
            str(column): round(float(frame[column].isna().mean() * 100), 3)
            for column in frame.columns
        },
    }


def sensor_report(frame: pd.DataFrame) -> dict[str, object]:
    report = table_report(frame)
    timestamp = pd.to_datetime(frame["recorded_at"], utc=True, errors="coerce")
    ordered = frame.assign(_timestamp=timestamp).sort_values(["device_id", "_timestamp"])
    intervals = ordered.groupby("device_id")["_timestamp"].diff().dt.total_seconds().div(60)
    report.update(
        {
            "time_start_utc": timestamp.min().isoformat() if timestamp.notna().any() else None,
            "time_end_utc": timestamp.max().isoformat() if timestamp.notna().any() else None,
            "devices": {str(key): int(value) for key, value in frame["device_id"].value_counts().items()},
            "median_interval_minutes": round(float(intervals.median()), 3) if intervals.notna().any() else None,
            "gaps_over_30_minutes": int((intervals > 30).sum()),
            "duplicate_event_ids": int(frame["event_id"].duplicated().sum()),
        }
    )
    return report


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig", date_format="%Y-%m-%dT%H:%M:%S%z")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tables = load_source_tables(args.input_xlsx)

    for sheet, frame in tables.items():
        write_csv(frame, args.output_dir / f"{sheet}.csv")

    training = prepare_sensor_training(tables[SENSOR_SHEET])
    write_csv(training, args.output_dir / "sensor_training_unlabeled.csv")

    report = {
        "source_file": args.input_xlsx.name,
        "warning": "No symptom/disease target label is present; use this export for EDA or unsupervised anomaly detection.",
        "tables": {sheet: table_report(frame) for sheet, frame in tables.items()},
        "sensor_training": sensor_report(training),
    }
    (args.output_dir / "data_quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
