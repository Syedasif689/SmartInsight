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
            color: "#1a2a1a",
          },
        },

        y: {
          title: {
            display: true,
            text: chart.y_label || "Y Axis",
          },

          grid: {
            color: "#1a2a1a",
          },
        },
      },
    };
  }

  return {
    ...baseOptions,

    scales: {
      x: {
        grid: {
          display: false,
        },

        ticks: {
          color: "#a0a0a0",
        },
      },

      y: {
        beginAtZero: true,

        ticks: {
          color: "#a0a0a0",
        },

        grid: {
          color: "#1a2a1a",
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
   MODERN UPLOAD HANDLER
========================= */

class ModernUploader {
  constructor() {
    this.dropzone = document.getElementById('dropzone');
    this.fileInput = document.getElementById('fileInput');
    this.uploadBtn = document.getElementById('uploadBtn');
    this.filePreview = document.querySelector('.file-preview');
    this.uploadProgress = document.querySelector('.upload-progress-modern');
    this.fileName = document.querySelector('.file-name');
    this.fileSize = document.querySelector('.file-size');
    this.progressFill = document.querySelector('.progress-fill');
    this.progressText = document.querySelector('.progress-text');
    
    this.selectedFile = null;
    this.maxUploadMB = 200;
    this.init();
  }
  
  init() {
    // Click to browse
    if (this.dropzone) {
      this.dropzone.addEventListener('click', (e) => {
        // Don't trigger if clicking on remove button
        if (e.target.classList.contains('remove-file')) return;
        this.fileInput.click();
      });
    }
    
    // Browse link click
    const browseLink = document.querySelector('.browse-link');
    if (browseLink) {
      browseLink.addEventListener('click', (e) => {
        e.stopPropagation();
        this.fileInput.click();
      });
    }
    
    // File selection
    if (this.fileInput) {
      this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e.target.files[0]));
    }
    
    // Drag & drop events
    if (this.dropzone) {
      this.dropzone.addEventListener('dragover', (e) => this.handleDragOver(e));
      this.dropzone.addEventListener('dragleave', () => this.handleDragLeave());
      this.dropzone.addEventListener('drop', (e) => this.handleDrop(e));
    }
    
    // Remove file
    const removeBtn = document.querySelector('.remove-file');
    if (removeBtn) {
      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.removeFile();
      });
    }
    
    // Upload button
    if (this.uploadBtn) {
      this.uploadBtn.addEventListener('click', () => this.uploadFile());
    }
  }
  
  handleFileSelect(file) {
    if (!file) return;
    
    console.log('File selected:', file.name);
    
    // Validate file type
    const validExtensions = ['csv', 'xlsx', 'xls'];
    const fileExt = file.name.split('.').pop().toLowerCase();
    
    if (!validExtensions.includes(fileExt)) {
      this.showError('Please upload CSV or Excel files only');
      return;
    }
    
    // Validate size (200MB max)
    if (file.size > this.maxUploadMB * 1024 * 1024) {
      this.showError(`File size must be less than ${this.maxUploadMB}MB`);
      return;
    }
    
    this.selectedFile = file;
    this.showPreview(file);
    if (this.uploadBtn) this.uploadBtn.disabled = false;
  }
  
  handleDragOver(e) {
    e.preventDefault();
    if (this.dropzone) this.dropzone.classList.add('drag-over');
  }
  
  handleDragLeave() {
    if (this.dropzone) this.dropzone.classList.remove('drag-over');
  }
  
  handleDrop(e) {
    e.preventDefault();
    if (this.dropzone) this.dropzone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    this.handleFileSelect(file);
  }
  
  showPreview(file) {
    const uploadIcon = document.querySelector('.upload-icon');
    const uploadText = document.querySelector('.upload-text');
    
    if (uploadIcon) uploadIcon.style.display = 'none';
    if (uploadText) uploadText.style.display = 'none';
    if (this.filePreview) this.filePreview.style.display = 'block';
    
    if (this.fileName) this.fileName.textContent = file.name;
    if (this.fileSize) this.fileSize.textContent = this.formatFileSize(file.size);
  }
  
  removeFile() {
    this.selectedFile = null;
    if (this.fileInput) this.fileInput.value = '';
    if (this.uploadBtn) this.uploadBtn.disabled = true;
    
    if (this.filePreview) this.filePreview.style.display = 'none';
    
    const uploadIcon = document.querySelector('.upload-icon');
    const uploadText = document.querySelector('.upload-text');
    
    if (uploadIcon) uploadIcon.style.display = 'block';
    if (uploadText) uploadText.style.display = 'block';
    if (this.uploadProgress) this.uploadProgress.style.display = 'none';
  }
  
  async uploadFile() {
    if (!this.selectedFile) return;
    
    console.log('Uploading file:', this.selectedFile.name);
    
    if (this.uploadProgress) this.uploadProgress.style.display = 'block';
    if (this.uploadBtn) {
      this.uploadBtn.disabled = true;
      this.uploadBtn.innerHTML = `<span>Uploading...</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>`;
    }
    
    const formData = new FormData();
    formData.append('dataset', this.selectedFile);
    
    try {
      // Simulate progress
      await this.simulateUpload();
      
      // Send to server - use the correct endpoint with 5 minute timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000); // 5 minutes
      
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData,
        headers: {
          Accept: 'application/json',
        },
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      const result = await response.json().catch(() => ({}));

      if (response.ok) {
        this.uploadSuccess();
        const dashboardUrl = result.dashboard_url || window.location.href;
        window.location.href = dashboardUrl;
        return;
      }

      this.uploadError(result.error || 'Upload failed');
      
    } catch (error) {
      console.error('Upload error:', error);
      if (error.name === 'AbortError') {
        this.uploadError('Upload took too long (timeout). Please try a smaller file.');
      } else {
        this.uploadError('Failed to upload file. Please try again.');
      }
    }
  }
  
  simulateUpload() {
    return new Promise((resolve) => {
      let progress = 0;
      const interval = setInterval(() => {
        progress += 10;
        this.updateProgress(progress);
        if (progress >= 100) {
          clearInterval(interval);
          resolve();
        }
      }, 150);
    });
  }
  
  updateProgress(percent) {
    if (this.progressFill) this.progressFill.style.width = `${percent}%`;
    if (this.progressText) {
      if (percent < 100) {
        this.progressText.textContent = `Uploading... ${percent}%`;
      } else {
        this.progressText.textContent = 'Processing data...';
      }
    }
  }
  
  uploadSuccess() {
    if (this.progressText) this.progressText.textContent = '✓ Upload Complete! Loading dashboard...';
    if (this.progressFill) this.progressFill.style.width = '100%';
    if (this.dropzone) this.dropzone.classList.add('upload-success-animation');
  }
  
  uploadError(message) {
    if (this.progressText) this.progressText.textContent = `✗ Error: ${message}`;
    if (this.progressFill) this.progressFill.style.background = '#ff4444';
    this.showError(message);
    
    setTimeout(() => {
      this.resetUploader();
    }, 3000);
  }
  
  resetUploader() {
    if (this.uploadProgress) this.uploadProgress.style.display = 'none';
    if (this.uploadBtn) {
      this.uploadBtn.disabled = false;
      this.uploadBtn.innerHTML = `<span>Analyze Dataset</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12H19M12 5L19 12L12 19"/></svg>`;
    }
    this.removeFile();
    if (this.progressFill) {
      this.progressFill.style.background = '';
      this.progressFill.style.width = '0%';
    }
  }
  
  showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'toast-error';
    errorDiv.textContent = message;
    document.body.appendChild(errorDiv);
    setTimeout(() => errorDiv.remove(), 3000);
  }
  
  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
}

