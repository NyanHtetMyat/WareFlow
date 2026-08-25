/*
 * location_cascade.js
 * ─────────────────────────────────────────────
 * Wires up the Product combobox + Zone->Rack->Bin cascade shared by
 * Receive Goods, Dispatch Goods, and Stock Adjustment Request. One
 * generic function drives all three via configuration instead of
 * duplicating the cascade logic three times.
 *
 * Expects each page to have combobox_field.html includes with
 * field_id="product"/"zone"/"rack"/"bin", plus throwaway hidden
 * inputs #zone_value/#rack_value/#bin_value, plus the REAL Django
 * hidden fields #id_product/#id_location.
 */

function _buildProductOptions(products) {
    return products.map(function (p) {
        return {
            id: p.id,
            label: p.sku + ' — ' + p.name,
            searchText: (p.sku + ' ' + p.name).toLowerCase(),
            supplierName: p.supplier_name,
        };
    });
}

function _buildZoneOptions(tree) {
    return Object.keys(tree).sort().map(function (zone) {
        return { id: zone, label: zone, searchText: zone.toLowerCase() };
    });
}

function _buildRackOptions(tree, zone) {
    var racks = (tree && tree[zone]) || {};
    return Object.keys(racks).sort(function (a, b) { return Number(a) - Number(b); }).map(function (rack) {
        return { id: rack, label: 'Rack ' + rack, searchText: rack };
    });
}

function _buildBinOptions(tree, zone, rack) {
    var bins = ((tree && tree[zone] && tree[zone][rack]) || []);
    return bins.slice().sort(function (a, b) { return a.bin - b.bin; }).map(function (b) {
        var label = 'Bin ' + b.bin + (b.quantity !== undefined ? ' — ' + b.quantity + ' in stock' : '');
        return { id: b.id, label: label, searchText: String(b.bin), quantity: b.quantity };
    });
}

/**
 * @param {Object} opts
 * @param {boolean} opts.productFirst - true for Dispatch/Decrease: Zone locked until a Product is chosen.
 * @param {Array}   opts.productOptions - [{id, sku, name, supplier_name?}]
 * @param {Object}  opts.locationTree - flat {zone:{rack:[...]}} (unrestricted) OR {productId:{zone:{rack:[...]}}} (restricted), matching productFirst
 * @param {Object}  [opts.stockLookup] - flat {"productId:locationId": quantity}, used only when !productFirst
 * @param {string}  [opts.stockInfoId] - element id for the "Current stock" indicator text
 * @param {Function}[opts.onProductSelect] - called with the selected product option (or null) on every product change
 */
