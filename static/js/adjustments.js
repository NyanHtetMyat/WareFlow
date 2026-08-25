/*
 * adjustments.js
 * ─────────────────────────────────────────────
 * Behavior for the Stock Adjustment Request pages.
 *   1. Staff submission form — signed quantity assembly, live
 *      character counter, and capping a Decrease request at the
 *      selected location's current stock (read from the hidden
 *      #id_location field's data-quantity, set by
 *      location_cascade.js — services.submit_adjustment_request()
 *      still enforces this authoritatively).
 *   2. Manager review page — shared Approve/Reject confirmation modal.
 */
document.addEventListener('DOMContentLoaded', function () {

    var hiddenQuantity = document.getElementById('id_quantity_change');
    var magnitudeInput = document.getElementById('id_magnitude');
    var previewBadge = document.getElementById('quantity-preview');
    var locationHidden = document.getElementById('id_location');
    var magnitudeWarning = document.getElementById('magnitude-warning');
    var submitButton = document.getElementById('adjustment-submit-button');

    function getAvailableQuantity() {
        if (!locationHidden || locationHidden.dataset.quantity === undefined) return null;
        return parseInt(locationHidden.dataset.quantity, 10);
    }

    function syncQuantityChange() {
        if (!hiddenQuantity || !magnitudeInput) return;

        var magnitude = parseInt(magnitudeInput.value, 10) || 0;
        var checkedRadio = document.querySelector('input[name="adjustment_direction"]:checked');
        var isDecrease = checkedRadio && checkedRadio.value === 'decrease';
        var signedValue = isDecrease ? -magnitude : magnitude;

        hiddenQuantity.value = signedValue;

        if (previewBadge) {
            previewBadge.textContent = (signedValue > 0 ? '+' : '') + signedValue;
            previewBadge.classList.toggle('quantity-change-badge--increase', signedValue >= 0);
            previewBadge.classList.toggle('quantity-change-badge--decrease', signedValue < 0);
        }

        var availableQty = getAvailableQuantity();
        var exceedsStock = isDecrease && availableQty !== null && magnitude > availableQty;

        if (magnitudeInput) {
            magnitudeInput.max = (isDecrease && availableQty !== null) ? availableQty : '';
        }

        if (magnitudeWarning) {
            if (exceedsStock) {
                magnitudeWarning.textContent = 'Only ' + availableQty + ' units available at this location.';
                magnitudeWarning.classList.remove('d-none');
            } else {
                magnitudeWarning.classList.add('d-none');
            }
        }

        if (submitButton) submitButton.disabled = exceedsStock;
    }

    if (magnitudeInput) {
        magnitudeInput.addEventListener('input', syncQuantityChange);
        document.querySelectorAll('input[name="adjustment_direction"]').forEach(function (radio) {
            radio.addEventListener('change', syncQuantityChange);
        });
        if (locationHidden) {
            // location_cascade.js dispatches 'change' on this field
            // whenever its value updates — keeps this in sync with
            // zero direct coupling between the two scripts.
            locationHidden.addEventListener('change', syncQuantityChange);
        }
        syncQuantityChange();
    }

    var reasonField = document.getElementById('id_reason');
    var reasonCounter = document.getElementById('reason-counter');
    if (reasonField && reasonCounter) {
        var maxLength = reasonField.getAttribute('maxlength') || 500;
        var updateCounter = function () {
            reasonCounter.textContent = reasonField.value.length + ' / ' + maxLength;
        };
        reasonField.addEventListener('input', updateCounter);
        updateCounter();
    }

    var confirmModalEl = document.getElementById('adjustmentConfirmModal');
    if (confirmModalEl) {
        var confirmModal = new bootstrap.Modal(confirmModalEl);
        var confirmForm = document.getElementById('adjustmentConfirmForm');
        var confirmTitle = document.getElementById('adjustmentConfirmTitle');
        var confirmBody = document.getElementById('adjustmentConfirmBody');
        var confirmButton = document.getElementById('adjustmentConfirmButton');

        document.querySelectorAll('[data-adjustment-action]').forEach(function (button) {
            button.addEventListener('click', function () {
                var action = button.getAttribute('data-adjustment-action');
                var productLabel = button.getAttribute('data-product-label');
                confirmForm.action = button.getAttribute('data-action-url');

                if (action === 'approve') {
                    confirmTitle.textContent = 'Approve Adjustment';
                    confirmBody.textContent = 'Approve the stock adjustment for ' + productLabel + '? This will update inventory immediately.';
                    confirmButton.textContent = 'Approve';
                    confirmButton.className = 'btn btn-approve';
                } else {
                    confirmTitle.textContent = 'Reject Adjustment';
                    confirmBody.textContent = 'Reject the stock adjustment for ' + productLabel + '? This cannot be undone.';
                    confirmButton.textContent = 'Reject';
                    confirmButton.className = 'btn btn-reject';
                }
                confirmModal.show();
            });
        });
    }
});