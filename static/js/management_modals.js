/*
 * management_modals.js
 * ─────────────────────────────────────────────
 * Generic "click a row -> view detail -> Edit -> edit modal" flow,
 * shared by Product Management and Supplier Management pages.
 *
 * Detail values are normally plain text, but two special shapes
 * are recognized:
 *   - {"__type": "badge", "cls": "...", "icon": "...", "text": "..."}
 *     renders as a colored status-badge instead of plain text.
 *   - a plain JS array renders as a bulleted list instead of one
 *     comma-joined line (used for Supplier's Associated Products).
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

    function renderDetailValue(value) {
        if (value && typeof value === 'object' && value.__type === 'badge') {
            var badge = document.createElement('span');
            badge.className = 'status-badge ' + value.cls;
            badge.innerHTML = '<i class="bi ' + value.icon + '" aria-hidden="true"></i> ' + value.text;
            return { el: badge, stacked: false };
        }

        if (value && typeof value === 'object' && value.__type === 'image') {
            if (!value.url) {
                return { el: document.createTextNode('No photo uploaded'), stacked: false };
            }
            var img = document.createElement('img');
            img.src = value.url;
            img.alt = 'Profile photo';
            img.className = 'detail-value-image';
            return { el: img, stacked: true };
        }

        if (Array.isArray(value)) {
            if (value.length === 0) {
                var empty = document.createTextNode('—');
                return { el: empty, stacked: false };
            }
            var list = document.createElement('ul');
            list.className = 'detail-value-list';
            value.forEach(function (item) {
                var li = document.createElement('li');
                li.textContent = item;
                list.appendChild(li);
            });
            return { el: list, stacked: true };
        }

        return { el: document.createTextNode(value), stacked: false };
    }

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

                var rendered = renderDetailValue(detailData[label]);
                valueEl.appendChild(rendered.el);
                if (rendered.stacked) rowEl.classList.add('detail-row--stacked');

                rowEl.appendChild(labelEl);
                rowEl.appendChild(valueEl);
                detailBody.appendChild(rowEl);
            });

            detailModal.show();
        });
    });

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