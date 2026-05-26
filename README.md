# SmartInsight

SmartInsight is a Flask dashboard generator. Upload a CSV or Excel dataset and the app detects numeric, categorical, and date columns, then builds KPI cards, charts, summary statistics, and automated insights.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app app run --debug
```

Open http://127.0.0.1:5000 in your browser.

Large uploads default to 200 MB. Set `MAX_UPLOAD_MB` in `.env`
to raise or lower that limit.

For fast dashboards on large files, SmartInsight analyzes the first
10,000 rows by default. Set
`FAST_ANALYSIS_ROW_LIMIT` in `.env` to trade speed for deeper analysis.
Column type detection scans the first 1,000 non-empty values per column.
Duplicate scanning is skipped above `DUPLICATE_CHECK_MAX_MB` to avoid
re-reading large uploads before dashboard generation.

## Project Layout

```text
app/
  __init__.py          Flask application factory
  config.py            App configuration classes
  routes/              Route blueprints
  services/            Dashboard generation logic
  static/              CSS, JavaScript, and assets
  templates/           Jinja templates
uploads/               Uploaded datasets
tests/                 Pytest test suite
run.py                 Local entry point
```

## Routes

- `POST /upload` saves a CSV or Excel file and redirects to its dashboard.
- `POST /analyze` accepts a `file_id` and returns dashboard JSON.
- `GET /dashboard/<file_id>` renders a generated dashboard with Jinja and Chart.js.