function createLocationCascade(opts) {
    var productHidden = document.getElementById('id_product');
    var locationHidden = document.getElementById('id_location');

    var productCombo = new Combobox(document.getElementById('product_combobox'), productHidden, {
        placeholder: 'Search SKU or product name…', lockedPlaceholder: 'No products available',
    });
    var zoneCombo = new Combobox(document.getElementById('zone_combobox'), document.getElementById('zone_value'), {
        placeholder: 'Search zone…', lockedPlaceholder: opts.productFirst ? 'Select a product first' : 'Select a zone',
    });
    var rackCombo = new Combobox(document.getElementById('rack_combobox'), document.getElementById('rack_value'), {
        placeholder: 'Search rack…', lockedPlaceholder: 'Select a zone first',
    });
    var binCombo = new Combobox(document.getElementById('bin_combobox'), document.getElementById('bin_value'), {
        placeholder: 'Search bin…', lockedPlaceholder: 'Select a rack first',
    });

    var stockInfo = opts.stockInfoId ? document.getElementById(opts.stockInfoId) : null;
    var currentTree = opts.locationTree || {};

    function setLocationValue(id, quantity) {
        locationHidden.value = id || '';
        if (quantity !== undefined && quantity !== null) {
            locationHidden.dataset.quantity = quantity;
        } else {
            delete locationHidden.dataset.quantity;
        }
        // Lets adjustments.js react to Location changes without any
        // direct coupling between the two scripts.
        locationHidden.dispatchEvent(new Event('change'));
    }

    function updateStockInfo() {
        if (!stockInfo) return;
        var locationId = locationHidden.value;
        if (!locationId) { stockInfo.textContent = ''; stockInfo.classList.remove('stock-info-active'); return; }

        if (opts.productFirst) {
            var qty = locationHidden.dataset.quantity;
            stockInfo.textContent = qty !== undefined ? ('Current stock at this location: ' + qty + ' units') : '';
        } else {
            var key = productHidden.value + ':' + locationId;
            var lookedUp = opts.stockLookup ? opts.stockLookup[key] : undefined;
            var qty2 = lookedUp !== undefined ? lookedUp : 0;
            stockInfo.textContent = qty2 > 0
                ? ('Current stock at this location: ' + qty2 + ' units')
                : 'No current stock at this location.';
        }
        stockInfo.classList.add('stock-info-active');
    }

    // ── Product selection ──────────────────────────────────────────────
    productCombo.onChange = function (productId, opt) {
        rackCombo.clear(); rackCombo.lock();
        binCombo.clear(); binCombo.lock();
        setLocationValue('', null);

        if (opts.productFirst) {
            if (!productId) {
                zoneCombo.lock('Select a product first');
            } else {
                var productTree = currentTree[productId] || {};
                zoneCombo.setOptions(_buildZoneOptions(productTree));
                zoneCombo.unlock();
            }
        }

        if (opts.onProductSelect) opts.onProductSelect(opt);
        updateStockInfo();
    };

    // ── Zone selection ────────────────────────────────────────────────
    zoneCombo.onChange = function (zoneId) {
        rackCombo.clear();
        binCombo.clear(); binCombo.lock();
        setLocationValue('', null);
        if (!zoneId) { rackCombo.lock(); updateStockInfo(); return; }

        var scopedTree = opts.productFirst ? (currentTree[productHidden.value] || {}) : currentTree;
        rackCombo.setOptions(_buildRackOptions(scopedTree, zoneId));
        rackCombo.unlock();
        updateStockInfo();
    };

    // ── Rack selection ────────────────────────────────────────────────
    rackCombo.onChange = function (rackId) {
        binCombo.clear();
        setLocationValue('', null);
        if (!rackId) { binCombo.lock(); updateStockInfo(); return; }

        var scopedTree = opts.productFirst ? (currentTree[productHidden.value] || {}) : currentTree;
        binCombo.setOptions(_buildBinOptions(scopedTree, zoneCombo.getValue(), rackId));
        binCombo.unlock();
        updateStockInfo();
    };

    // ── Bin selection -> resolves the actual Location PK ────────────────
    binCombo.onChange = function (binOptionId, opt) {
        setLocationValue(binOptionId, opt ? opt.quantity : null);
        updateStockInfo();
    };

    // ── Initial setup ──────────────────────────────────────────────────
    productCombo.setOptions(_buildProductOptions(opts.productOptions || []));
    rackCombo.lock();
    binCombo.lock();

    if (!opts.productFirst) {
        zoneCombo.setOptions(_buildZoneOptions(currentTree));
        zoneCombo.unlock();
    } else {
        zoneCombo.lock('Select a product first');
    }

    return {
        /** Swaps the Product combobox's option list (e.g. Increase <-> Decrease mode). */
        setProductOptions: function (products) {
            productCombo.setOptions(_buildProductOptions(products));
        },
        /** Swaps the active Location tree and re-locks the cascade to its initial state for the new mode. */
        setLocationTree: function (tree, productFirst) {
            currentTree = tree || {};
            opts.productFirst = productFirst;

            rackCombo.clear(); rackCombo.lock();
            binCombo.clear(); binCombo.lock();
            setLocationValue('', null);

            if (!productFirst) {
                zoneCombo.setOptions(_buildZoneOptions(currentTree));
                zoneCombo.unlock();
            } else {
                zoneCombo.clear();
                zoneCombo.lock('Select a product first');
            }
            updateStockInfo();
        },
    };
}