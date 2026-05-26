const chartPalette = [
  "#0f766e",
  "#2563eb",
  "#f59e0b",
  "#7c3aed",
  "#d97706",
  "#16a34a",
  "#dc2626",
  "#0891b2",
  "#475569",
];

const MAX_CHARTS = 6;

/* =========================
   JSON HELPERS
========================= */

function readJsonScript(selector, fallback) {
  const element = document.querySelector(selector);

  if (!element) {
    console.warn(`[SmartInsight] Missing JSON script: ${selector}`);
    return fallback;
  }

  try {
    return JSON.parse(element.textContent);
  } catch (error) {
    console.error(`[SmartInsight] Failed parsing JSON: ${selector}`, error);
    return fallback;
  }
}

function readDetectedColumns() {
  const columns = readJsonScript("#detected-columns", {});

  console.table({
    numeric: columns.numeric || [],
    categorical: columns.categorical || [],
    continuous: columns.continuous_numeric || [],
    encoded: columns.encoded_categorical || [],
    date: columns.date || [],
  });

  return columns;
}

/* =========================
   VALIDATION
========================= */

function hasDrawableData(chart) {
  if (!chart) return false;

  if (chart.type === "scatter") {
    return Array.isArray(chart.points) && chart.points.length > 0;
  }

  return (
    Array.isArray(chart.labels) &&
    Array.isArray(chart.values) &&
    chart.labels.length > 0 &&
    chart.values.length > 0
  );
}

function filterCharts(charts) {
  const usedTitles = new Set();

  return charts
    .filter(hasDrawableData)
    .filter((chart) => {
      if (usedTitles.has(chart.title)) {
        return false;
      }

      usedTitles.add(chart.title);
      return true;
    })
    .slice(0, MAX_CHARTS);
}

/* =========================
   CHART CONFIG
========================= */

function chartType(chart) {
  const mapping = {
    histogram: "bar",
    doughnut: "doughnut",
    donut: "doughnut",
    pie: "pie",
    line: "line",
    area: "line",
    scatter: "scatter",
    bar: "bar",
  };

  return mapping[chart.type] || "bar";
}

function formatNumber(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return value;
  }

  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: number % 1 === 0 ? 0 : 2,
  }).format(number);
}

function buildDataset(chart) {
  if (chart.type === "scatter") {
    return {
      datasets: [
        {
          label: chart.title,
          data: chart.points,
          backgroundColor: "rgba(15,118,110,0.75)",
          borderColor: "#0f766e",
          pointRadius: 5,
          pointHoverRadius: 7,
        },
      ],
    };
  }

  const isCircular =
    chart.type === "pie" ||
    chart.type === "doughnut" ||
    chart.type === "donut";

  const isLine =
    chart.type === "line" ||
    chart.type === "area";

  return {
    labels: chart.labels,

    datasets: [
      {
        label: chart.title,

        data: chart.values,

        backgroundColor: isCircular
          ? (chart.colors || chart.labels).map(
              (_, index) =>
                chartPalette[index % chartPalette.length]
            )
          : isLine
          ? "rgba(15,118,110,0.15)"
          : "#0f766e",

        borderColor: isCircular
          ? "#ffffff"
          : "#0f766e",

        borderWidth: isCircular ? 2 : 3,
        hoverBorderColor: isCircular ? "#ffffff" : "#0f766e",
        hoverBorderWidth: isCircular ? 4 : 3,
        spacing: isCircular ? 2 : 0,

        borderRadius:
          chart.type === "bar" ||
          chart.type === "histogram"
            ? 12
            : 0,

        fill: chart.type === "area",

        tension: 0.35,

        hoverOffset: isCircular ? 12 : 0,
      },
    ],
  };
}

function chartOptions(chart) {
  const isCircular =
    chart.type === "pie" ||
    chart.type === "doughnut" ||
    chart.type === "donut";

  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,

    animation: {
      duration: 1000,
      easing: "easeOutQuart",
    },

    plugins: {
      legend: {
        display: false,
        position: "bottom",

        labels: {
          usePointStyle: true,
          padding: 18,
          boxWidth: 10,
          boxHeight: 10,
          font: {
            size: 12,
            weight: "600",
          },
        },
      },

      tooltip: {
        enabled: true,

        callbacks: {
          label: function (context) {
            const value = context.parsed;

            if (isCircular) {
              const percentage =
                chart.percentages?.[context.dataIndex] ||
                0;

              const valueLabel =
                chart.value_label || "Value";

              return `${context.label}: ${formatNumber(value)} ${valueLabel} (${percentage}%)`;
            }

            return `${context.label}: ${formatNumber(value)}`;
          },
        },
      },
    },
  };

  /* =========================
     PIE / DOUGHNUT
  ========================= */

  if (isCircular) {
    return {
      ...baseOptions,

      layout: {
        padding: 8,
      },

      cutout:
        chart.type === "doughnut" ||
        chart.type === "donut"
          ? "58%"
          : "0%",

      plugins: {
        ...baseOptions.plugins,

        legend: {
          ...baseOptions.plugins.legend,
          position: "right",

          labels: {
            ...baseOptions.plugins.legend.labels,

            generateLabels: function (chartInstance) {
              const defaultLabels =
                Chart.defaults.plugins.legend.labels
                  .generateLabels(chartInstance);

              return defaultLabels.map((label) => {
                const percentage =
                  chart.percentages?.[label.index];

                if (percentage === undefined) {
                  return label;
                }

                return {
                  ...label,
                  text: `${label.text} (${percentage}%)`,
                };
              });
            },
          },
        },
      },
    };
  }

  /* =========================
     SCATTER
  ========================= */

  if (chart.type === "scatter") {
    return {
      ...baseOptions,

      scales: {
        x: {
          title: {
            display: true,
            text: chart.x_label || "X Axis",
          },

          grid: {
            color: "#eef2f6",
          },
        },

        y: {
          title: {
            display: true,
            text: chart.y_label || "Y Axis",
          },

          grid: {
            color: "#eef2f6",
          },
        },
      },
    };
  }

  /* =========================
     BAR / LINE
  ========================= */

  return {
    ...baseOptions,

    scales: {
      x: {
        grid: {
          display: false,
        },

        ticks: {
          color: "#667085",
        },
      },

      y: {
        beginAtZero: true,

        ticks: {
          color: "#667085",
        },

        grid: {
          color: "#eef2f6",
        },
      },
    },
  };
}

