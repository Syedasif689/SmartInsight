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

You can deploy SmartInsight on:

- Render
- Railway
- Vercel
- PythonAnywhere

---

## Author

   Syed Asif