/* =========================
   SMOOTH SCROLLING ENHANCEMENTS
========================= */

function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
          inline: 'nearest'
        });
      }
    });
  });
}

window.scrollToTop = function() {
  window.scrollTo({
    top: 0,
    behavior: 'smooth'
  });
};

function initScrollDetection() {
  window.addEventListener('scroll', () => {
    const scrollPosition = window.scrollY;
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
      if (scrollPosition > 100) {
        sidebar.classList.add('scrolled');
      } else {
        sidebar.classList.remove('scrolled');
      }
    }
  });
}

/* =========================
   PAGE INIT
========================= */

document.addEventListener("DOMContentLoaded", () => {
  // Read detected columns
  readDetectedColumns();

  // Initialize chart data
  const chartData = readJsonScript("#chart-data", []);

  console.log("[SmartInsight] Raw chart data:", chartData);

  if (!chartData.length) {
    console.warn("[SmartInsight] No chart data available.");
  } else {
    const filteredCharts = filterCharts(chartData);
    console.log("[SmartInsight] Final charts:", filteredCharts);
    filteredCharts.forEach(renderChart);
  }

  // Initialize smooth scrolling features
  initSmoothScroll();
  initScrollDetection();

  // Initialize modern uploader
  new ModernUploader();

  console.log("[SmartInsight] All features initialized");
});