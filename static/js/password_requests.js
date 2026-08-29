/*
 * password_requests.js
 * ─────────────────────────────────────────────
 * Admin's Password Reset Requests page: click a card -> "User
 * Details" overlay (same visual pattern as User Management's own
 * Detail modal) -> Reset Password or Reject, each confirmed via a
 * second shared modal. Deliberately its own small file rather than
 * reusing management_modals.js — there's no Edit form anywhere on
 * this page, just two account-recovery actions.
 */
document.addEventListener('DOMContentLoaded', function () {
    var detailModalEl = document.getElementById('detailModal');
    if (!detailModalEl) return;
    var detailModal = new bootstrap.Modal(detailModalEl);

    var detailBody = document.getElementById('detailModalBody');
    var resetBtn = document.getElementById('resetPasswordBtn');
    var rejectBtn = document.getElementById('rejectRequestBtn');

    var current = { pk: null, username: null };

    document.querySelectorAll('.detail-row-trigger').forEach(function (row) {
        row.addEventListener('click', function () {
            current.pk = row.getAttribute('data-pk');

            var detailData = JSON.parse(row.getAttribute('data-detail'));
            detailBody.innerHTML = '';
            Object.keys(detailData).forEach(function (label) {
                var rowEl = document.createElement('div');
                rowEl.className = 'detail-row';

                var labelEl = document.createElement('span');
                labelEl.className = 'detail-label';
                labelEl.textContent = label;

                var valueEl = document.createElement('span');
                valueEl.className = 'detail-value';
                valueEl.textContent = detailData[label];

                rowEl.appendChild(labelEl);
                rowEl.appendChild(valueEl);
                detailBody.appendChild(rowEl);
            });

            var header = JSON.parse(row.getAttribute('data-header'));
            current.username = header.full_name;

            var avatarImg = document.getElementById('userDetailAvatarImg');
            var avatarInitial = document.getElementById('userDetailAvatarInitial');
            var roleBadge = document.getElementById('userDetailRoleBadge');

            document.getElementById('userDetailName').textContent = header.full_name;

            avatarInitial.className = 'user-detail-avatar-initial profile-avatar--' + header.role;
            avatarInitial.textContent = header.avatar_initial;

            if (header.image_url) {
                avatarImg.src = header.image_url;
                avatarImg.style.display = '';
                avatarInitial.style.display = 'none';
            } else {
                avatarImg.style.display = 'none';
                avatarInitial.style.display = '';
            }

            roleBadge.className = 'status-badge ' + header.role_badge.cls;
            roleBadge.innerHTML = '<i class="bi ' + header.role_badge.icon + '" aria-hidden="true"></i> ' + header.role_badge.text;

            detailModal.show();
        });
    });

    var confirmModalEl = document.getElementById('requestActionConfirmModal');
    if (!confirmModalEl) return;
    var confirmModal = new bootstrap.Modal(confirmModalEl);

    var confirmForm = document.getElementById('requestActionConfirmForm');
    var confirmTitle = document.getElementById('requestActionConfirmTitle');
    var confirmBody = document.getElementById('requestActionConfirmBody');
    var confirmButton = document.getElementById('requestActionConfirmButton');
    var confirmIconWrap = document.getElementById('requestActionConfirmIcon');
    var confirmIcon = confirmIconWrap ? confirmIconWrap.querySelector('i') : null;
    var reasonWrap = document.getElementById('rejectionReasonWrap');
    var reasonField = document.getElementById('rejection_reason');

    function setConfirmIcon(variant, iconClass) {
        if (!confirmIconWrap || !confirmIcon) return;
        confirmIconWrap.className = 'confirm-modal-icon confirm-modal-icon--' + variant;
        confirmIcon.className = 'bi ' + iconClass;
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', function () {
            var openDetailModal = bootstrap.Modal.getInstance(detailModalEl);
            if (openDetailModal) openDetailModal.hide();

            confirmTitle.textContent = 'Reset Password';
            setConfirmIcon('warning', 'bi-key-fill');
            confirmBody.innerHTML = 'Reset <strong>' + current.username + '</strong>’s password to the system default and mark this request complete?';
            confirmButton.textContent = 'Reset Password';
            confirmButton.className = 'btn btn-dispatch';
            reasonWrap.classList.add('d-none');
            reasonField.value = '';
            confirmForm.action = confirmForm.dataset.completeUrlTemplate.replace('0', current.pk);
            confirmModal.show();
        });
    }

    if (rejectBtn) {
        rejectBtn.addEventListener('click', function () {
            var openDetailModal = bootstrap.Modal.getInstance(detailModalEl);
            if (openDetailModal) openDetailModal.hide();

            confirmTitle.textContent = 'Reject Request';
            setConfirmIcon('danger', 'bi-exclamation-triangle-fill');
            confirmBody.innerHTML = 'Reject the password reset request from <strong>' + current.username + '</strong>?';
            confirmButton.textContent = 'Reject';
            confirmButton.className = 'btn btn-reject';
            reasonWrap.classList.remove('d-none');
            confirmForm.action = confirmForm.dataset.rejectUrlTemplate.replace('0', current.pk);
            confirmModal.show();
        });
    }
});