"""Exploratory, chronological comparison of annual provincial yield predictors.

Run after analyze_annual_yield_windows.py. These associations are not causal effects.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from train_monthly_production import fit_ridge, predict, mae

BASE = Path(__file__).resolve().parents[1] / 'research_data/five_province_history'
OUT = BASE / 'training'
FIELDS = {
    'temperature_c': 'อุณหภูมิ',
    'rain_mm': 'ฝน',
    'humidity_pct': 'ความชื้นอากาศ',
    'solar_mj_m2_day': 'รังสีดวงอาทิตย์',
}


def main():
    panel = pd.read_csv(OUT / 'annual_yield_windows_panel.csv', dtype={'province_code': str})
    info = json.loads((OUT / 'annual_yield_windows_info.json').read_text(encoding='utf-8'))
    window = info['selected_window_by_validation']
    if window != 6:
        raise ValueError('Expected pre-selected six-month window; inspect method before rerunning')
    panel = panel[panel.year_ce.le(2025)].copy()
    cols = [f'w{window}_{field}' for field in FIELDS]
    panel = panel.dropna(subset=['yield_kg_rai', *cols])
    if panel.duplicated(['province_code', 'year_ce']).any():
        raise ValueError('Duplicate province-year')
    train = panel[panel.year_ce.le(2021)]
    valid = panel[panel.year_ce.between(2022, 2023)]
    test = panel[panel.year_ce.between(2024, 2025)]
    if (len(train), len(valid), len(test)) != (125, 10, 10):
        raise ValueError('Panel/split changed; audit before interpreting scores')
    codes = sorted(panel.province_code.unique())

    def design(frame, fields):
        parts = [frame.province_code.eq(code).to_numpy(float) for code in codes]
        parts.append((frame.year_ce - 2000).to_numpy(float))
        parts.extend(frame[f'w{window}_{field}'].to_numpy(float) for field in fields)
        return np.column_stack(parts)

    variants = [('baseline', [], 'จังหวัด + แนวโน้มปี')]
    variants += [(field, [field], label) for field, label in FIELDS.items()]
    variants.append(('all_weather', list(FIELDS), 'อากาศ 4 ค่า'))
    scores = []
    for key, fields, label in variants:
        candidates = []
        for alpha in (1., 10., 100.):
            model = fit_ridge(design(train, fields), train.yield_kg_rai.to_numpy(), alpha)
            candidates.append((mae(valid.yield_kg_rai, predict(model, design(valid, fields))), model))
        _, model = min(candidates, key=lambda item: item[0])
        scores.append({
            'key': key, 'label': label, 'alpha': model['alpha'],
            'validation_mae_kg_rai': mae(valid.yield_kg_rai, predict(model, design(valid, fields))),
            'test_mae_kg_rai': mae(test.yield_kg_rai, predict(model, design(test, fields))),
        })
    result = {
        'method': 'ridge; all variants contain province indicators and a linear year trend',
        'target': 'OAE provincial annual production tonnes × 1000 / bearing rai, all durian varieties',
        'window_months': window, 'rows': len(panel),
        'split_counts': {'train': len(train), 'validation': len(valid), 'test': len(test)},
        'splits': {'train': '1997–2021', 'validation': '2022–2023', 'test': '2024–2025'},
        'scores': scores,
        'yearly_context': [
            {'province_code': str(r.province_code), 'year_ce': int(r.year_ce),
             'yield_kg_rai': float(r.yield_kg_rai),
             **{field: float(getattr(r, f'w{window}_{field}')) for field in FIELDS}}
            for r in panel.itertuples()
        ],
        'limits': [
            'Feature comparison is exploratory. The same small 2024–2025 test set is viewed across variants; do not tune a final model on it.',
            'NASA POWER is a province reference-point grid, not orchard weather; no district/soil/yield join.',
            'No verified fruit-drop, irrigation, disease, storm gust, tree-stage or cultivar labels.',
            'Prediction accuracy or a variable association cannot establish why yield changed.',
        ],
    }
    (OUT / 'annual_yield_feature_comparison.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved:', OUT / 'annual_yield_feature_comparison.json')
    for row in scores:
        print(f"{row['key']}: validation MAE {row['validation_mae_kg_rai']:.1f}; test MAE {row['test_mae_kg_rai']:.1f} kg/rai")


if __name__ == '__main__':
    main()
