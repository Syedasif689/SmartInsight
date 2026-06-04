from __future__ import annotations

import json
import logging
import os
import re
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
)

logger = logging.getLogger(__name__)

CHART_SCHEMA_VERSION = 5
# Optimized for fast processing of 20MB files
DEFAULT_FAST_ANALYSIS_ROW_LIMIT = 3_000  # Reduced from 10K for speed
DEFAULT_COLUMN_SCAN_ROW_LIMIT = 500  # Reduced from 1K for speed


# =========================================================
# MAIN DASHBOARD GENERATOR
# =========================================================

def generate_dashboard_from_file(file_path: str | Path) -> dict[str, Any]:

    path = Path(file_path)

    # -----------------------------
    # CACHE SYSTEM
    # -----------------------------

    in_uploads = any(parent.name == "uploads" for parent in path.resolve().parents)

    cache_path = (
        path.with_name(path.name + ".json")
        if in_uploads
        else None
    )

    if cache_path:
        try:
            if (
                cache_path.exists()
                and cache_path.stat().st_mtime >= path.stat().st_mtime
            ):
                with cache_path.open("r", encoding="utf-8") as file:
                    cached_dashboard = json.load(file)

                if (
                    cached_dashboard.get("chart_schema_version")
                    == CHART_SCHEMA_VERSION
                ):
                    return cached_dashboard

        except Exception as error:
            logger.warning("Cache read failed: %s", error)

    # -----------------------------
    # READ + CLEAN DATA
    # -----------------------------

    dataframe, dataset_info = _read_dataset(path)
    dataframe = _clean_dataframe(dataframe)

    columns = detect_columns(dataframe)

    numeric_columns = columns["numeric"]
    continuous_numeric_columns = columns["continuous_numeric"]
    categorical_columns = columns["categorical"]
    date_columns = columns["date"]

    # -----------------------------
    # BUILD DASHBOARD
    # -----------------------------

    dashboard = {
        "title": _display_name(path.name),
        "file_id": path.name,
        "chart_schema_version": CHART_SCHEMA_VERSION,

        "shape": {
            "rows": dataset_info.get("total_rows") or len(dataframe),
            "columns": len(dataframe.columns),
        },

        "analysis": {
            "sampled": dataset_info["sampled"],
            "sample_rows": len(dataframe),
            "row_limit": dataset_info["row_limit"],
            "exact_rows": dataset_info["exact_rows"],
        },

        "columns": columns,

        "kpis": _build_kpis(
            dataframe,
            numeric_columns,
            continuous_numeric_columns,
            categorical_columns,
            total_rows=dataset_info.get("total_rows"),
            sampled=dataset_info["sampled"],
        ),

        "chart_data": _build_charts(
            dataframe,
            numeric_columns,
            continuous_numeric_columns,
            categorical_columns,
            date_columns,
        ),

        "insights": _build_insights(
            dataframe,
            numeric_columns,
            continuous_numeric_columns,
            categorical_columns,
            date_columns,
        ),

        "summary_statistics": _build_summary_statistics(
            dataframe,
            numeric_columns,
        ),

        "preview": _build_preview(dataframe),
    }

    # -----------------------------
    # SAVE CACHE
    # -----------------------------

    if cache_path:
        try:
            with cache_path.open("w", encoding="utf-8") as file:
                json.dump(
                    dashboard,
                    file,
                    default=_json_default,
                )

        except Exception as error:
            logger.warning("Cache write failed: %s", error)

    return dashboard


# =========================================================
# COLUMN DETECTION
# =========================================================

def detect_columns(dataframe: pd.DataFrame) -> dict[str, list[str]]:
    """
    Optimized column detection with parallel-ready architecture.
    """
    numeric_columns = []
    continuous_numeric_columns = []
    categorical_columns = []
    encoded_categorical_columns = []
    date_columns = []

    for column in dataframe.columns:
        series = dataframe[column]
        non_null = series.dropna()

        if non_null.empty:
            continue

        # DATE - Use faster detection methods
        if is_datetime64_any_dtype(series):
            date_columns.append(column)
            continue
        
        # Quick date string detection (faster than full regex check)
        if _looks_like_date(series, column):
            date_columns.append(column)
            continue

        # NUMERIC
        if is_numeric_dtype(series) and not is_bool_dtype(series):
            numeric_columns.append(column)

            # Check if numeric column is actually categorical (limited unique values)
            if _looks_like_category(series):
                categorical_columns.append(column)
                encoded_categorical_columns.append(column)
            else:
                continuous_numeric_columns.append(column)
            continue

        # CATEGORICAL - all non-numeric, non-date columns
        categorical_columns.append(column)

    return {
        "numeric": numeric_columns,
        "continuous_numeric": continuous_numeric_columns,
        "categorical": categorical_columns,
        "encoded_categorical": encoded_categorical_columns,
        "date": date_columns,
    }


