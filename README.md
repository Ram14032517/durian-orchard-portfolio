# Durian Orchard Data Platform

Academic portfolio: ESP32-based orchard ingestion, data quality checks, five-province soil/weather exploration, and baseline machine learning experiments.

**Private research/portfolio snapshot with fresh Git history.** No original Git history, deployed keys, private configuration, or private orchard sensor snapshots are included. The original orchard system has not been changed. Repository: [Ram14032517/durian-orchard-portfolio](https://github.com/Ram14032517/durian-orchard-portfolio).

## Run the map

Install Python 3.11+ and open a terminal in this folder:

```powershell
py -m venv .venv-portfolio
& .\.venv-portfolio\Scripts\python.exe -m pip install requests
& .\.venv-portfolio\Scripts\python.exe tools\serve_orchard_analysis.py
```

Open [the dashboard](http://127.0.0.1:8871/research_data/five_province_history/UNIFIED_MAP.html). Keep the terminal running; stop with Ctrl+C. Do not open the HTML template with file://.

Alternatively run SETUP_PORTFOLIO.ps1 once, then double-click 00_OPEN_REPORT.cmd. Setup creates a local environment and installs requests, numpy, and pandas; it does not contact orchard devices. The launcher reuses an existing report server on port 8871. Stop that server yourself first to inspect this copy specifically; no existing process is stopped automatically.

Setup also packages the regional training ZIP locally from the checked-in CSVs. Environments, point caches, exports, and ZIPs are excluded from Git. To build only the ZIP, run `python tools/package_training_bundle.py`; source CSVs and manifests remain unchanged.

## Explore

Select a month and a province (Chanthaburi, Chumphon, Sisaket, Uttaradit, Surat Thani), choose area A and optional B, switch between temperature/rain/humidity/solar/wind charts, review production evidence, and export source-labelled CSVs.

Leaflet and basemap tiles need internet. Historical weather queries use NASA POWER; bundled provincial series provides explicitly labelled fallback data. This is not a live connection to a private gateway.

## Python and Jupyter

```powershell
& .\.venv-portfolio\Scripts\python.exe tools\read_monthly_report.py --province 84 --year 2025 --month 7
& .\.venv-portfolio\Scripts\python.exe -m pip install -r tools\requirements-national-analysis.txt
```

Open [00_OPEN_ME.ipynb](00_OPEN_ME.ipynb) and select that environment as kernel. Saved regional outputs are included; private orchard readings are not. See [training data and experiments](research_data/five_province_history/training/README_TH.md).

Recorded monthly test MAE: province-month Ridge 14,685.26 tonnes; adding previous-month weather 15,283.82 tonnes. These are errors, not accuracy percentages or causal evidence.

- Production is provincial and includes reported varieties, not per-tree or Monthong-only yield.
- NASA weather is gridded, not orchard measurements.
- Soil polygons do not prove cultivation or individual-orchard fertility.
- Calendars are not observed stages of an individual tree.
- Tree-health diagnosis, flowering readiness, and irrigation prescriptions are not established.

## IoT source and tests

sender_1/, receiver_gateway/, google-apps-script/, and supabase/ show the ingestion architecture. Supply your own configuration using example headers before compiling firmware; regional analysis needs no device key.

```powershell
& .\.venv-portfolio\Scripts\python.exe -m unittest discover -s tests
node --test tests/test_weather_fallback.js tests/test_weather_export.js
```

Node.js is needed only for the JavaScript tests. Full rebuilds of soil layers need separately obtained source archives and extra geospatial dependencies; no private orchard export is bundled.

## Before publication

[Read the data-rights checklist](PUBLIC_SHARE_NOTES_TH.md). Private storage is not permission for public redistribution. Soil/boundary redistribution terms remain unverified; keep this repository private until reviewed or prepare a code-only public edition. No blanket repository license has been assigned. Never publish the original orchard repository history.
