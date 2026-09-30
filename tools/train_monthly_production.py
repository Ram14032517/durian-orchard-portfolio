"""Offline chronological research benchmark. No disease labels or causal claims."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1] / 'research_data/five_province_history/training'
WEATHER = ['lag1_temperature_c','lag1_rain_mm','lag1_humidity_pct','lag1_solar_mj_m2_day']

def design(frame, weather=False):
    # Fixed category vocabulary: encoding does not learn anything from held-out targets.
    group = frame.province_code.astype(str) + '_' + frame.month.astype(str)
    names = [f'{p}_{m}' for p in ['22','33','53','84','86'] for m in range(1,13)]
    x = np.column_stack([(group == name).astype(float).to_numpy() for name in names])
    if weather:
        x = np.column_stack([x, frame[WEATHER].to_numpy(float)])
        names += WEATHER
    return x, names

def fit_ridge(x, y, alpha):
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1
    centered = (x - mean) / scale
    intercept = float(y.mean())
    coef = np.linalg.solve(centered.T @ centered + alpha*np.eye(x.shape[1]), centered.T @ (y-intercept))
    return dict(mean=mean.tolist(), scale=scale.tolist(), coef=coef.tolist(), intercept=intercept, alpha=alpha)

def predict(model, x):
    return np.maximum(0, ((x-np.array(model['mean']))/np.array(model['scale'])) @ np.array(model['coef']) + model['intercept'])

def mae(actual, predicted):
    return float(np.mean(np.abs(np.asarray(actual)-np.asarray(predicted))))

def main():
    data = pd.read_csv(BASE/'monthly_model_panel.csv', dtype={'province_code':str})
    data = data[data.eligible_for_baseline.eq(1)].copy()
    train = data[data.suggested_split.eq('train')]
    valid = data[data.suggested_split.eq('validation')]
    test = data[data.suggested_split.eq('test')]
    if any(f.empty for f in [train, valid, test]): raise ValueError('Empty split')
    assert train.year_ce.max() < valid.year_ce.min() <= valid.year_ce.max() < test.year_ce.min()
    target = 'target_production_tonnes'
    medians = train.groupby(['province_code','month'])[target].median()
    province_medians = train.groupby('province_code')[target].median()
    def seasonal(frame):
        return np.array([medians.get((r.province_code,r.month),province_medians.get(r.province_code,train[target].median())) for r in frame.itertuples()])
    predictions = {'seasonal_median': {'validation':seasonal(valid), 'test':seasonal(test)}}
    saved_models, tuning = {}, []
    for name, use_weather in [('ridge_season',False),('ridge_weather',True)]:
        x, features = design(train,use_weather)
        xv,_ = design(valid,use_weather)
        candidates = []
        for alpha in [1.,10.,100.]:
            model = fit_ridge(x,train[target].to_numpy(),alpha)
            score = mae(valid[target],predict(model,xv))
            candidates.append((score,model))
            tuning.append(dict(model=name,alpha=alpha,validation_mae_tonnes=score))
        _, model = min(candidates,key=lambda pair:pair[0])
        saved_models[name] = dict(model, features=features)
        predictions[name] = {'validation':predict(model,xv), 'test':predict(model,design(test,use_weather)[0])}
    selected = min(predictions, key=lambda name: mae(valid[target],predictions[name]['validation']))
    metrics, rows = [], []
    for name, splits in predictions.items():
        for split, frame in [('validation',valid),('test',test)]:
            values = splits[split]
            for province in ['ALL',*sorted(frame.province_code.unique())]:
                mask = np.ones(len(frame),dtype=bool) if province == 'ALL' else frame.province_code.eq(province).to_numpy()
                metrics.append(dict(model=name,split=split,province_code=province,n=int(mask.sum()),mae_tonnes=mae(frame[target].to_numpy()[mask],values[mask])))
            for (_,r), estimate in zip(frame.iterrows(),values):
                rows.append(dict(model=name,split=split,province_code=r.province_code,target_month=r.target_month,actual_tonnes=r[target],predicted_tonnes=float(estimate)))
    pd.DataFrame(metrics).to_csv(BASE/'model_metrics.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(rows).to_csv(BASE/'model_predictions.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(tuning).to_csv(BASE/'model_validation.csv',index=False,encoding='utf-8-sig')
    result = dict(selected_by_validation=selected, training_rows=len(train),validation_rows=len(valid),test_rows=len(test),
                  models=saved_models, seasonal_medians={f'{p}_{m}':float(v) for (p,m),v in medians.items()},
                  province_medians=province_medians.to_dict(),global_median=float(train[target].median()),
                  limitations=['Retrospective revised data, not a point-in-time forecast test',
                  'Only months with reported production evaluated; missing months are not zero',
                  'No causal attribution, no orchard health or irrigation recommendation',
                  'No refit on validation; compare weather ridge against season-only ridge, not just median'])
    (BASE/'model_baseline.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(pd.DataFrame(metrics).query("province_code == 'ALL'").to_string(index=False))
    print('Selected only by validation:',selected)

if __name__ == '__main__': main()