# =========================================================
# DATASET READER
# =========================================================

def _read_dataset(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Highly optimized dataset reader for fast processing of 20MB files.
    Uses minimal sampling and fast dtype detection.
    """
    suffix = path.suffix.lower()
    file_size_mb = path.stat().st_size / (1024 * 1024)
    row_limit = _fast_analysis_row_limit()
    
    # Aggressive optimization for files <= 20MB
    if file_size_mb <= 20:
        # For small files, reduce row limit significantly
        row_limit = 2000
    elif file_size_mb <= 50:
        row_limit = 2500
    elif file_size_mb <= 100:
        row_limit = 3000
    else:
        # Large files: very aggressive sampling
        row_limit = min(row_limit, 3000)

    if suffix == ".csv":
        # Ultra-fast CSV reading
        try:
            # Direct read with minimal dtype inference
            dataframe = pd.read_csv(
                path,
                nrows=row_limit,
                encoding='utf-8',
                engine='c',  # C engine is fastest
                dtype=str,  # Read as string first (faster)
                na_values=['NA', 'null', '', 'None', 'N/A', '#N/A'],
                skipinitialspace=True,
                keep_default_na=False,
            )
            
            # Quick post-read dtype conversion (vectorized, very fast)
            dataframe = _fast_dtype_inference(dataframe)
            
        except (UnicodeDecodeError, pd.errors.ParserError):
            # Fallback: Latin-1 encoding
            dataframe = pd.read_csv(
                path,
                nrows=row_limit,
                encoding='latin-1',
                engine='c',
                dtype=str,
                na_values=['NA', 'null', '', 'None', 'N/A', '#N/A'],
                skipinitialspace=True,
                keep_default_na=False,
            )
            dataframe = _fast_dtype_inference(dataframe)

        sampled = row_limit is not None and len(dataframe) >= row_limit
        total_rows = len(dataframe)

        return dataframe, {
            "total_rows": total_rows,
            "sampled": sampled,
            "row_limit": row_limit,
            "exact_rows": not sampled,
            "file_size_mb": file_size_mb,
        }

    if suffix in {".xls", ".xlsx"}:
        # Excel reading (already fast)
        dataframe = pd.read_excel(
            path,
            nrows=row_limit,
        )

        return dataframe, {
            "total_rows": len(dataframe),
            "sampled": row_limit is not None and len(dataframe) >= row_limit,
            "row_limit": row_limit,
            "exact_rows": False,
            "file_size_mb": file_size_mb,
        }

    raise ValueError(
        "Unsupported file type. Upload CSV or Excel."
    )


def _fast_dtype_inference(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Ultra-fast dtype conversion using vectorized operations.
    Only converts obvious numeric columns.
    """
    for col in dataframe.columns:
        series = dataframe[col]
        
        # Skip empty columns
        non_null = series.dropna()
        if non_null.empty or len(non_null) == 0:
            continue
        
        # Try numeric conversion on sample (not full column = faster)
        sample = non_null.head(100)
        try:
            numeric_sample = pd.to_numeric(sample, errors='coerce')
            # If 90%+ is numeric, convert full column
            if numeric_sample.notna().sum() / len(sample) > 0.9:
                dataframe[col] = pd.to_numeric(series, errors='coerce')
        except:
            pass
    
    return dataframe


def _fast_analysis_row_limit():

    try:
        return max(
            int(os.getenv(
                "FAST_ANALYSIS_ROW_LIMIT",
                DEFAULT_FAST_ANALYSIS_ROW_LIMIT,
            )),
            1_000,
        )

    except (TypeError, ValueError):
        return DEFAULT_FAST_ANALYSIS_ROW_LIMIT


def _column_scan_row_limit():

    try:
        return max(
            int(os.getenv(
                "COLUMN_SCAN_ROW_LIMIT",
                DEFAULT_COLUMN_SCAN_ROW_LIMIT,
            )),
            100,
        )

    except (TypeError, ValueError):
        return DEFAULT_COLUMN_SCAN_ROW_LIMIT


# =========================================================
# DATA CLEANING
# =========================================================

def _clean_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Minimal data cleaning for speed.
    Skips extensive coercion - relies on fast_dtype_inference.
    """
    dataframe = dataframe.copy()

    # Clean column names
    dataframe.columns = [str(col).strip() for col in dataframe.columns]

    # Drop completely empty rows
    dataframe = dataframe.dropna(how="all")

    return dataframe


def _coerce_numeric_columns(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Already handled in _fast_dtype_inference during read.
    This is kept for compatibility only.
    """
    return dataframe


def _clean_numeric_text(series: pd.Series) -> pd.Series:
    """Minimal numeric text cleaning for speed."""
    return (
        series.astype("string")
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace(r"[\$£€₹¥]", "", regex=True)
        .str.replace("%", "", regex=False)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
        .str.strip()
    )


# =========================================================
# CHART BUILDER
# =========================================================

def _build_charts(
    dataframe: pd.DataFrame,
    numeric_columns: list[str],
    continuous_numeric_columns: list[str],
    categorical_columns: list[str],
    date_columns: list[str],
) -> list[dict[str, Any]]:

    charts = []

    metric = _best_metric_column(
        dataframe,
        continuous_numeric_columns or numeric_columns,
    )

    category = _best_category_column(
        dataframe,
        categorical_columns,
    )

    # --------------------------------
    # LINE CHART
    # --------------------------------

    if date_columns and metric:

        line_chart = _line_chart(
            dataframe,
            date_columns[0],
            metric,
        )

        if line_chart:
            charts.append(line_chart)

    # --------------------------------
    # BAR CHART
    # --------------------------------

    if category and metric:

        bar_chart = _bar_chart(
            dataframe,
            category,
            metric,
        )

        if bar_chart:
            charts.append(bar_chart)

    # --------------------------------
    # PROFESSIONAL PIE CHART
    # --------------------------------

    if category:

        pie_chart = _pie_chart(
            dataframe,
            category,
            metric,
        )

        if pie_chart:
            charts.append(pie_chart)

    # --------------------------------
    # SCATTER CHART
    # --------------------------------

    scatter_chart = _scatter_chart(
        dataframe,
        continuous_numeric_columns or numeric_columns,
    )

    if scatter_chart:
        charts.append(scatter_chart)

    # --------------------------------
    # HISTOGRAM
    # --------------------------------

    if metric:

        histogram = _histogram_chart(
            dataframe,
            metric,
        )

        if histogram:
            charts.append(histogram)

    # --------------------------------
    # DONUT CHARTS
    # --------------------------------

    for column in categorical_columns[:2]:

        donut_chart = _donut_chart(
            dataframe,
            column,
        )

        if donut_chart:
            charts.append(donut_chart)

    # --------------------------------
    # FALLBACK
    # --------------------------------

    if not charts:

        charts.append({
            "id": "empty-chart",
            "type": "bar",
            "title": "No Charts Available",
            "labels": [],
            "values": [],
            "empty_message":
                "Upload better structured data.",
        })

    # --------------------------------
    # REMOVE DUPLICATES
    # --------------------------------

    unique = []
    seen = set()

    for chart in charts:

        if chart["id"] in seen:
            continue

        seen.add(chart["id"])
        unique.append(chart)

    return unique[:6]


# =========================================================
# LINE CHART
# =========================================================

def _line_chart(
    dataframe: pd.DataFrame,
    date_column: str,
    metric: str,
):

    try:

        temp = dataframe[[date_column, metric]].copy()

        temp[date_column] = pd.to_datetime(
            temp[date_column],
            errors="coerce",
        )

        temp[metric] = pd.to_numeric(
            temp[metric],
            errors="coerce",
        )

        grouped = (
            temp.dropna()
            .set_index(date_column)
            .sort_index()[metric]
            .resample("ME")
            .sum()
            .tail(12)
        )

        if grouped.empty:
            return None

        return {
            "id": "line-chart",
            "type": "line",
            "title": f"{_titleize(metric)} Trend",

            "labels": [
                date.strftime("%b %Y")
                for date in grouped.index
            ],

            "values": _series_values(grouped),

            "empty_message": "",
        }

    except Exception:
        return None


# =========================================================
# BAR CHART
# =========================================================

def _bar_chart(
    dataframe: pd.DataFrame,
    category: str,
    metric: str,
):

    try:

        grouped = (
            dataframe.groupby(category)[metric]
            .sum()
            .sort_values(ascending=False)
            .head(8)
        )

        if grouped.empty:
            return None

        return {
            "id": "bar-chart",
            "type": "bar",

            "title":
                f"{_titleize(metric)} by {_titleize(category)}",

            "labels": [
                str(label)
                for label in grouped.index
            ],

            "values": _series_values(grouped),

            "empty_message": "",
        }

    except Exception:
        return None


# =========================================================
# PIE CHART
# =========================================================

def _pie_chart(
    dataframe: pd.DataFrame,
    category: str,
    metric: str | None = None,
):

    try:
        use_metric = False

        if metric:
            temp = dataframe[[category, metric]].copy()

            temp[category] = (
                temp[category]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
                .replace("", "Unknown")
            )

            temp[metric] = pd.to_numeric(
                temp[metric],
                errors="coerce",
            )

            metric_values = (
                temp.dropna(subset=[metric])
                .groupby(category)[metric]
                .sum()
                .sort_values(ascending=False)
            )

            metric_values = metric_values[metric_values > 0]

            if not metric_values.empty:
                values = metric_values
                use_metric = True

        if not use_metric:
            values = (
                dataframe[category]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
                .replace("", "Unknown")
                .value_counts()
                .sort_values(ascending=False)
            )

        values = _compact_top_slices(values, limit=6)

        if values.empty:
            return None

        total = float(values.sum())

        if total <= 0:
            return None

        chart_values = _series_values(values)

        return {
            "id": f"pie-{_chart_id(category)}",
            "type": "pie",

            "title": (
                f"{_titleize(metric)} Share by {_titleize(category)}"
                if use_metric
                else f"{_titleize(category)} Distribution"
            ),

            "labels": [
                str(label)
                for label in values.index
            ],

            "values": chart_values,
            "percentages": _series_percentages(chart_values),
            "total": round(total, 2),
            "value_label": _titleize(metric) if use_metric else "Records",

            "empty_message": "",
        }

    except Exception:
        return None


# =========================================================
# DONUT CHART
# =========================================================

def _donut_chart(
    dataframe: pd.DataFrame,
    category: str,
):

    try:

        counts = (
            dataframe[category]
            .fillna("Unknown")
            .astype(str)
            .value_counts()
            .head(5)
        )

        if counts.empty:
            return None

        return {
            "id": f"donut-{category}",
            "type": "doughnut",

            "title":
                f"{_titleize(category)} Overview",

            "labels": [
                str(label)
                for label in counts.index
            ],

            "values": _series_values(counts),

            "empty_message": "",
        }

    except Exception:
        return None


# =========================================================
# SCATTER CHART
# =========================================================

def _scatter_chart(
    dataframe: pd.DataFrame,
    numeric_columns: list[str],
):

    pair = _best_correlation_pair(
        dataframe,
        numeric_columns,
    )

    if not pair:
        return None

    x_column, y_column, correlation = pair

    points = (
        dataframe[[x_column, y_column]]
        .dropna()
        .head(250)
        .to_dict(orient="records")
    )

    return {
        "id": "scatter-chart",
        "type": "scatter",

        "title":
            f"{_titleize(y_column)} vs {_titleize(x_column)}",

        "x_label": _titleize(x_column),
        "y_label": _titleize(y_column),

        "correlation":
            round(float(correlation), 2),

        "points": [
            {
                "x": row[x_column],
                "y": row[y_column],
            }
            for row in points
        ],

        "empty_message": "",
    }


# =========================================================
# HISTOGRAM
# =========================================================

def _histogram_chart(
    dataframe: pd.DataFrame,
    metric: str,
):

    values = pd.to_numeric(
        dataframe[metric],
        errors="coerce",
    ).dropna()

    if values.empty:
        return None

    bins = pd.cut(
        values,
        bins=min(8, max(3, values.nunique())),
    )

    counts = bins.value_counts().sort_index()

    return {
        "id": "histogram-chart",
        "type": "histogram",

        "title":
            f"{_titleize(metric)} Distribution",

        "labels": [
            str(label)
            for label in counts.index
        ],

        "values": _series_values(counts),

        "empty_message": "",
    }


# =========================================================
# HELPERS
# =========================================================

def _best_metric_column(
    dataframe: pd.DataFrame,
    numeric_columns: list[str],
):

    if not numeric_columns:
        return None

    scores = []

    for column in numeric_columns:

        values = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        ).dropna()

        if values.empty:
            continue

        scores.append((
            values.std(),
            values.sum(),
            column,
        ))

    if not scores:
        return None

    scores.sort(reverse=True)

    return scores[0][2]


