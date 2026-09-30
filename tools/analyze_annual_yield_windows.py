"""Retrospective annual yield benchmark; one row per province-year, not month."""
import calendar
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from prepare_monthly_training import daily_profile, previous_month, WEATHER
from train_monthly_production import fit_ridge, predict, mae

BASE = Path(__file__).resolve().parents[1] / 'research_data/five_province_history'

def months_before(year, month, count):
    if not 1 <= month <= 12 or not 1 <= count <= 6:
        raise ValueError('Month must be 1..12 and window 1..6')
    result = []
    for _ in range(count):
        year, month = previous_month(year, month)
        result.append((year, month))
    return result

def aggregate_window(daily, province, year, month, count):
    values = {f: [] for f in WEATHER}
    for y, m in months_before(year, month, count):
        group = daily.get((province, y, m), {})
        for field in WEATHER:
            v = group.get(field, [])
            if len(v) != calendar.monthrange(y, m)[1] or not np.isfinite(v).all():
                return {f: np.nan for f in WEATHER}
            values[field].extend(v)
    return {f: sum(v) if f == 'rain_mm' else float(np.mean(v)) for f, v in values.items()}

def annual_yield(production_tonnes, bearing_rai):
    if not (np.isfinite(production_tonnes) and production_tonnes >= 0
            and np.isfinite(bearing_rai) and bearing_rai > 0):
        return np.nan
    return production_tonnes * 1000 / bearing_rai

def main():
    annual = pd.read_csv(BASE/'production_annual.csv', dtype={'province_code':str})
    harvest = pd.read_csv(BASE/'harvest_monthly.csv', dtype={'province_code':str})
    assert not annual.duplicated(['province_code','year_ce']).any()
    # Freeze anchor from training years only. It is NOT an observed orchard stage.
    peak = harvest[harvest.year_ce.le(2021)].groupby(['province_code','month_number']).tonnes.sum()
    anchors = {p:int(peak.loc[p].idxmax()) for p in sorted(annual.province_code.unique())}
    daily = daily_profile()
    rows = []
    for r in annual.itertuples():
        target = annual_yield(r.production_tonnes, r.bearing_rai)
        if not np.isfinite(target):
            continue
        row = dict(province_code=r.province_code,province_name=r.province_name,year_ce=r.year_ce,
                   anchor_month=anchors[r.province_code],yield_kg_rai=target)
        for window in range(1,7):
            values = aggregate_window(daily,r.province_code,r.year_ce,row['anchor_month'],window)
            row.update({f'w{window}_{f}': value for f,value in values.items()})
        rows.append(row)
    panel = pd.DataFrame(rows)
    features = [c for c in panel if c.startswith('w') and c[1].isdigit()]
    usable = panel.dropna(subset=features).copy()
    usable['split'] = np.select([usable.year_ce.le(2021),usable.year_ce.le(2023)],['train','validation'],default='test')
    usable = usable[usable.year_ce.le(2025)]
    frames = {s:usable[usable.split.eq(s)] for s in ['train','validation','test']}
    assert all(not f.empty for f in frames.values())
    codes = sorted(annual.province_code.unique())
    def design(frame, window):
        x = np.column_stack([frame.province_code.eq(p).to_numpy(float) for p in codes] + [(frame.year_ce-2000).to_numpy(float)])
        if window:
            x = np.column_stack([x,frame[[f'w{window}_{f}' for f in WEATHER]].to_numpy(float)])
        return x
    metrics, predictions, tuning = [], [], []
    for window in range(7):
        train, valid = frames['train'],frames['validation']
        candidates = []
        for alpha in [1.,10.,100.]:
            model = fit_ridge(design(train,window),train.yield_kg_rai.to_numpy(),alpha)
            score = mae(valid.yield_kg_rai,predict(model,design(valid,window)))
            candidates.append((score,model))
            tuning.append(dict(window_months=window,alpha=alpha,validation_mae_kg_rai=score))
        _,model = min(candidates,key=lambda item:item[0])
        for split in ['validation','test']:
            frame = frames[split]
            estimates = predict(model,design(frame,window))
            metrics.append(dict(window_months=window,split=split,n=len(frame),mae_kg_rai=mae(frame.yield_kg_rai,estimates),alpha=model['alpha']))
            for r,estimate in zip(frame.itertuples(),estimates):
                predictions.append(dict(window_months=window,split=split,province_code=r.province_code,year_ce=r.year_ce,actual_kg_rai=r.yield_kg_rai,predicted_kg_rai=float(estimate)))
    out = BASE/'training'
    panel.to_csv(out/'annual_yield_windows_panel.csv',index=False,encoding='utf-8-sig')
    scores = pd.DataFrame(metrics)
    scores.to_csv(out/'annual_yield_windows_metrics.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(predictions).to_csv(out/'annual_yield_windows_predictions.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(tuning).to_csv(out/'annual_yield_windows_tuning.csv',index=False,encoding='utf-8-sig')
    selected = int(scores[scores.split.eq('validation')].sort_values('mae_kg_rai').iloc[0].window_months)
    info = dict(selected_window_by_validation=selected,anchors=anchors,rows=len(panel),complete_rows=len(usable),
                split_counts={s:len(f) for s,f in frames.items()},
                sources={f:hashlib.sha256((BASE/f).read_bytes()).hexdigest() for f in ['production_annual.csv','harvest_monthly.csv','weather_daily.csv']},
                limits=['Annual provincial yield, all varieties; not monthly or orchard yield',
                'Anchor is the highest total harvest month in available training records through 2021; not actual yearly phenology',
                'Cumulative full calendar months BEFORE anchor, with day-weighted means and total rain',
                'Province and linear year trend baseline; identical complete rows for every window',
                'Validation 2022-2023 selects alpha/window; test 2024-2025 has only 10 province-years at most',
                'Retrospective revised data; no causal claims or operational forecast validation'])
    (out/'annual_yield_windows_info.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(scores.to_string(index=False))
    print(json.dumps(info,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
