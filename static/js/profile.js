/*
 * profile.js
 * ─────────────────────────────────────────────
 * Client-side-only behavior for the Profile card's photo:
 *   - Selecting a file shows an instant preview (FileReader), no
 *     upload happens yet.
 *   - The (x) button clears the file input and reverts to the
 *     initial-letter fallback view — also no persistence yet.
 * Nothing here touches the server; both actions only take effect
 * once the surrounding form is actually submitted via Save Changes.
 */
document.addEventListener('DOMContentLoaded', function () {
    var fileInput = document.getElementById('id_image');
    var clearCheckbox = document.getElementById('id_image-clear');
    var previewImg = document.getElementById('avatar-preview-img');
    var previewInitial = document.getElementById('avatar-preview-initial');
    var removeBtn = document.getElementById('avatar-remove-btn');
    var uploadLabel = document.getElementById('upload-btn-label');

    if (!fileInput || !previewImg || !previewInitial || !removeBtn) return;

    function showImage(url) {
        previewImg.src = url;
        previewImg.style.display = '';
        previewInitial.style.display = 'none';
        removeBtn.style.display = '';
    }

    function showInitialFallback() {
        previewImg.removeAttribute('src');
        previewImg.style.display = 'none';
        previewInitial.style.display = '';
        removeBtn.style.display = 'none';
    }

    fileInput.addEventListener('change', function () {
        if (!fileInput.files || !fileInput.files[0]) return;

        var file = fileInput.files[0];
        if (uploadLabel) {
            uploadLabel.textContent = file.name;
            uploadLabel.closest('.profile-upload-btn').title = file.name; // full name still available on hover once CSS truncates the visible text
        }

        var reader = new FileReader();
        reader.onload = function (e) { showImage(e.target.result); };
        reader.readAsDataURL(file);

        // A freshly chosen file supersedes any pending removal.
        if (clearCheckbox) clearCheckbox.checked = false;
    });

    removeBtn.addEventListener('click', function () {
        fileInput.value = '';
        if (clearCheckbox) clearCheckbox.checked = true;
        if (uploadLabel) uploadLabel.textContent = 'Edit Photo';
        showInitialFallback();
    });
});