def _best_category_column(
    dataframe: pd.DataFrame,
    categorical_columns: list[str],
):

    if not categorical_columns:
        return None

    best = None
    best_score = -1

    for column in categorical_columns:

        unique_count = dataframe[column].nunique()

        if 1 < unique_count <= 12:

            score = 12 - unique_count

            if score > best_score:
                best_score = score
                best = column

    return best


def _best_correlation_pair(
    dataframe: pd.DataFrame,
    numeric_columns: list[str],
):

    if len(numeric_columns) < 2:
        return None

    corr = (
        dataframe[numeric_columns]
        .apply(pd.to_numeric, errors="coerce")
        .corr()
    )

    best_pair = None
    best_value = 0

    for i, first in enumerate(numeric_columns):

        for second in numeric_columns[i + 1:]:

            value = corr.loc[first, second]

            if pd.notna(value):

                if abs(value) > abs(best_value):

                    best_value = value

                    best_pair = (
                        first,
                        second,
                        value,
                    )

    return best_pair


# =========================================================
# INSIGHTS
# =========================================================

def _build_insights(
    dataframe: pd.DataFrame,
    numeric_columns,
    continuous_numeric_columns,
    categorical_columns,
    date_columns,
):

    insights = []

    analysis_numeric_columns = (
        continuous_numeric_columns
        or numeric_columns
    )

    metric = _best_metric_column(
        dataframe,
        analysis_numeric_columns,
    )

    category = _best_category_column(
        dataframe,
        categorical_columns,
    )

    data_quality = _missing_data_insight(dataframe)

    if data_quality:
        insights.append(data_quality)

    trend_insight = _trend_insight(
        dataframe,
        date_columns,
        metric,
    )

    if trend_insight:
        insights.append(trend_insight)

    correlation_insight = _correlation_insight(
        dataframe,
        analysis_numeric_columns,
    )

    if correlation_insight:
        insights.append(correlation_insight)

    if category and metric:

        category_insight = _category_driver_insight(
            dataframe,
            category,
            metric,
        )

        if category_insight:
            insights.append(category_insight)

    outlier_insight = _outlier_insight(
        dataframe,
        metric,
    )

    if outlier_insight:
        insights.append(outlier_insight)

    if not insights:

        insights.append(
            "Upload structured data for better AI insights."
        )

    return _dedupe_insights(insights)[:6]


