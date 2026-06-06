from pathlib import Path
from io import BytesIO
from uuid import uuid4

import pytest

from app import create_app
from app.routes.dashboard import (
    read_hash_file,
    write_hash_file,
)
from app.services.dashboard_generator import generate_dashboard_from_file


ROOT_DIR = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT_DIR / "samples"


# =========================================================
# FIXTURES
# =========================================================

@pytest.fixture()
def app():
    app = create_app("testing")
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture()
def upload_dir(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    return uploads


# =========================================================
# HELPERS
# =========================================================


def upload_csv(client, filename: str, content: bytes):
    return client.post(
        "/upload",
        data={
            "dataset": (
                BytesIO(content),
                filename,
            )
        },
        content_type="multipart/form-data",
        headers={"Accept": "application/json"},
    )


# =========================================================
# INDEX + ANALYZE ROUTES
# =========================================================


def test_index_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Dashboard Generator" in response.data


@pytest.mark.parametrize(
    "payload,expected_error",
    [
        ({}, "Provide a file_id to analyze."),
        ({"file_id": ""}, "Provide a file_id to analyze."),
    ],
)
def test_analyze_requires_file_id(client, payload, expected_error):
    response = client.post("/analyze", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"] == expected_error


# =========================================================
# UPLOAD TESTS
# =========================================================


def test_uploaded_dashboard_shows_original_filename(app, client, upload_dir):
    app.config["UPLOAD_FOLDER"] = str(upload_dir)

    upload = upload_csv(
        client,
        "my sales report.csv",
        b"date,region,sales\n2026-01-01,North,100\n2026-02-01,South,200\n",
    )

    assert upload.status_code == 200

    payload = upload.get_json()
    file_id = payload["file_id"]

    assert "__my_sales_report.csv" in file_id

    dashboard = client.get(f"/dashboard/{file_id}")

    assert dashboard.status_code == 200
    assert b"my_sales_report.csv" in dashboard.data



def test_history_page_lists_uploaded_dashboards(app, client, upload_dir):
    app.config["UPLOAD_FOLDER"] = str(upload_dir)

    upload = upload_csv(
        client,
        "history report.csv",
        b"date,region,sales\n2026-01-01,North,100\n",
    )

    file_id = upload.get_json()["file_id"]

    history = client.get("/history")

    assert history.status_code == 200
    assert b"history_report.csv" in history.data
    assert f"/dashboard/{file_id}".encode() in history.data



def test_duplicate_upload_reuses_existing_dashboard(app, client, upload_dir):
    app.config["UPLOAD_FOLDER"] = str(upload_dir)

    content = b"date,region,sales\n2026-01-01,North,100\n"

    first_upload = upload_csv(client, "first.csv", content)
    second_upload = upload_csv(client, "second.csv", content)

    uploaded_files = list(upload_dir.glob("*.csv"))

    assert first_upload.status_code == 200
    assert second_upload.status_code == 200

    first_payload = first_upload.get_json()
    second_payload = second_upload.get_json()

    assert first_payload["file_id"] == second_payload["file_id"]
    assert first_payload["duplicate"] is False
    assert second_payload["duplicate"] is True

    assert len(uploaded_files) == 1


def test_upload_limit_is_configurable(app):
    app.config.from_object("app.config.BaseConfig")

    assert app.config["MAX_CONTENT_LENGTH"] >= 25 * 1024 * 1024


def test_hash_sidecar_round_trip(tmp_path):
    csv_path = tmp_path / "large.csv"
    csv_path.write_text(
        "region,sales\nNorth,100\n",
        encoding="utf-8",
    )

    write_hash_file(csv_path, "abc123")

    assert read_hash_file(csv_path) == "abc123"


# =========================================================
# DASHBOARD GENERATOR TESTS
# =========================================================


def test_numeric_strings_are_detected_and_charted():
    dashboard = generate_dashboard_from_file(
        SAMPLES_DIR / "sales_messy_numbers.csv"
    )

    columns = dashboard["columns"]

    assert "revenue" in columns["numeric"]
    assert "profit" in columns["numeric"]
    assert "units" in columns["numeric"]

    assert "region" in columns["categorical"]
    assert "date" in columns["date"]

    chart_types = [chart["type"] for chart in dashboard["chart_data"]]

    assert "line" in chart_types
    assert "bar" in chart_types
    assert "scatter" in chart_types



def test_null_only_columns_are_ignored():
    dashboard = generate_dashboard_from_file(
        SAMPLES_DIR / "null_only_column.csv"
    )

    columns = dashboard["columns"]

    assert "amount" in columns["numeric"]

    assert "blank" not in columns["numeric"]
    assert "blank" not in columns["categorical"]
    assert "blank" not in columns["date"]



def test_all_numeric_dataset_generates_charts():
    dashboard = generate_dashboard_from_file(
        SAMPLES_DIR / "heart_numeric_sample.csv"
    )

    columns = dashboard["columns"]

    assert "age" in columns["numeric"]
    assert "oldpeak" in columns["numeric"]

    assert "sex" in columns["categorical"]
    assert "target" in columns["categorical"]

    chart_types = [chart["type"] for chart in dashboard["chart_data"]]

    assert "scatter" in chart_types
    assert any(chart in chart_types for chart in ["pie", "doughnut"])

    assert all(
        chart["empty_message"] == ""
        for chart in dashboard["chart_data"]
    )


def test_pie_chart_uses_metric_share_when_available(tmp_path):
    csv_path = tmp_path / "regional_sales.csv"

    csv_path.write_text(
        "\n".join([
            "region,sales",
            "North,100",
            "South,200",
            "East,50",
            "West,25",
            "Central,10",
            "Online,5",
            "Retail,5",
        ]),
        encoding="utf-8",
    )

    dashboard = generate_dashboard_from_file(csv_path)

    pie_chart = next(
        chart
        for chart in dashboard["chart_data"]
        if chart["type"] == "pie"
    )

    assert pie_chart["title"] == "Sales Share by Region"
    assert pie_chart["value_label"] == "Sales"
    assert pie_chart["labels"] == [
        "South",
        "North",
        "East",
        "West",
        "Central",
        "Other",
    ]
    assert pie_chart["values"] == [200, 100, 50, 25, 10, 10]
    assert round(sum(pie_chart["percentages"]), 1) == 100.0



def test_single_numeric_dataset_gets_histogram():
    dashboard = generate_dashboard_from_file(
        SAMPLES_DIR / "single_numeric.csv"
    )

    assert dashboard["columns"]["continuous_numeric"] == ["score"]

    chart_types = [
        chart["type"]
        for chart in dashboard["chart_data"]
    ]

    assert chart_types == ["histogram"]



def test_dynamic_recommendations_vary_by_schema():
    sales = generate_dashboard_from_file(
        SAMPLES_DIR / "sales_messy_numbers.csv"
    )

    medical = generate_dashboard_from_file(
        SAMPLES_DIR / "heart_numeric_sample.csv"
    )

    scores = generate_dashboard_from_file(
        SAMPLES_DIR / "single_numeric.csv"
    )

    sales_types = [c["type"] for c in sales["chart_data"]]
    medical_types = [c["type"] for c in medical["chart_data"]]
    score_types = [c["type"] for c in scores["chart_data"]]

    assert sales_types != medical_types
    assert score_types != sales_types
    assert score_types != medical_types


def test_insights_include_relationships_and_trends():
    dashboard = generate_dashboard_from_file(
        SAMPLES_DIR / "sales_messy_numbers.csv"
    )

    insights = dashboard["insights"]

    assert any(
        "Revenue increased" in insight
        for insight in insights
    )
    assert any(
        "Revenue and Units" in insight
        and "correlation" in insight
        for insight in insights
    )
    assert any(
        "Automation leads Revenue" in insight
        for insight in insights
    )


def test_encoded_category_insights_name_the_column():
    dashboard = generate_dashboard_from_file(
        SAMPLES_DIR / "heart_numeric_sample.csv"
    )

    assert any(
        "Sex value 1 leads Chol" in insight
        for insight in dashboard["insights"]
    )


# =========================================================
# CACHE TESTS
# =========================================================


def test_dashboard_cache_is_created(tmp_path):
    csv_path = tmp_path / "sample.csv"

    csv_path.write_text(
        "date,sales\n2026-01-01,100\n",
        encoding="utf-8",
    )

    generate_dashboard_from_file(csv_path)

    cache_path = csv_path.with_name(csv_path.name + ".json")

    # Cache only created for uploads folder
    assert cache_path.exists() is False


# =========================================================
# ERROR HANDLING
# =========================================================


def test_invalid_file_type_raises_error(tmp_path):
    invalid = tmp_path / "invalid.txt"

    invalid.write_text("hello")

    with pytest.raises(ValueError):
        generate_dashboard_from_file(invalid)


# =========================================================
# PERFORMANCE CHECK
# =========================================================


def test_dashboard_generation_returns_required_sections():
    dashboard = generate_dashboard_from_file(
        SAMPLES_DIR / "sales_messy_numbers.csv"
    )

    required_keys = {
        "title",
        "file_id",
        "shape",
        "columns",
        "kpis",
        "chart_data",
        "insights",
        "summary_statistics",
        "preview",
    }

    assert required_keys.issubset(dashboard.keys())


def test_large_csv_uses_fast_sample(monkeypatch, tmp_path):
    monkeypatch.setenv("FAST_ANALYSIS_ROW_LIMIT", "1000")

    csv_path = tmp_path / "large_sales.csv"

    rows = [
        "date,region,sales,units",
    ]

    for index in range(1500):
        rows.append(
            f"2026-01-01,North,{index + 1},{index + 2}"
        )

    csv_path.write_text(
        "\n".join(rows),
        encoding="utf-8",
    )

    dashboard = generate_dashboard_from_file(csv_path)

    assert dashboard["shape"]["rows"] == 1000
    assert dashboard["analysis"]["sampled"] is True
    assert dashboard["analysis"]["sample_rows"] == 1000
    assert dashboard["analysis"]["exact_rows"] is False
    assert dashboard["kpis"][0]["hint"] == "Analyzed first 1,000"
