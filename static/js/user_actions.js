/*
 * user_actions.js
 * ─────────────────────────────────────────────
 * Powers User Management's two account ACTIONS — Deactivate/
 * Reactivate and Reset Password — which deliberately live OUTSIDE
 * management_modals.js's generic Detail->Edit flow, since they're
 * account actions, not field edits. Reuses the exact same
 * shared-confirmation-modal pattern already established for
 * Approve/Reject on the Adjustment Requests page.
 *
 * The two action buttons sit in a static area of the Detail modal
 * that management_modals.js never touches (it only rewrites
 * #detailModalBody's innerHTML), so a second independent listener
 * on the same .detail-row-trigger rows is what keeps these buttons
 * in sync with whichever row was last clicked.
 */
document.addEventListener('DOMContentLoaded', function () {
    var resetBtn = document.getElementById('resetPasswordBtn');
    var toggleBtn = document.getElementById('toggleActiveBtn');
    var toggleLabel = document.getElementById('toggleActiveBtnLabel');
    var toggleIcon = document.getElementById('toggleActiveBtnIcon');
    if (!resetBtn || !toggleBtn) return;

    var current = { pk: null, username: null, isActive: null };

    document.querySelectorAll('.detail-row-trigger').forEach(function (row) {
        row.addEventListener('click', function () {
            current.pk = row.getAttribute('data-pk');
            current.username = row.getAttribute('data-username');
            current.isActive = row.getAttribute('data-is-active') === 'true';
            var isSelf = row.getAttribute('data-is-self') === 'true';

            if (current.isActive) {
                toggleLabel.textContent = 'Deactivate Account';
                toggleIcon.className = 'bi bi-slash-circle';
                toggleBtn.className = 'btn btn-sm btn-reject';
            } else {
                toggleLabel.textContent = 'Reactivate Account';
                toggleIcon.className = 'bi bi-check-circle';
                toggleBtn.className = 'btn btn-sm btn-approve';
            }

            toggleBtn.disabled = isSelf;
            toggleBtn.title = isSelf ? "You can't deactivate your own account." : '';
        });
    });

    var confirmModalEl = document.getElementById('accountActionConfirmModal');
    if (!confirmModalEl) return;
    var confirmModal = new bootstrap.Modal(confirmModalEl);
    var confirmForm = document.getElementById('accountActionConfirmForm');
    var confirmTitle = document.getElementById('accountActionConfirmTitle');
    var confirmBody = document.getElementById('accountActionConfirmBody');
    var confirmButton = document.getElementById('accountActionConfirmButton');

    resetBtn.addEventListener('click', function () {
        confirmTitle.textContent = 'Reset Password';
        confirmBody.textContent = 'Reset ' + current.username + '’s password to the system default? They should change it after logging in.';
        confirmButton.textContent = 'Reset Password';
        confirmButton.className = 'btn btn-adjustment';
        confirmForm.action = confirmForm.dataset.resetUrlTemplate.replace('0', current.pk);
        confirmModal.show();
    });

    toggleBtn.addEventListener('click', function () {
        if (toggleBtn.disabled) return;
        var activating = !current.isActive;
        confirmTitle.textContent = activating ? 'Reactivate Account' : 'Deactivate Account';
        confirmBody.textContent = (activating ? 'Reactivate ' : 'Deactivate ') + current.username + '’s account?';
        confirmButton.textContent = activating ? 'Reactivate' : 'Deactivate';
        confirmButton.className = activating ? 'btn btn-approve' : 'btn btn-reject';
        confirmForm.action = confirmForm.dataset.toggleUrlTemplate.replace('0', current.pk);
        confirmModal.show();
    });
});