def _missing_data_insight(dataframe: pd.DataFrame):

    total_cells = dataframe.shape[0] * dataframe.shape[1]

    if total_cells == 0:
        return None

    missing_cells = int(dataframe.isna().sum().sum())
    missing_rate = missing_cells / total_cells

    if missing_rate < 0.05:
        return None

    missing_by_column = (
        dataframe.isna()
        .mean()
        .sort_values(ascending=False)
    )

    top_column = missing_by_column.index[0]
    top_rate = missing_by_column.iloc[0] * 100

    return (
        f"Data quality watch: {_titleize(top_column)} has "
        f"{top_rate:.1f}% missing values, which may affect "
        "chart accuracy and relationships."
    )


def _trend_insight(
    dataframe: pd.DataFrame,
    date_columns: list[str],
    metric: str | None,
):

    if not date_columns or not metric:
        return None

    try:
        temp = dataframe[[date_columns[0], metric]].copy()

        temp[date_columns[0]] = pd.to_datetime(
            temp[date_columns[0]],
            errors="coerce",
        )

        temp[metric] = pd.to_numeric(
            temp[metric],
            errors="coerce",
        )

        grouped = (
            temp.dropna()
            .set_index(date_columns[0])
            .sort_index()[metric]
            .resample("ME")
            .sum()
            .tail(12)
        )

        if len(grouped) < 2:
            return None

        first = float(grouped.iloc[0])
        last = float(grouped.iloc[-1])

        if first == 0:
            return None

        change = ((last - first) / abs(first)) * 100

        if abs(change) < 5:
            return (
                f"{_titleize(metric)} stayed relatively stable "
                f"over time, changing {change:.1f}% across the "
                "available date range."
            )

        direction = "increased" if change > 0 else "decreased"

        return (
            f"{_titleize(metric)} {direction} by "
            f"{abs(change):.1f}% from the first to latest "
            "available period."
        )

    except Exception:
        return None


