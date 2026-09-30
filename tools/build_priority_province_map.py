"""Build the advisor-scoped durian priority-province dataset and one-country map.

Selection = top 3 production provinces within each DPM region, union the
national top 12, for the latest available OAE year. Missing soil overlays stay
explicitly missing; a province-wide soil label is never substituted.
"""
from __future__ import annotations

import json
from pathlib import Path

import folium
import numpy as np
import pandas as pd
from branca.element import Element

ROOT = Path(__file__).resolve().parents[1]
NATIONAL = ROOT / "research_data/thailand_comparison"
REGIONAL = ROOT / "research_data/regional_orchards"
OAE_MONTHLY = ROOT / "research_data/external/oae_2026-09-17/durian_monthly_province.xlsx"
OUT = ROOT / "research_data/priority_provinces"
MONTH_ORDER = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
               "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]


def load_priority() -> tuple[pd.DataFrame, int]:
    production = pd.read_csv(NATIONAL / "production_province_year.csv", dtype={"province_code": str})
    year = int(production.year_ce.max())
    latest = production.loc[production.year_ce.eq(year)].copy()
    assert not latest.duplicated("province_code").any()
    latest["national_rank"] = latest.production_tonnes.rank(method="first", ascending=False).astype(int)
    latest["regional_rank"] = latest.groupby("region").production_tonnes.rank(
        method="first", ascending=False).astype(int)
    latest["selected_national_top12"] = latest.national_rank.le(12)
    latest["selected_regional_top3"] = latest.regional_rank.le(3)
    selected = latest.loc[latest.selected_national_top12 | latest.selected_regional_top3].copy()
    selected["selection_reason"] = np.select(
        [selected.selected_national_top12 & selected.selected_regional_top3,
         selected.selected_national_top12, selected.selected_regional_top3],
        ["Top 12 ประเทศ + Top 3 ภาค", "Top 12 ประเทศ", "Top 3 ภาค"],
        default="ไม่เข้าเกณฑ์")
    return selected.sort_values(["region", "regional_rank"]), year


