/*
 * report_charts.js
 * ─────────────────────────────────────────────
 * Renders whichever charts exist on the currently active Reports
 * tab. Each render function checks for its own canvas before
 * running, so this one script safely covers all 5 tabs.
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof Chart === 'undefined') return;

    function readData(scriptId) {
        var el = document.getElementById(scriptId);
        return el ? JSON.parse(el.textContent) : null;
    }

    // ── Activity: Received vs Dispatched trend line ──────────────────
    var activityData = readData('activity-chart-data');
    var activityCanvas = document.getElementById('activityTrendChart');
    if (activityData && activityCanvas) {
        new Chart(activityCanvas, {
            type: 'line',
            data: {
                labels: activityData.labels,
                datasets: [
                    { label: 'Received', data: activityData.received, borderColor: '#2F9E63', backgroundColor: 'rgba(47,158,99,0.1)', tension: 0.3, fill: true, borderWidth: 3, pointRadius: 3 },
                    { label: 'Dispatched', data: activityData.dispatched, borderColor: '#E8871E', backgroundColor: 'rgba(232,135,30,0.1)', tension: 0.3, fill: true, borderWidth: 3, pointRadius: 3 },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom', labels: { usePointStyle: true } } },
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
    }

    // ── Generic ranked horizontal bar (Products top-5s) ───────────────
    // Optional "names" array in the data (SKU -> full product name)
    // drives the tooltip title, so the tooltip shows the product's
    // real name instead of just repeating the SKU already visible
    // on the axis.
    function renderRankedBar(canvasId, dataId, color) {
        var data = readData(dataId);
        var canvas = document.getElementById(canvasId);
        if (!data || !canvas) return;

        var tooltipOptions = {};
        if (data.names) {
            tooltipOptions = {
                callbacks: {
                    title: function (items) { return data.names[items[0].dataIndex]; },
                },
            };
        }

        new Chart(canvas, {
            type: 'bar',
            data: { labels: data.labels, datasets: [{ data: data.values, backgroundColor: color, borderRadius: 4 }] },
            options: {
                indexAxis: 'y',
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: tooltipOptions },
                scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
    }
    renderRankedBar('topReceivedChart', 'top-received-data', '#2F9E63');
    renderRankedBar('topDispatchedChart', 'top-dispatched-data', '#E8871E');

    // ── Locations: ranked bar with a multi-line product breakdown tooltip ──
    // Kept separate from renderRankedBar above rather than folding
    // in another conditional branch — this tooltip is a genuinely
    // different shape (a list, not a single title override), so a
    // dedicated function stays easier to read than one function
    // trying to serve both cases.
    (function renderLocationsChart() {
        var data = readData('top-locations-data');
        var canvas = document.getElementById('topLocationsChart');
        if (!data || !canvas) return;

        new Chart(canvas, {
            type: 'bar',
            data: { labels: data.labels, datasets: [{ data: data.values, backgroundColor: '#1E2A45', borderRadius: 4 }] },
            options: {
                indexAxis: 'y',
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: function (items) { return items[0].label; },
                            label: function (context) {
                                var items = (data.breakdown && data.breakdown[context.dataIndex]) || [];
                                if (items.length === 0) return 'No stock breakdown available';
                                return items.map(function (p) { return p.name + ': ' + p.quantity + ' units'; });
                            },
                        },
                    },
                },
                scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
    })();

    // ── Categories: SKU-count Treemap ─────────────────────────────────
    var treemapData = readData('category-treemap-data');
    var treemapCanvas = document.getElementById('categoryTreemapChart');
    if (treemapData && treemapCanvas) {
        var palette = ['#1E2A45', '#2F9E63', '#E8871E', '#6366F1', '#EAB308', '#D64545', '#2A3B5C', '#92700B'];
        var treeNodes = treemapData.labels.map(function (label, i) {
            return { name: label, value: treemapData.values[i], pct: treemapData.percentages[i] };
        });

        new Chart(treemapCanvas, {
            type: 'treemap',
            data: {
                datasets: [{
                    tree: treeNodes,
                    key: 'value',
                    labels: {
                        display: true,
                        color: '#fff',
                        font: { weight: '600' },
                        // Tooltip below shows the FULL name; this
                        // in-tile label is allowed to visually clip
                        // (the plugin handles that itself) since
                        // that's expected for small tiles/long names.
                        formatter: function (ctx) {
                            var raw = ctx.raw && ctx.raw._data;
                            return raw ? [raw.name, raw.pct + '%'] : '';
                        },
                    },
                    backgroundColor: function (ctx) {
                        return palette[ctx.dataIndex % palette.length];
                    },
                    spacing: 2,
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            // Full, untruncated category name — this
                            // is the actual fix for long names that
                            // get visually clipped inside the tile
                            // itself (e.g. "Electric Vehic...").
                            title: function (items) {
                                return items[0].raw._data.name;
                            },
                            label: function (item) {
                                var raw = item.raw._data;
                                return raw.value + ' SKUs (' + raw.pct + '%)';
                            },
                        },
                    },
                },
            },
        });
    }

    // ── Adjustments: status donut ──────────────────────────────────────
    var adjStatusData = readData('adjustment-status-data');
    var adjStatusCanvas = document.getElementById('adjustmentStatusChart');
    if (adjStatusData && adjStatusCanvas) {
        new Chart(adjStatusCanvas, {
            type: 'doughnut',
            data: { labels: adjStatusData.labels, datasets: [{ data: adjStatusData.values, backgroundColor: ['#E8871E', '#2F9E63', '#D64545'] }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true } } } },
        });
    }

    // ── Adjustments: daily submission trend ────────────────────────────
    var adjTrendData = readData('adjustment-trend-data');
    var adjTrendCanvas = document.getElementById('adjustmentTrendChart');
    if (adjTrendData && adjTrendCanvas) {
        new Chart(adjTrendCanvas, {
            type: 'bar',
            data: { labels: adjTrendData.labels, datasets: [{ data: adjTrendData.values, backgroundColor: '#6366F1', borderRadius: 4 }] },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });
    }
});