def _correlation_insight(
    dataframe: pd.DataFrame,
    numeric_columns: list[str],
):

    pair = _best_correlation_pair(
        dataframe,
        numeric_columns,
    )

    if not pair:
        return None

    first, second, correlation = pair
    strength = abs(float(correlation))

    if strength < 0.5:
        return None

    direction = "positive" if correlation > 0 else "negative"

    if strength >= 0.8:
        label = "very strong"
    elif strength >= 0.65:
        label = "strong"
    else:
        label = "moderate"

    return (
        f"{_titleize(first)} and {_titleize(second)} have a "
        f"{label} {direction} relationship "
        f"(correlation {correlation:.2f})."
    )


def _category_driver_insight(
    dataframe: pd.DataFrame,
    category: str,
    metric: str,
):

    try:
        temp = dataframe[[category, metric]].copy()

        temp[category] = (
            temp[category]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
            .replace("", "Unknown")
        )

        temp[metric] = pd.to_numeric(
            temp[metric],
            errors="coerce",
        )

        grouped = (
            temp.dropna(subset=[metric])
            .groupby(category)[metric]
            .agg(["sum", "mean", "count"])
            .sort_values("sum", ascending=False)
        )

        if grouped.empty:
            return None

        total = float(grouped["sum"].sum())

        if total == 0:
            return None

        top_label = _format_category_label(
            category,
            grouped.index[0],
        )
        top_sum = float(grouped.iloc[0]["sum"])
        share = (top_sum / total) * 100

        if len(grouped) > 1:
            second_sum = float(grouped.iloc[1]["sum"])
            gap = top_sum - second_sum

            return (
                f"{top_label} leads {_titleize(metric)} by "
                f"{_format_number(gap)} over the next category "
                f"and contributes {share:.1f}% of the total."
            )

        return (
            f"{top_label} contributes {share:.1f}% of total "
            f"{_titleize(metric)}."
        )

    except Exception:
        return None


