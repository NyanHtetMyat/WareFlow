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
    var editBtn = document.getElementById('detailEditButton');
    if (!resetBtn || !toggleBtn) return;

    var current = { pk: null, username: null, isActive: null };

    document.querySelectorAll('.detail-row-trigger').forEach(function (row) {
        row.addEventListener('click', function () {
            current.pk = row.getAttribute('data-pk');
            current.username = row.getAttribute('data-username');
            current.isActive = row.getAttribute('data-is-active') === 'true';
            var isSelf = row.getAttribute('data-is-self') === 'true';
            var isTargetAdmin = row.getAttribute('data-role') === 'ADMIN';

            if (current.isActive) {
                toggleLabel.textContent = 'Deactivate Account';
                toggleIcon.className = 'bi bi-slash-circle';
                toggleBtn.className = 'btn btn-sm btn-reject';
            } else {
                toggleLabel.textContent = 'Reactivate Account';
                toggleIcon.className = 'bi bi-check-circle';
                toggleBtn.className = 'btn btn-sm btn-approve';
            }

            // On the Admin's own account, or ANY other Admin
            // account: hide Deactivate/Reactivate entirely (not just
            // disable) — the matching hard block exists server-side
            // in accounts.views.user_toggle_active, so this is UX
            // only, never the actual security boundary. Edit stays
            // visible for other Admins (their profile fields, just
            // not Role, remain editable — see setRoleFieldForEdit),
            // but is still hidden for self, same as before. Reset
            // Password intentionally stays available in every case.
            toggleBtn.style.display = (isSelf || isTargetAdmin) ? 'none' : '';
            if (editBtn) editBtn.style.display = (isSelf || isTargetAdmin) ? 'none' : '';
        });
    });

    var confirmModalEl = document.getElementById('accountActionConfirmModal');
    if (!confirmModalEl) return;
    var confirmModal = new bootstrap.Modal(confirmModalEl);

    var detailModalEl = document.getElementById('detailModal');
    var confirmForm = document.getElementById('accountActionConfirmForm');
    var confirmTitle = document.getElementById('accountActionConfirmTitle');
    var confirmBody = document.getElementById('accountActionConfirmBody');
    var confirmButton = document.getElementById('accountActionConfirmButton');
    var confirmIconWrap = document.getElementById('accountActionConfirmIcon');
    var confirmIcon = confirmIconWrap ? confirmIconWrap.querySelector('i') : null;

    function setConfirmIcon(variant, iconClass) {
        if (!confirmIconWrap || !confirmIcon) return;
        confirmIconWrap.className = 'confirm-modal-icon confirm-modal-icon--' + variant;
        confirmIcon.className = 'bi ' + iconClass;
    }

    resetBtn.addEventListener('click', function () {
        var detailModal = bootstrap.Modal.getInstance(detailModalEl);
        if (detailModal) detailModal.hide();

        confirmTitle.textContent = 'Reset Password';
        setConfirmIcon('warning', 'bi-key-fill');
        confirmBody.innerHTML = 'Reset <strong>' + current.username + '</strong>’s password to the system default? They should change it after logging in.';
        confirmButton.textContent = 'Reset Password';
        confirmButton.className = 'btn btn-dispatch';
        confirmForm.action = confirmForm.dataset.resetUrlTemplate.replace('0', current.pk);
        confirmModal.show();
    });

    toggleBtn.addEventListener('click', function () {
        if (toggleBtn.disabled) return;
        var detailModal = bootstrap.Modal.getInstance(detailModalEl);
        if (detailModal) detailModal.hide();
        var activating = !current.isActive;
        confirmTitle.textContent = activating ? 'Reactivate Account' : 'Deactivate Account';
        setConfirmIcon(
            activating ? 'success' : 'danger',
            activating ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill'
        );
        confirmBody.innerHTML = 'Are you sure you want to <strong>' + (activating ? 'reactivate' : 'deactivate') +
            '</strong> ' + current.username + '’s account? This action will ' +
            (activating ? 'restore' : 'revoke') + ' their access to the system.';
        confirmButton.textContent = activating ? 'Reactivate' : 'Deactivate';
        confirmButton.className = activating ? 'btn btn-approve' : 'btn btn-danger';
        confirmForm.action = confirmForm.dataset.toggleUrlTemplate.replace('0', current.pk);
        confirmModal.show();
    });
});