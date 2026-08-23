/*
 * sort_toggle.js
 * ─────────────────────────────────────────────
 * Powers the compact ascending/descending toggle button next to a
 * table's "Sort by" dropdown. Flips a hidden "dir" field between
 * asc/desc and re-submits the surrounding GET filter form — shared
 * by Inventory, Products, and Suppliers, since all three use the
 * identical sort dropdown + toggle button pattern.
 */
document.addEventListener('DOMContentLoaded', function () {
    var toggleButton = document.getElementById('dir-toggle-button');
    var dirInput = document.getElementById('id_dir');
    if (!toggleButton || !dirInput) return;

    var icon = toggleButton.querySelector('i');

    function updateButtonState() {
        var isDesc = dirInput.value === 'desc';
        toggleButton.title = isDesc ? 'Descending' : 'Ascending';
        toggleButton.setAttribute(
            'aria-label',
            isDesc ? 'Sorted descending — click for ascending' : 'Sorted ascending — click for descending'
        );
        if (icon) {
            icon.className = 'bi ' + (isDesc ? 'bi-sort-up' : 'bi-sort-down');
        }
    }

    toggleButton.addEventListener('click', function () {
        dirInput.value = dirInput.value === 'desc' ? 'asc' : 'desc';
        toggleButton.closest('form').submit();
    });

    updateButtonState();
});