def _outlier_insight(
    dataframe: pd.DataFrame,
    metric: str | None,
):

    if not metric:
        return None

    values = pd.to_numeric(
        dataframe[metric],
        errors="coerce",
    ).dropna()

    if len(values) < 8:
        return None

    quartile_1 = values.quantile(0.25)
    quartile_3 = values.quantile(0.75)
    iqr = quartile_3 - quartile_1

    if iqr == 0:
        return None

    lower_bound = quartile_1 - (1.5 * iqr)
    upper_bound = quartile_3 + (1.5 * iqr)

    outliers = values[
        (values < lower_bound)
        | (values > upper_bound)
    ]

    if outliers.empty:
        return None

    return (
        f"{_titleize(metric)} contains {len(outliers)} possible "
        f"outlier value{'s' if len(outliers) != 1 else ''}; "
        f"highest observed value is {_format_number(values.max())}."
    )


def _dedupe_insights(insights: list[str]):

    deduped = []
    seen = set()

    for insight in insights:
        normalized = insight.strip().lower()

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        deduped.append(insight)

    return deduped


def _format_category_label(
    category: str,
    value: Any,
):

    text = str(value)

    if text.replace(".", "", 1).isdigit():
        return f"{_titleize(category)} value {text}"

    return text


# =========================================================
# SUMMARY TABLE
# =========================================================

def _build_summary_statistics(
    dataframe: pd.DataFrame,
    numeric_columns: list[str],
):

    if not numeric_columns:
        return []

    summary = (
        dataframe[numeric_columns]
        .describe()
        .round(2)
        .transpose()
        .reset_index()
    )

    summary.rename(
        columns={"index": "column"},
        inplace=True,
    )

    return summary.to_dict(orient="records")


