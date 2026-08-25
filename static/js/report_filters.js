/*
 * report_filters.js
 * ─────────────────────────────────────────────
 * Shows/hides the Custom Range start/end date inputs based on the
 * range preset dropdown. The inputs stay in the DOM regardless (so
 * their values still submit if already filled in) — only their
 * visibility toggles, keeping this a pure UX convenience rather
 * than something the form's correctness depends on.
 */
document.addEventListener('DOMContentLoaded', function () {
    var rangeSelect = document.getElementById('id_range');
    var startGroup = document.getElementById('range-start-group');
    var endGroup = document.getElementById('range-end-group');
    if (!rangeSelect || !startGroup || !endGroup) return;

    function toggle() {
        var isCustom = rangeSelect.value === 'custom';
        startGroup.style.display = isCustom ? '' : 'none';
        endGroup.style.display = isCustom ? '' : 'none';
    }

    rangeSelect.addEventListener('change', toggle);
    toggle();
});