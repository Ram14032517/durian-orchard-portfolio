"""Build compact daily Farm IoT environment statistics as JSON for Sheets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


WEATHER_KEY = [
    "outdoor_temperature_c",
    "outdoor_humidity_percent",
    "pressure_hpa",
]


def main() -> None:
    data = pd.read_csv(Path(sys.argv[1]))
    data["recorded_at"] = pd.to_datetime(data["recorded_at"], utc=True, errors="coerce")
    data = data.dropna(subset=["recorded_at"]).sort_values("recorded_at").reset_index(drop=True)
    local = data["recorded_at"].dt.tz_convert("Asia/Bangkok")
    data["date"] = local.dt.strftime("%Y-%m-%d")

    valid = data[WEATHER_KEY].notna().all(axis=1)
    changed = data[WEATHER_KEY].ne(data[WEATHER_KEY].shift()).any(axis=1)
    run_id = changed.cumsum()
    run_start = data.groupby(run_id)["recorded_at"].transform("min")
    stale_minutes = (data["recorded_at"] - run_start).dt.total_seconds().div(60)
    data["weather_stale"] = valid & (stale_minutes >= 60)
    data["weather_usable"] = valid & ~data["weather_stale"]

    data["wet_alert"] = data["weather_usable"] & (
        (data["soil_moisture_percent"] >= 43.5).astype(int)
        + (data["outdoor_humidity_percent"] >= 75).astype(int)
        + (data["rain_1h_mm"].fillna(0) > 0).astype(int)
        >= 2
    )
    data["light_usable"] = data["light_lux"].where(data["weather_usable"])
    data["uv_usable"] = data["uv_index"].where(data["weather_usable"])
    data["humidity_usable"] = data["outdoor_humidity_percent"].where(data["weather_usable"])
    data["rain_usable"] = data["rain_1h_mm"].where(data["weather_usable"], 0)

    grouped = data.groupby("date", sort=True)
    summary = grouped.agg(
        reading_count=("event_id", "size"),
        usable_weather_count=("weather_usable", "sum"),
        stale_weather_count=("weather_stale", "sum"),
        avg_soil_moisture_percent=("soil_moisture_percent", "mean"),
        avg_humidity_percent=("humidity_usable", "mean"),
        rain_1h_sum_mm=("rain_usable", "sum"),
        avg_light_lux=("light_usable", "mean"),
        max_light_lux=("light_usable", "max"),
        avg_uv_index=("uv_usable", "mean"),
        max_uv_index=("uv_usable", "max"),
        wet_environment_alert_count=("wet_alert", "sum"),
    ).reset_index()
    summary["light_exposure_klux_hours"] = grouped["light_usable"].sum().values * 0.25 / 1000
    summary["wet_environment_alert_rate"] = (
        summary["wet_environment_alert_count"]
        / summary["usable_weather_count"].replace(0, np.nan)
    ).fillna(0)
    summary["risk_level"] = np.select(
        [summary["wet_environment_alert_rate"] >= 0.5,
         summary["wet_environment_alert_rate"] >= 0.2],
        ["high", "medium"],
        default="low",
    )
    summary["method"] = "environment proxy; not NDVI or disease diagnosis"

    columns = [
        "date", "reading_count", "usable_weather_count", "stale_weather_count",
        "avg_soil_moisture_percent", "avg_humidity_percent", "rain_1h_sum_mm",
        "avg_light_lux", "max_light_lux", "light_exposure_klux_hours",
        "avg_uv_index", "max_uv_index", "wet_environment_alert_count",
        "wet_environment_alert_rate", "risk_level", "method",
    ]
    rows = []
    for record in summary[columns].round(4).to_dict("records"):
        rows.append([None if pd.isna(record[column]) else record[column] for column in columns])
    print(json.dumps({"headers": columns, "rows": rows}, ensure_ascii=False))


if __name__ == "__main__":
    main()
