/*
 * inventory_chain.js
 * ─────────────────────────────────────────────
 * Chains a Location dropdown to whichever Product is currently
 * selected, so Staff only ever see Locations where that Product
 * genuinely has existing stock. Used on Dispatch Goods and Stock
 * Adjustment Request — the two operations that must target
 * EXISTING inventory rather than arbitrary Product/Location
 * combinations.
 *
 * Reads a JSON blob embedded via Django's json_script filter,
 * shaped as: { "<product_id>": [{id, label, quantity}, ...], ... }
 *
 * This is a UX convenience only — the server independently
 * re-validates the actual Product+Location pair in services.py
 * before applying any stock change, exactly as the business rules
 * require ("UI filtering is for user experience; the backend must
 * always re-check the business rules").
 */
document.addEventListener('DOMContentLoaded', function () {
    var productSelect = document.getElementById('id_product');
    var locationSelect = document.getElementById('id_location');
    var stockInfo = document.getElementById('stock-info');
    var dataScript = document.getElementById('inventory-map-data');

    if (!productSelect || !locationSelect || !dataScript) return;

    var inventoryMap = JSON.parse(dataScript.textContent);

    function resetLocationSelect(placeholderText) {
        locationSelect.innerHTML = '';
        var placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = placeholderText;
        locationSelect.appendChild(placeholder);
    }

    function updateStockInfo() {
        if (!stockInfo) return;
        var locations = inventoryMap[productSelect.value] || [];
        var match = locations.find(function (loc) {
            return String(loc.id) === locationSelect.value;
        });

        if (match) {
            stockInfo.textContent = 'Current stock: ' + match.quantity + ' units';
            stockInfo.classList.add('stock-info-active');
        } else {
            stockInfo.textContent = '';
            stockInfo.classList.remove('stock-info-active');
        }
    }

    productSelect.addEventListener('change', function () {
        var locations = inventoryMap[productSelect.value] || [];

        if (locations.length === 0) {
            resetLocationSelect('No stock recorded for this product');
            locationSelect.disabled = true;
            updateStockInfo();
            return;
        }

        resetLocationSelect('Select a location…');
        locations.forEach(function (loc) {
            var option = document.createElement('option');
            option.value = loc.id;
            option.textContent = loc.label + ' — ' + loc.quantity + ' in stock';
            option.dataset.quantity = loc.quantity; // read by adjustments.js to cap decrease requests
            locationSelect.appendChild(option);
        });
        locationSelect.disabled = false;
        updateStockInfo();
    });

    locationSelect.addEventListener('change', updateStockInfo);
});