def add_monthly_season(selected: pd.DataFrame, year_ce: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_excel(OAE_MONTHLY, sheet_name="durian_monthly")
    raw["year_ce"] = pd.to_numeric(raw.year) - 543
    monthly = raw.loc[raw.year_ce.eq(year_ce) & raw.province_name.isin(selected.province_name)].copy()
    pct = monthly.loc[monthly.item.eq("ร้อยละผลผลิตรายเดือน"),
                      ["province_name", "month", "data"]].rename(columns={"data": "production_share_pct"})
    tonnes = monthly.loc[monthly.item.eq("ปริมาณผลผลิตรายเดือน"),
                         ["province_name", "month", "data"]].rename(columns={"data": "monthly_production_tonnes"})
    season = pct.merge(tonnes, on=["province_name", "month"], validate="one_to_one")
    season["month_number"] = season.month.map({m: i + 1 for i, m in enumerate(MONTH_ORDER)})
    assert season.month_number.notna().all()
    season = season.sort_values(["province_name", "month_number"])
    checks = season.groupby("province_name").agg(
        share_sum=("production_share_pct", "sum"), tonnes_sum=("monthly_production_tonnes", "sum"))
    annual = selected.set_index("province_name").production_tonnes
    assert checks.share_sum.sub(100).abs().lt(0.11).all()
    assert checks.tonnes_sum.sub(annual.loc[checks.index]).abs().lt(1).all()
    summaries = []
    for province, group in season.groupby("province_name"):
        peak = group.loc[group.production_share_pct.idxmax()]
        material = group.loc[group.production_share_pct.ge(10), "month"].tolist()
        summaries.append({
            "province_name": province,
            "peak_month": peak.month,
            "peak_share_pct": float(peak.production_share_pct),
            "reported_months": ", ".join(group.month.tolist()),
            "months_at_least_10pct": ", ".join(material) if material else "ไม่มีเดือนถึง 10%",
            "reported_month_count": len(group),
        })
    return selected.merge(pd.DataFrame(summaries), on="province_name", validate="one_to_one"), season


def add_soil_status(selected: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    soil_path = REGIONAL / "soil_series_comparison.csv"
    overlay_path = REGIONAL / "overlay_summaries.json"
    soil = pd.read_csv(soil_path, dtype={"province_code": str})
    overlays = json.loads(overlay_path.read_text(encoding="utf-8"))
    details = {}
    for item in overlays:
        code = str(item["province_code"])
        rows = soil.loc[soil.province_code.eq(code)].nlargest(5, "pure_rai")
        details[code] = {
            "soil_year_be": item["soil_year_be"], "landuse_year_be": item["landuse_year_be"],
            "mapped_a403_rai": item["summary"]["pure"]["rai"],
            "top": [{"soil_code": r.soil_code, "soil_name": r.soil_name, "rai": r.pure_rai}
                    for r in rows.itertuples()],
        }
    selected["soil_overlay_status"] = selected.province_code.map(
        lambda code: "ซ้อนชุดดินกับ A403 แล้ว" if str(code) in details else "ยังไม่ซ้อนชุดดินกับพื้นที่ทุเรียน")
    return selected, details


def add_weather_profile(selected: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Attach a multi-year NASA POWER profile; never imply province-wide observations."""
    weather = pd.read_csv(NATIONAL / "weather_annual.csv", dtype={"province_code": str})
    start, end = int(weather.year_ce.min()), int(weather.year_ce.max())
    profile = weather.groupby("province_code", as_index=False).agg(
        climate_temperature_c=("temperature_c", "mean"),
        climate_humidity_pct=("humidity_pct", "mean"),
        climate_solar_mj_m2_day=("solar_mj_m2_day", "mean"),
        climate_rain_mm_year=("rain_mm_year", "mean"),
        climate_complete_years=("complete_weather_months", lambda s: int(s.eq(12).sum())),
    )
    return selected.merge(profile, on="province_code", how="left", validate="one_to_one"), f"{start}–{end}"


def build_region_season(year_ce: int) -> pd.DataFrame:
    """Compute regional harvest season from every province, not only selected provinces."""
    raw = pd.read_excel(OAE_MONTHLY, sheet_name="durian_monthly")
    raw["year_ce"] = pd.to_numeric(raw.year) - 543
    tonnes = raw.loc[raw.year_ce.eq(year_ce) & raw.item.eq("ปริมาณผลผลิตรายเดือน"),
                     ["province_name", "month", "data"]].copy()
    lookup = pd.read_csv(NATIONAL / "production_province_year.csv")
    lookup = lookup.loc[lookup.year_ce.eq(year_ce), ["province_name", "region"]].drop_duplicates()
    tonnes = tonnes.merge(lookup, on="province_name", validate="many_to_one")
    regional = tonnes.groupby(["region", "month"], as_index=False).data.sum()
    regional["region_total_tonnes"] = regional.groupby("region").data.transform("sum")
    regional["production_share_pct"] = 100 * regional.data / regional.region_total_tonnes
    regional = regional.rename(columns={"data": "monthly_production_tonnes"})
    regional["month_number"] = regional.month.map({m: i + 1 for i, m in enumerate(MONTH_ORDER)})
    return regional.sort_values(["region", "month_number"])


def build_map(selected: pd.DataFrame, season: pd.DataFrame, region_season: pd.DataFrame,
              soil_details: dict, year_ce: int, climate_period: str) -> Path:
    boundaries = json.loads((NATIONAL / "province_display.geojson").read_text(encoding="utf-8"))
    selected_codes = set(selected.province_code.astype(str))
    selected_features = [f for f in boundaries["features"] if str(f["properties"]["province_code"]) in selected_codes]
    assert len(selected_features) == len(selected)
    by_code = selected.set_index("province_code").to_dict("index")
    map_obj = folium.Map(location=[13.2, 101.0], zoom_start=6, tiles="OpenStreetMap", control_scale=True)
    values = selected.production_tonnes.to_numpy()
    cuts = np.quantile(values, [0, .25, .5, .75, 1])
    palette = ["#dce9e4", "#a9ccbf", "#68a98f", "#1f6f5f"]

    def style(feature):
        value = by_code[str(feature["properties"]["province_code"])]["production_tonnes"]
        index = min(3, max(0, int(np.searchsorted(cuts[1:], value, side="right"))))
        return {"fillColor": palette[index], "color": "#4b5551", "weight": 1,
                "fillOpacity": .85}

    geo = folium.GeoJson({"type": "FeatureCollection", "features": selected_features},
                         name="จังหวัดเป้าหมาย", style_function=style,
                         tooltip=folium.GeoJsonTooltip(fields=["province_name", "region"],
                                                       aliases=["จังหวัด", "ภาค"], sticky=False))
    geo.add_to(map_obj)

    feature_by_code = {str(f["properties"]["province_code"]): f for f in selected_features}
    soil_map_codes = {p.stem for p in (OUT / 'soil_layers').glob('*.geojson')}
    for row in selected.itertuples():
        feature = feature_by_code[str(row.province_code)]
        # Existing weather reference is reproducible and inside the province, not an orchard coordinate.
        lat, lon = float(row.weather_latitude), float(row.weather_longitude)
        monthly = season.loc[season.province_name.eq(row.province_name)]
        month_lines = "".join(
            f"<tr><td>{r.month}</td><td>{r.production_share_pct:.1f}%</td><td>{r.monthly_production_tonnes:,.0f}</td></tr>"
            for r in monthly.itertuples())
        if str(row.province_code) in soil_details:
            info = soil_details[str(row.province_code)]
            soil_lines = "".join(f"<li>{s['soil_code']} — {s['soil_name']} ({s['rai']:,.0f} ไร่)</li>" for s in info["top"])
            soil_html = (f"<b>หน่วยดินที่ซ้อน A403 มากสุด</b><ol>{soil_lines}</ol>"
                         f"<small>ดินปี {info['soil_year_be']} × การใช้ที่ดินปี {info['landuse_year_be']}; "
                         "ไม่ใช่อันดับความเหมาะสม และผลผลิตจังหวัดแจกลงชุดดินไม่ได้</small>")
            color = "#1f6f5f"
        else:
            soil_html = ("<b>ชุดดิน:</b> ยังไม่ประมวลผลการซ้อนกับพื้นที่ทุเรียน A403 จังหวัดนี้ "
                         "จึงไม่ใช้ชุดดินเด่นของทั้งจังหวัดมาแทน")
            color = "#9a681a"
        popup = f"""
        <div style='font-family:Tahoma,Arial;width:390px;line-height:1.45'>
        <h3 style='margin:0'>{row.province_name} · {row.region}</h3>
        {f'<p><a href="../five_province_history/HISTORY.html?province={row.province_code}">ดูย้อนหลังรายวัน / นับย้อนช่วงดอก / ผลผลิตแต่ละปี</a></p>' if str(row.province_code) in {'22','86','33','53','84'} else ''}
        {f'<button onclick="showSoil(\'{row.province_code}\')">ซูมดูขอบเขตชุดดิน</button>' if str(row.province_code) in soil_map_codes else ''}
        <p><b>ผลผลิต พ.ศ. {year_ce+543}:</b> {row.production_tonnes:,.0f} ตัน<br>
        อันดับประเทศ {row.national_rank} · อันดับภาค {row.regional_rank}<br>{row.selection_reason}</p>
        <p><b>ฤดูกาลจากสัดส่วนผลผลิตรายเดือน สศก.</b><br>
        เดือนสูงสุด: {row.peak_month} ({row.peak_share_pct:.1f}%)<br>
        เดือนที่มีสัดส่วนอย่างน้อย 10%: {row.months_at_least_10pct}</p>
        <table style='border-collapse:collapse;width:100%'><tr><th>เดือนที่รายงาน</th><th>%</th><th>ตัน</th></tr>{month_lines}</table>
        <p><b>โปรไฟล์อากาศ NASA POWER {climate_period}</b><br>
        อุณหภูมิ {row.climate_temperature_c:.1f} °C · ความชื้น {row.climate_humidity_pct:.1f}%<br>
        ฝน {row.climate_rain_mm_year:,.0f} มม./ปี · แสง {row.climate_solar_mj_m2_day:.1f} MJ/m²/วัน<br>
        <small>ค่าเฉลี่ยกริด ณ จุดอ้างอิง ไม่ใช่ค่าเฉลี่ยทั้งจังหวัดหรือสถานีสวน</small></p>
        <hr>{soil_html}
        <p><small>หมุดคือจุดอ้างอิงภายในจังหวัดสำหรับข้อมูลอากาศเดิม ไม่ใช่พิกัดสวนหรือจุดเก็บตัวอย่างดิน</small></p>
        </div>"""
        folium.CircleMarker([lat, lon], radius=8, color=color, fill=True, fill_color=color,
                            fill_opacity=.95, tooltip=f"{row.province_name}: {row.production_tonnes:,.0f} ตัน",
                            popup=folium.Popup(popup, max_width=450)).add_to(map_obj)

    title = f"""
    <div style='position:fixed;top:10px;left:50px;right:50px;z-index:9999;background:white;
    border:1px solid #bbb;padding:10px 14px;font-family:Tahoma,Arial'>
    <b>พื้นที่ทุเรียนเป้าหมาย พ.ศ. {year_ce+543}</b> — Top 3 ของแต่ละภาค ∪ Top 12 ประเทศ<br>
    <small>{len(selected)} จังหวัด · สีพื้นที่ = ผลผลิตรวมภายในกลุ่มที่คัด · หมุดเขียว = ซ้อนชุดดินกับ A403 แล้ว ·
    หมุดน้ำตาล = รอประมวลผลชุดดิน · คลิกหมุดดูฤดูกาลรายเดือนและหลักฐานดิน</small></div>"""
    map_obj.get_root().html.add_child(Element(title))
    peaks = region_season.loc[region_season.groupby("region").production_share_pct.idxmax()]
    peak_text = " · ".join(f"{r.region}: {r.month} ({r.production_share_pct:.1f}%)" for r in peaks.itertuples())
    region_box = f"""<div style='position:fixed;bottom:25px;left:50px;z-index:9999;background:white;
    border:1px solid #bbb;padding:8px 12px;font-family:Tahoma,Arial;max-width:760px'>
    <b>เดือนผลผลิตสูงสุดรายภาค พ.ศ. {year_ce+543}</b><br><small>{peak_text}<br>
    คำนวณจากทุกจังหวัดที่มีระเบียน สศก. ในภาค ไม่ใช่เฉพาะจังหวัดที่คัด</small></div>"""
    map_obj.get_root().html.add_child(Element(region_box))
    folium.LayerControl(collapsed=False).add_to(map_obj)
    choices = ''.join(f'<option value="{r.province_code}">{r.province_name}</option>'
                      for r in selected.itertuples() if str(r.province_code) in soil_map_codes)
    map_obj.get_root().html.add_child(Element('''
    <div style="position:fixed;top:110px;left:10px;z-index:10000;background:white;padding:10px;max-width:290px;font-family:Tahoma">
    <label for="soil-choice">ซูมดูชุดดิน</label>
    <select id="soil-choice" onchange="showSoil(this.value)"><option value="">เลือกจังหวัด</option>''' + choices + '''</select>
    <button onclick="hideSoil()">ปิดชั้นดิน</button>
    <div id="soil-status" style="font-size:12px">เลือกจังหวัด แล้วคลิกพื้นที่สีเพื่ออ่านชื่อชุดดิน</div></div>'''))
    script = r'''
    const soilCache = {}; let activeSoil = null; let soilRequest = 0;
    function hideSoil() {
      const soilMap = MAP_NAME;
      soilRequest++; if(activeSoil) soilMap.removeLayer(activeSoil); activeSoil=null;
      document.getElementById('soil-status').textContent='ปิดชั้นชุดดินแล้ว';
    }
    async function showSoil(code) {
      const soilMap = MAP_NAME;
      if(!code) return; const request = ++soilRequest;
      const status = document.getElementById('soil-status');
      status.textContent='กำลังโหลดขอบเขตชุดดิน…';
      soilMap.closePopup();
      try {
        if(!soilCache[code]) {
          const response = await fetch('soil_layers/'+code+'.geojson');
          if(!response.ok) throw new Error('HTTP '+response.status);
          const data = await response.json();
          const palette=['#d8b365','#5ab4ac','#b2abd2','#a6dba0','#f4a582','#92c5de'];
          soilCache[code] = L.geoJSON(data, {
            style: f => {let h=0; for(const c of f.properties.soil_code) h=(h+c.charCodeAt(0))%palette.length;
              return {color:'#555',weight:0.7,fillColor:palette[h],fillOpacity:0.55};},
            onEachFeature: (f,l) => {
              const p=f.properties; const box=document.createElement('div');
              for(const value of [p.province+' '+(p.district||''),p.soil_code+' — '+p.soil_name,
                'ความอุดมสมบูรณ์ดิน: '+(p.fertility||'ไม่ระบุ'), 'เนื้อดินบน: '+(p.topsoil_texture||'ไม่ระบุ'),
                'ปฏิกิริยาดินบน: '+(p.topsoil_ph||'ไม่ระบุ'),p.source,p.display_note,
                'ชั้นชุดดินทั้งจังหวัด; พื้นที่สีไม่ได้หมายถึงปลูกทุเรียนทุกแห่ง']) {
                const line=document.createElement('p');line.textContent=value;box.appendChild(line);
              }
              l.bindPopup(box); l.bindTooltip(document.createTextNode(p.soil_code+' — '+p.soil_name));
            }
          });
        }
        if(request!==soilRequest) return;
        if(activeSoil) soilMap.removeLayer(activeSoil);
        activeSoil=soilCache[code];activeSoil.addTo(soilMap);
        soilMap.fitBounds(activeSoil.getBounds(),{paddingTopLeft:[25,170],paddingBottomRight:[25,130]});
        document.getElementById('soil-choice').value=code;
        status.textContent='คลิกพื้นที่สีเพื่ออ่านชุดดิน · ข้อมูล LDD ปี 2561 · สีแยกหน่วยดิน ไม่ใช่ความเหมาะสม';
      } catch(e) {if(request===soilRequest) status.textContent='โหลดชั้นดินไม่สำเร็จ กรุณาเปิดผ่านเว็บ localhost และตรวจไฟล์ soil_layers';}
    }
    '''.replace('MAP_NAME', map_obj.get_name())
    map_obj.get_root().script.add_child(Element(script))
    path = OUT / "PRIORITY_DURIAN_MAP.html"
    map_obj.save(path)
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    selected, year = load_priority()
    selected, season = add_monthly_season(selected, year)
    selected, soil_details = add_soil_status(selected)
    selected, climate_period = add_weather_profile(selected)
    region_season = build_region_season(year)
    selected.to_csv(OUT / "priority_provinces_2025.csv", index=False, encoding="utf-8-sig")
    season.to_csv(OUT / "production_season_monthly_2025.csv", index=False, encoding="utf-8-sig")
    region_season.to_csv(OUT / "region_production_season_2025.csv", index=False, encoding="utf-8-sig")
    map_path = build_map(selected, season, region_season, soil_details, year, climate_period)
    summary = {
        "selection_year_be": year + 543, "selection_rule": "top3_each_region_union_national_top12",
        "selected_provinces": len(selected), "regions": int(selected.region.nunique()),
        "soil_overlay_complete": int(selected.soil_overlay_status.str.startswith("ซ้อน").sum()),
        "soil_overlay_pending": int(selected.soil_overlay_status.str.startswith("ยัง").sum()),
        "annual_production_tonnes_selected": float(selected.production_tonnes.sum()),
    }
    (OUT / "coverage.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(map_path)


if __name__ == "__main__":
    main()
