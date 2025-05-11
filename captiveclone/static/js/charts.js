/**
 * CaptiveClone Charts Module
 * Provides visualization capabilities for the dashboard using Chart.js
 */

// Global chart instances to allow updating
let credentialTimelineChart = null;
let clientConnectionChart = null;
let attackSuccessChart = null;

/**
 * Initialize all charts on the dashboard
 */
function initCharts() {
  initCredentialTimeline();
  initClientConnectionChart();
  initAttackSuccessChart();
  
  // Set up refresh intervals
  setInterval(updateCredentialTimeline, 30000); // 30s
  setInterval(updateClientConnections, 15000);  // 15s
  setInterval(updateAttackSuccess, 60000);      // 60s
}

/**
 * Initialize the credential capture timeline chart
 */
function initCredentialTimeline() {
  const ctx = document.getElementById('credentialTimelineChart');
  if (!ctx) return;
  
  fetch('/api/stats/credentials/timeline')
    .then(response => response.json())
    .then(data => {
      credentialTimelineChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: data.labels,
          datasets: [{
            label: 'Captured Credentials',
            data: data.values,
            borderColor: 'rgba(75, 192, 192, 1)',
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
            borderWidth: 2,
            tension: 0.3,
            fill: true
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: {
              position: 'top',
            },
            title: {
              display: true,
              text: 'Credential Capture Timeline'
            },
            tooltip: {
              callbacks: {
                label: function(context) {
                  return `Credentials: ${context.raw}`;
                }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                precision: 0
              },
              title: {
                display: true,
                text: 'Count'
              }
            },
            x: {
              title: {
                display: true,
                text: 'Time'
              }
            }
          }
        }
      });
    })
    .catch(error => console.error('Error loading credential timeline data:', error));
}

/**
 * Update the credential timeline chart with fresh data
 */
function updateCredentialTimeline() {
  if (!credentialTimelineChart) return;
  
  fetch('/api/stats/credentials/timeline')
    .then(response => response.json())
    .then(data => {
      credentialTimelineChart.data.labels = data.labels;
      credentialTimelineChart.data.datasets[0].data = data.values;
      credentialTimelineChart.update();
    })
    .catch(error => console.error('Error updating credential timeline:', error));
}

/**
 * Initialize the client connection chart
 */
function initClientConnectionChart() {
  const ctx = document.getElementById('clientConnectionChart');
  if (!ctx) return;
  
  fetch('/api/stats/clients')
    .then(response => response.json())
    .then(data => {
      clientConnectionChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['Total Clients', 'Connected', 'Deauthenticated', 'Captured'],
          datasets: [{
            label: 'Client Status',
            data: [
              data.total_clients || 0,
              data.connected || 0,
              data.deauthenticated || 0,
              data.captured || 0
            ],
            backgroundColor: [
              'rgba(54, 162, 235, 0.5)',
              'rgba(75, 192, 192, 0.5)',
              'rgba(255, 99, 132, 0.5)',
              'rgba(255, 206, 86, 0.5)'
            ],
            borderColor: [
              'rgba(54, 162, 235, 1)',
              'rgba(75, 192, 192, 1)',
              'rgba(255, 99, 132, 1)',
              'rgba(255, 206, 86, 1)'
            ],
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: {
              display: false
            },
            title: {
              display: true,
              text: 'Client Connection Status'
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                precision: 0
              }
            }
          }
        }
      });
    })
    .catch(error => console.error('Error loading client connection data:', error));
}

/**
 * Update the client connection chart with fresh data
 */
function updateClientConnections() {
  if (!clientConnectionChart) return;
  
  fetch('/api/stats/clients')
    .then(response => response.json())
    .then(data => {
      clientConnectionChart.data.datasets[0].data = [
        data.total_clients || 0,
        data.connected || 0,
        data.deauthenticated || 0,
        data.captured || 0
      ];
      clientConnectionChart.update();
    })
    .catch(error => console.error('Error updating client connections:', error));
}

/**
 * Initialize the attack success rate doughnut chart
 */
function initAttackSuccessChart() {
  const ctx = document.getElementById('attackSuccessChart');
  if (!ctx) return;
  
  fetch('/api/stats/success_rate')
    .then(response => response.json())
    .then(data => {
      attackSuccessChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: ['Successful Captures', 'Failed Attempts'],
          datasets: [{
            data: [data.success || 0, data.failure || 0],
            backgroundColor: [
              'rgba(75, 192, 192, 0.5)',
              'rgba(255, 99, 132, 0.5)'
            ],
            borderColor: [
              'rgba(75, 192, 192, 1)',
              'rgba(255, 99, 132, 1)'
            ],
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: {
              position: 'bottom'
            },
            title: {
              display: true,
              text: 'Capture Success Rate'
            },
            tooltip: {
              callbacks: {
                label: function(context) {
                  const total = context.dataset.data.reduce((a, b) => a + b, 0);
                  const percentage = Math.round((context.raw / total) * 100);
                  return `${context.label}: ${percentage}% (${context.raw})`;
                }
              }
            }
          },
          cutout: '60%'
        }
      });
    })
    .catch(error => console.error('Error loading attack success data:', error));
}

/**
 * Update the attack success chart with fresh data
 */
function updateAttackSuccess() {
  if (!attackSuccessChart) return;
  
  fetch('/api/stats/success_rate')
    .then(response => response.json())
    .then(data => {
      attackSuccessChart.data.datasets[0].data = [data.success || 0, data.failure || 0];
      attackSuccessChart.update();
    })
    .catch(error => console.error('Error updating attack success rate:', error));
}

/**
 * Export chart as image
 * @param {string} chartId - The ID of the chart canvas element
 * @param {string} format - Export format ('png' or 'jpg')
 */
function exportChart(chartId, format = 'png') {
  const canvas = document.getElementById(chartId);
  if (!canvas) return;
  
  // Create temporary link for download
  const link = document.createElement('a');
  link.download = `captiveclone-chart-${new Date().toISOString()}.${format}`;
  link.href = canvas.toDataURL(`image/${format}`);
  link.click();
}

// Initialize charts when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  // Check if we're on a page with charts
  if (document.getElementById('credentialTimelineChart') || 
      document.getElementById('clientConnectionChart') || 
      document.getElementById('attackSuccessChart')) {
    // Dynamically load Chart.js from CDN
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
    script.onload = initCharts;
    document.head.appendChild(script);
  }
}); 