/*
 * adjustments.js
 * ─────────────────────────────────────────────
 * Behavior for the Stock Adjustment Request pages.
 *
 *   1. Staff submission form — combines the Increase/Decrease
 *      toggle and a positive magnitude number into the single
 *      signed integer the backend expects, and runs a live
 *      character counter on the Reason field.
 *   2. Manager review page — powers one shared confirmation modal
 *      for both Approve and Reject, so every card's buttons reuse
 *      the same modal instead of needing one per card.
 */
document.addEventListener('DOMContentLoaded', function () {

    // ── Direction toggle + magnitude -> signed quantity_change ──────────
    var hiddenQuantity = document.getElementById('id_quantity_change');
    var magnitudeInput = document.getElementById('id_magnitude');
    var previewBadge = document.getElementById('quantity-preview');

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
    }

    if (magnitudeInput) {
        magnitudeInput.addEventListener('input', syncQuantityChange);
        document.querySelectorAll('input[name="adjustment_direction"]').forEach(function (radio) {
            radio.addEventListener('change', syncQuantityChange);
        });
        syncQuantityChange(); // set the initial value on page load
    }

    // ── Live character counter for the Reason textarea ──────────────────
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

    // ── Shared Approve/Reject confirmation modal (Manager review page) ──
    var confirmModalEl = document.getElementById('adjustmentConfirmModal');
    if (confirmModalEl) {
        var confirmModal = new bootstrap.Modal(confirmModalEl);
        var confirmForm = document.getElementById('adjustmentConfirmForm');
        var confirmTitle = document.getElementById('adjustmentConfirmTitle');
        var confirmBody = document.getElementById('adjustmentConfirmBody');
        var confirmButton = document.getElementById('adjustmentConfirmButton');

        document.querySelectorAll('[data-adjustment-action]').forEach(function (button) {
            button.addEventListener('click', function () {
                var action = button.getAttribute('data-adjustment-action'); // "approve" | "reject"
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