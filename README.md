# SmartInsight

SmartInsight is a modern dashboard generator built with Flask and Chart.js.  
Upload CSV or Excel datasets to instantly generate interactive dashboards, charts, KPI cards, and insights.

---

## Features

- Automatic dataset analysis
- Smart chart generation
- KPI metrics dashboard
- Correlation heatmaps
- Responsive mobile-friendly UI
- Upload history tracking
- CSV and Excel support
- Fast large-file processing

---

## Tech Stack

- Python
- Flask
- Pandas
- Chart.js
- HTML/CSS/JavaScript

---

## Installation

### Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/smartinsight-dashboard.git
cd smartinsight-dashboard
```

### Create Virtual Environment

#### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install Requirements

```bash
pip install -r requirements.txt
```

### Run Project

```bash
flask --app app run --debug
```

Open:

```text
http://127.0.0.1:5000
```

---

## Project Structure

```text
SmartInsight/
│
├── app/
├── tests/
├── uploads/
├── samples/
├── static/
├── templates/
├── requirements.txt
├── run.py
└── README.md
```

---

## Routes

| Method | Route | Description |
|--------|------|-------------|
| POST | `/upload` | Upload dataset |
| POST | `/analyze` | Generate dashboard JSON |
| GET | `/dashboard/<file_id>` | View dashboard |
| GET | `/history` | View upload history |

---

## Testing

Run tests using:

```bash
pytest
```

---

## Deployment

SmartInsight can be deployed on Render, Railway, Vercel, or PythonAnywhere.

### Render

1. Add `runtime.txt` with:

```text
python-3.13.12
```

2. Add `render.yaml` to configure the web service:

```yaml
services:
  - type: web
    name: smartinsight
    env: python
    plan: free
    branch: main
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --bind 0.0.0.0:$PORT run:app
    envVars:
      - key: SECRET_KEY
        sync: false
      - key: MYSQL_HOST
        sync: false
      - key: MYSQL_USER
        sync: false
      - key: MYSQL_PASSWORD
        sync: false
      - key: MYSQL_DB
        sync: false
      - key: GOOGLE_CLIENT_ID
        sync: false
      - key: GOOGLE_CLIENT_SECRET
        sync: false
      - key: MAIL_SERVER
      - key: MAIL_PORT
      - key: MAIL_USE_TLS
      - key: MAIL_USERNAME
        sync: false
      - key: MAIL_PASSWORD
        sync: false
      - key: MAIL_DEFAULT_SENDER
      - key: MAX_UPLOAD_MB
      - key: FAST_ANALYSIS_ROW_LIMIT
      - key: COLUMN_SCAN_ROW_LIMIT
      - key: DUPLICATE_CHECK_MAX_MB
      - key: UPLOAD_FOLDER
```

3. Set the required Render environment variables in the Render dashboard.

> Note: Render filesystem is ephemeral, so uploaded files are not permanent in production.

---

## Author

   Syed Asif

