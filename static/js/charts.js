/**
 * FleetSync - Chart.js Visualizations
 * High-performance enterprise charts with modern color palettes
 */

document.addEventListener('DOMContentLoaded', function () {
  initDashboardCharts();
  initReportCharts();
});

function initDashboardCharts() {
  // 1. Fleet Status Doughnut Chart
  const statusCanvas = document.getElementById('fleetStatusChart');
  if (statusCanvas) {
    const labels = JSON.parse(statusCanvas.getAttribute('data-labels') || '[]');
    const counts = JSON.parse(statusCanvas.getAttribute('data-counts') || '[]');

    const colorMap = {
      'Active': '#10b981',
      'In Service': '#3b82f6',
      'Maintenance Due': '#f59e0b',
      'Out of Service': '#ef4444'
    };

    const backgroundColors = labels.map(l => colorMap[l] || '#64748b');

    new Chart(statusCanvas, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: counts,
          backgroundColor: backgroundColors,
          borderWidth: 2,
          borderColor: '#ffffff',
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              padding: 15,
              font: { family: "'Plus Jakarta Sans', sans-serif", size: 12 }
            }
          },
          tooltip: {
            padding: 10,
            cornerRadius: 8
          }
        },
        cutout: '68%'
      }
    });
  }

  // 2. Service Category / Revenue Breakdown Chart
  const revenueCanvas = document.getElementById('serviceTypesChart');
  if (revenueCanvas) {
    const labels = JSON.parse(revenueCanvas.getAttribute('data-labels') || '[]');
    const counts = JSON.parse(revenueCanvas.getAttribute('data-counts') || '[]');

    new Chart(revenueCanvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Service Volume',
          data: counts,
          backgroundColor: 'rgba(79, 70, 229, 0.85)',
          borderRadius: 6,
          maxBarThickness: 32
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            padding: 10,
            cornerRadius: 8
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 } }
          },
          y: {
            beginAtZero: true,
            grid: { color: '#f1f5f9' },
            ticks: { stepSize: 1 }
          }
        }
      }
    });
  }
}

function initReportCharts() {
  const reportRevenueCanvas = document.getElementById('reportMonthlyRevenueChart');
  if (reportRevenueCanvas) {
    const months = JSON.parse(reportRevenueCanvas.getAttribute('data-months') || '[]');
    const revenues = JSON.parse(reportRevenueCanvas.getAttribute('data-revenue') || '[]');
    const parts = JSON.parse(reportRevenueCanvas.getAttribute('data-parts') || '[]');
    const labor = JSON.parse(reportRevenueCanvas.getAttribute('data-labor') || '[]');

    new Chart(reportRevenueCanvas, {
      type: 'line',
      data: {
        labels: months.reverse(),
        datasets: [
          {
            label: 'Total Revenue (₹)',
            data: revenues.reverse(),
            borderColor: '#4f46e5',
            backgroundColor: 'rgba(79, 70, 229, 0.08)',
            borderWidth: 3,
            fill: true,
            tension: 0.35,
            pointBackgroundColor: '#4f46e5',
            pointRadius: 5
          },
          {
            label: 'Labor Billed (₹)',
            data: labor.reverse(),
            borderColor: '#06b6d4',
            borderWidth: 2,
            borderDash: [5, 5],
            fill: false,
            tension: 0.35,
            pointRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top' },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ctx.dataset.label + ': ₹' + Number(ctx.raw).toLocaleString('en-IN');
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function (val) {
                return '₹' + val.toLocaleString('en-IN');
              }
            }
          }
        }
      }
    });
  }
}
