"""Mask repeated weather in a separate CSV; preserve original rows and soil.

Offline rule: mark the entire observed run when five weather values repeat
for >=60 minutes. Break runs at missing values, device changes or gaps >30m.
The first reading is masked conservatively too; exact unplug times are unknown.
"""
from pathlib import Path
import argparse
import pandas as pd

SIGNATURE = ['outdoor_temperature_c', 'outdoor_humidity_percent',
             'pressure_hpa', 'light_lux', 'uv_index']
WEATHER = ['air_temperature_c', 'humidity_percent', 'outdoor_temperature_c',
           'outdoor_humidity_percent', 'pressure_hpa', 'wind_avg', 'wind_gust',
           'rain_1h_mm', 'rain_24h_mm', 'rain_rate_mm_h', 'uv_index',
           'dew_point_c', 'feels_like_c', 'heat_index_c', 'light_lux']


def clean(raw):
    work = raw.copy()
    work['_order'] = range(len(work))
    work['_time'] = pd.to_datetime(work.recorded_at, utc=True, errors='raise')
    work = work.sort_values(['device_id', '_time', '_order'])
    complete = work[SIGNATURE].notna().all(axis=1)
    same = work[SIGNATURE].eq(work[SIGNATURE].shift()).all(axis=1)
    same &= complete & complete.shift(fill_value=False)
    same &= work.device_id.eq(work.device_id.shift())
    gap = work.groupby('device_id')['_time'].diff().dt.total_seconds().div(60)
    work['_run'] = (~same | gap.gt(30)).cumsum()
    runs = work.groupby('_run').agg(device_id=('device_id', 'first'),
        start_utc=('_time', 'min'), end_utc=('_time', 'max'), rows=('_time', 'size'))
    runs['duration_minutes'] = (runs.end_utc-runs.start_utc).dt.total_seconds()/60
    runs = runs.loc[runs.duration_minutes.ge(60)].copy()
    work['weather_stale_suspected'] = work['_run'].isin(runs.index)
    work['weather_missing_original'] = work[WEATHER].isna().any(axis=1)
    work['weather_cleaning_reason'] = ''
    mask = work.weather_stale_suspected
    work.loc[mask, WEATHER] = float('nan')
    work.loc[mask, 'weather_cleaning_reason'] = 'repeated_signature_60min_offline_full_run'
    work = work.sort_values('_order').drop(columns=['_order', '_time', '_run'])
    return work, runs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output_directory', type=Path)
    args = parser.parse_args()
    raw = pd.read_csv(args.input)
    result, runs = clean(raw)
    args.output_directory.mkdir(parents=True, exist_ok=True)
    target = args.output_directory / 'readings_15min_weather_clean.csv'
    if target.resolve() == args.input.resolve():
        raise ValueError('Output must differ from input')
    # Verify preservation and masking before writing outputs.
    preserved = [c for c in raw.columns if c not in WEATHER]
    pd.testing.assert_frame_equal(raw[preserved], result[preserved])
    mask = result.weather_stale_suspected
    assert result.loc[mask, WEATHER].isna().all().all()
    pd.testing.assert_frame_equal(raw.loc[~mask, WEATHER], result.loc[~mask, WEATHER])
    result.to_csv(target, index=False)
    runs.to_csv(args.output_directory / 'weather_stale_intervals.csv', index=False)
    print(f'Rows preserved: {len(result)}; masked rows: {mask.sum()}; runs: {len(runs)}')
    print(target)
