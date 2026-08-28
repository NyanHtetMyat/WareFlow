/*
 * tooltips.js
 * ─────────────────────────────────────────────
 * Global one-time initializer for Bootstrap tooltips on STATIC
 * elements — anything present in the initial page HTML (rendered
 * server-side, like the navbar's truncated name) is covered by this
 * single querySelectorAll + forEach on page load.
 *
 * This does NOT cover elements injected into the DOM after this
 * script runs (e.g. rows added dynamically via JS elsewhere in the
 * project) — those need their own explicit `new bootstrap.Tooltip(el)`
 * call at the point they're created, since Bootstrap has no built-in
 * mechanism to auto-detect newly-added [data-bs-toggle="tooltip"]
 * elements after its own initial scan. If a future dynamic case
 * needs this, initialize it locally in that feature's own script
 * rather than expanding this file to re-scan on a timer/observer.
 */
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        new bootstrap.Tooltip(el);
    });
});