/* =========================
   CHART RENDERING
========================= */

function destroyExistingChart(canvas) {
  const existingChart = Chart.getChart(canvas);

  if (existingChart) {
    existingChart.destroy();
  }
}

function legendColor(chart, index) {
  return chart.colors?.[index] || chartPalette[index % chartPalette.length];
}

function circularLegendItems(chart) {
  return chart.labels.map((label, index) => {
    const value = chart.values?.[index];
    const percentage = chart.percentages?.[index];
    const detailParts = [];

    if (value !== undefined) {
      detailParts.push(formatNumber(value));
    }

    if (percentage !== undefined) {
      detailParts.push(`${percentage}%`);
    }

    if (chart.value_label) {
      detailParts.push(chart.value_label);
    }

    return {
      color: legendColor(chart, index),
      label,
      detail: detailParts.join(" · "),
    };
  });
}

function standardLegendItems(chart) {
  if (chart.type === "scatter") {
    return [
      {
        color: "#0f766e",
        label: "Data points",
        detail: `${chart.x_label || "X"} vs ${chart.y_label || "Y"}`,
      },
    ];
  }

  if (chart.type === "line" || chart.type === "area") {
    return [
      {
        color: "#0f766e",
        label: chart.type === "area" ? "Trend area" : "Trend line",
        detail: chart.title,
      },
    ];
  }

  if (chart.type === "histogram") {
    return [
      {
        color: "#0f766e",
        label: "Frequency bars",
        detail: chart.title,
      },
    ];
  }

  return [
    {
      color: "#0f766e",
      label: "Bars",
      detail: chart.title,
    },
  ];
}

function chartLegendItems(chart) {
  const isCircular =
    chart.type === "pie" ||
    chart.type === "doughnut" ||
    chart.type === "donut";

  return isCircular
    ? circularLegendItems(chart)
    : standardLegendItems(chart);
}

function removeExistingLegend(panel) {
  const existingLegend = panel.querySelector(".chart-color-info");

  if (existingLegend) {
    existingLegend.remove();
  }
}

function renderColorInfo(chart, canvas) {
  const panel = canvas.closest(".chart-panel");

  if (!panel) {
    return;
  }

  removeExistingLegend(panel);

  const items = chartLegendItems(chart);

  if (!items.length) {
    return;
  }

  const legend = document.createElement("div");
  legend.className = "chart-color-info";
  legend.setAttribute("aria-label", `${chart.title} color information`);

  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "chart-color-item";

    const swatch = document.createElement("span");
    swatch.className = "chart-color-swatch";
    swatch.style.backgroundColor = item.color;
    swatch.setAttribute("aria-hidden", "true");

    const text = document.createElement("span");
    text.className = "chart-color-text";

    const label = document.createElement("strong");
    label.textContent = item.label;

    text.appendChild(label);

    if (item.detail) {
      const detail = document.createElement("small");
      detail.textContent = item.detail;
      text.appendChild(detail);
    }

    row.appendChild(swatch);
    row.appendChild(text);
    legend.appendChild(row);
  });

  panel.appendChild(legend);
}

function renderChart(chart) {
  const canvas = document.querySelector(
    `canvas[data-chart-id="${chart.id}"]`
  );

  if (!canvas) {
    console.warn(
      `[SmartInsight] Canvas missing for chart: ${chart.id}`
    );
    return;
  }

  if (!window.Chart) {
    console.error("[SmartInsight] Chart.js not loaded.");
    return;
  }

  console.log(
    `[SmartInsight] Rendering ${chart.type}: ${chart.title}`
  );

  destroyExistingChart(canvas);

  new Chart(canvas, {
    type: chartType(chart),

    data: buildDataset(chart),

    options: chartOptions(chart),
  });

  renderColorInfo(chart, canvas);
}

/* =========================
   PAGE INIT
========================= */

document.addEventListener("DOMContentLoaded", () => {
  readDetectedColumns();

  const chartData = readJsonScript("#chart-data", []);

  console.log("[SmartInsight] Raw chart data:", chartData);

  if (!chartData.length) {
    console.warn("[SmartInsight] No chart data available.");
    return;
  }

  const filteredCharts = filterCharts(chartData);

  console.log(
    "[SmartInsight] Final charts:",
    filteredCharts
  );

  filteredCharts.forEach(renderChart);
});
