/*
 * forms.js
 * ─────────────────────────────────────────────
 * Small, reusable form-enhancement behaviors that don't require a
 * page reload or a backend call.
 *
 * Currently handles: auto-filling a read-only display field based
 * on the selected option in a related dropdown (e.g. showing a
 * product's supplier once a product is chosen on the Receive Goods
 * form). Generic by design — any future field pair (e.g. "Category"
 * auto-showing based on a chosen Product) can reuse this without
 * writing new JS, just by adding the matching data-attributes below.
 *
 * Usage:
 *   <select data-autofill-source="supplier" data-autofill-target="id_supplier_display">
 *       <option data-autofill-value="Acme Corp">...</option>
 *   </select>
 *   <input id="id_supplier_display" disabled>
 */
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-autofill-source]').forEach(function (source) {
        var targetId = source.getAttribute('data-autofill-target');
        var target = document.getElementById(targetId);
        if (!target) return;

        source.addEventListener('change', function () {
            var selected = source.options[source.selectedIndex];
            target.value = selected.getAttribute('data-autofill-value') || '—';
        });
    });
});