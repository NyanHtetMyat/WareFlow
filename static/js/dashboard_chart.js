/*
 * dashboard_chart.js
 * ─────────────────────────────────────────────
 * Renders the Manager Dashboard's two data visualizations:
 *   1. A semicircle "gauge" doughnut chart for Stock Status
 *      (OK / Low / Out of Stock), replacing three identical KPI
 *      cards with one visualization.
 *   2. The Received vs Dispatched 7-day trend line chart.
 *
 * Deliberately the ONLY charts on this dashboard, per the confirmed
 * scope keeping it a concise overview — deeper analytics belong on
 * the future Reports page instead.
 */
document.addEventListener('DOMContentLoaded', function () {

    // ── Stock Status semicircle gauge ────────────────────────────────
    var stockScript = document.getElementById('stock-counts-data');
    var gaugeCanvas = document.getElementById('stockGaugeChart');
    if (stockScript && gaugeCanvas && typeof Chart !== 'undefined') {
        var stockCounts = JSON.parse(stockScript.textContent);

        new Chart(gaugeCanvas, {
            type: 'doughnut',
            data: {
                labels: ['OK', 'Low Stock', 'Out of Stock'],
                datasets: [{
                    data: [stockCounts.ok, stockCounts.low_stock, stockCounts.out_of_stock],
                    backgroundColor: ['#2F9E63', '#EAB308', '#D64545'],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                // circumference: 180 + rotation: 270 draws only the
                // top half of the doughnut, producing the semicircle
                // gauge look — the total count is shown as plain text
                // below the canvas instead, rather than overlaid, to
                // avoid the arc's empty bottom-half space.
                circumference: 180,
                rotation: 270,
                cutout: '72%',
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: true },
                },
            },
        });
    }
});