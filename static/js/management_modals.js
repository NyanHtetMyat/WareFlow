/*
 * management_modals.js
 * ─────────────────────────────────────────────
 * Generic "click a row -> view detail -> Edit -> edit modal" flow,
 * shared by Product Management and Supplier Management pages (and
 * any future management page built the same way — Locations, Users).
 *
 * Expected markup per page:
 *   - Table rows with class "detail-row-trigger", plus
 *     data-pk, data-detail='{...}' (label -> display value, shown
 *     read-only), and data-edit='{...}' (form field name -> value,
 *     used to prefill the edit form).
 *   - #detailModal / #detailModalBody / #detailEditButton
 *     (data-edit-title on the button sets the edit modal's title).
 *   - #editModal / #editModalForm / #editModalTitle. The form
 *     carries data-create-url and data-edit-url-template (the
 *     latter containing a literal "0" placeholder for the pk).
 *   - #addRecordButton (data-add-title) opens the same edit modal
 *     empty, in create mode.
 *
 * One shared edit modal serves both Add and Edit — matches the
 * same shared-modal pattern already used for Approve/Reject on the
 * Adjustment Requests page, rather than introducing a new pattern.
 */
document.addEventListener('DOMContentLoaded', function () {
    var detailModalEl = document.getElementById('detailModal');
    var editModalEl = document.getElementById('editModal');
    if (!detailModalEl || !editModalEl) return;

    var detailModal = new bootstrap.Modal(detailModalEl);
    var editModal = new bootstrap.Modal(editModalEl);

    var detailBody = document.getElementById('detailModalBody');
    var detailEditButton = document.getElementById('detailEditButton');

    var editForm = document.getElementById('editModalForm');
    var editTitle = document.getElementById('editModalTitle');

    var pendingEditData = null;
    var pendingEditPk = null;
    var openEditAfterDetailCloses = false;

    function fillEditForm(data) {
        editForm.reset();
        Object.keys(data || {}).forEach(function (fieldName) {
            var field = editForm.elements[fieldName];
            if (field) field.value = data[fieldName];
        });
    }

    // Row click -> show read-only Detail modal
    document.querySelectorAll('.detail-row-trigger').forEach(function (row) {
        row.addEventListener('click', function () {
            var detailData = JSON.parse(row.getAttribute('data-detail'));
            pendingEditData = JSON.parse(row.getAttribute('data-edit'));
            pendingEditPk = row.getAttribute('data-pk');

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

            detailModal.show();
        });
    });

    // Detail modal's "Edit" button -> close detail, THEN open edit.
    // Waiting for hidden.bs.modal (rather than opening immediately)
    // avoids Bootstrap's stacked-backdrop glitch when one modal
    // opens while another is still mid-close.
    if (detailEditButton) {
        detailEditButton.addEventListener('click', function () {
            openEditAfterDetailCloses = true;
            detailModal.hide();
        });
    }

    detailModalEl.addEventListener('hidden.bs.modal', function () {
        if (!openEditAfterDetailCloses) return;
        openEditAfterDetailCloses = false;

        editTitle.textContent = detailEditButton.dataset.editTitle || 'Edit';
        editForm.action = editForm.dataset.editUrlTemplate.replace('0', pendingEditPk);
        fillEditForm(pendingEditData);
        editModal.show();
    });

    // "Add" button -> open the same edit modal, empty, in create mode
    var addButton = document.getElementById('addRecordButton');
    if (addButton) {
        addButton.addEventListener('click', function () {
            editTitle.textContent = addButton.dataset.addTitle || 'Add';
            editForm.action = editForm.dataset.createUrl;
            fillEditForm({});
            editModal.show();
        });
    }
});