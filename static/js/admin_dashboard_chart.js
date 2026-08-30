/*
 * admin_dashboard_chart.js
 * ─────────────────────────────────────────────
 * Renders the Admin Dashboard's single chart: a vertical bar chart
 * of User Role Distribution (Staff / Manager / Admin counts). Kept
 * in its own small file rather than folded into dashboard_chart.js,
 * which is scoped specifically to the Manager Dashboard's own
 * charts — neither dashboard's script needs to know the other
 * exists.
 *
 * No animation config here — Chart.js's default entrance animation
 * already applies (same as every other chart in the project, none
 * of which set `animation: false`), which is enough to satisfy the
 * "subtle entrance animation" requirement without extra code.
 */
document.addEventListener('DOMContentLoaded', function () {
    var dataScript = document.getElementById('role-distribution-data');
    var canvas = document.getElementById('roleDistributionChart');
    if (!dataScript || !canvas || typeof Chart === 'undefined') return;

    var roleData = JSON.parse(dataScript.textContent);

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: roleData.labels,
            datasets: [{
                data: roleData.values,
                // Staff = primary navy, Manager = warning amber,
                // Admin = danger red — WareFlow's actual semantic
                // colors (variables.css), matching each role's
                // meaning rather than an arbitrary chart palette.
                backgroundColor: ['#1E2A45', '#EAB308', '#D64545'],
                borderRadius: 6,
                maxBarThickness: 40,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: true },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    // Pinned to the TOTAL user count, not the
                    // tallest individual bar — so each bar's height
                    // reads as "this role's share of everyone",
                    // not just relative to the other two roles.
                    max: roleData.total,
                    ticks: { precision: 0 },
                },
            },
        },
    });
});