# =========================================================
# PREVIEW
# =========================================================

def _build_preview(dataframe: pd.DataFrame):

    preview = dataframe.head(10)

    return {
        "columns": [
            str(column)
            for column in preview.columns
        ],

        "rows": preview.to_dict(orient="records"),
    }


# =========================================================
# HELPERS
# =========================================================

def _looks_like_date(series: pd.Series, column_name: str | None = None):

    if is_numeric_dtype(series):
        return False

    values = series.dropna().head(_column_scan_row_limit())

    if values.empty:
        return False

    if not _date_parse_is_worth_trying(values, column_name):
        return False

    with warnings.catch_warnings():

        warnings.simplefilter(
            "ignore",
            UserWarning,
        )

        parsed = pd.to_datetime(
            values,
            errors="coerce",
        )

    return parsed.notna().mean() >= 0.8


def _date_parse_is_worth_trying(
    values: pd.Series,
    column_name: str | None = None,
):

    name = str(column_name or "").lower()

    if re.search(r"\b(date|time|year|month|day|created|updated)\b", name):
        return True

    text_values = values.astype("string").str.strip()

    if text_values.str.len().median() > 32:
        return False

    date_like = text_values.str.contains(
        r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}",
        regex=True,
        na=False,
    )

    return date_like.mean() >= 0.5


def _looks_like_category(series: pd.Series):

    values = series.dropna().head(_column_scan_row_limit())

    if values.empty:
        return False

    unique = values.nunique()

    unique_ratio = unique / max(len(values), 1)

    return 1 < unique <= 20 and unique_ratio <= 0.6


def _series_values(series: pd.Series):

    return [
        round(float(value), 2)
        for value in series.fillna(0).tolist()
    ]


def _compact_top_slices(
    series: pd.Series,
    limit: int = 6,
):

    if len(series) <= limit:
        return series

    top_count = max(limit - 1, 1)

    top_values = series.head(top_count)
    other_value = series.iloc[top_count:].sum()

    if other_value <= 0:
        return top_values

    return pd.concat([
        top_values,
        pd.Series({"Other": other_value}),
    ])


def _series_percentages(values: list[float]):

    total = sum(values)

    if total <= 0:
        return [0 for _ in values]

    return [
        round((value / total) * 100, 1)
        for value in values
    ]


def _chart_id(text: str):

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        str(text).lower(),
    ).strip("-")

    return slug or "chart"


def _json_default(value):

    try:
        return value.tolist()

    except Exception:

        try:
            return float(value)

        except Exception:
            return str(value)


def _display_name(file_name: str):

    if "__" in file_name:
        return file_name.split("__", 1)[1]

    return file_name


def _titleize(text: str):

    return (
        str(text)
        .replace("_", " ")
        .replace("-", " ")
        .title()
    )


def _format_number(value: Any):

    try:
        number = float(value)

    except Exception:
        return str(value)

    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"

    if abs(number) >= 1_000:
        return f"{number / 1_000:.1f}K"

    if number.is_integer():
        return f"{int(number):,}"

    return f"{number:,.2f}"


def _build_kpis(
    dataframe,
    numeric_columns,
    continuous_numeric_columns,
    categorical_columns,
    total_rows=None,
    sampled=False,
):

    missing = int(dataframe.isna().sum().sum())
    row_count = total_rows or len(dataframe)

    kpis = [
        {
            "label": "Rows",
            "value": f"{row_count:,}",
            "hint": (
                f"Analyzed first {len(dataframe):,}"
                if sampled
                else "Total records"
            ),
        },

        {
            "label": "Columns",
            "value": f"{len(dataframe.columns):,}",
            "hint": "Total columns",
        },

        {
            "label": "Missing",
            "value": f"{missing:,}",
            "hint": (
                "Missing cells in sample"
                if sampled
                else "Missing cells"
            ),
        },
    ]

    metric = _best_metric_column(
        dataframe,
        continuous_numeric_columns or numeric_columns,
    )

    if metric:

        kpis.append({
            "label": f"Average {_titleize(metric)}",

            "value": _format_number(
                dataframe[metric].mean()
            ),

            "hint": "Main metric average",
        })

    return kpis
