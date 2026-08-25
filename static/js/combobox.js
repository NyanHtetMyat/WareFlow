/*
 * combobox.js
 * ─────────────────────────────────────────────
 * Generic searchable dropdown ("combobox"). One reusable class
 * instead of writing "click to see all options, type to filter,
 * select to set a hidden field" four separate times per page
 * (Product + Zone + Rack + Bin).
 *
 * Expected markup per instance (see components/combobox_field.html):
 *   <div class="combobox" id="X_combobox">
 *     <div class="combobox-control">
 *       <input class="combobox-input">
 *     </div>
 *     <div class="combobox-panel" hidden></div>
 *   </div>
 * The real value-holding field (hidden form input, or an internal
 * throwaway hidden input for Zone/Rack/Bin) is passed in separately.
 */
class Combobox {
    constructor(rootEl, hiddenInput, config) {
        this.root = rootEl;
        this.hiddenInput = hiddenInput;
        this.input = rootEl.querySelector('.combobox-input');
        this.panel = rootEl.querySelector('.combobox-panel');
        this.placeholder = (config && config.placeholder) || 'Select…';
        this.lockedPlaceholder = (config && config.lockedPlaceholder) || 'Unavailable';
        this.onChange = (config && config.onChange) || function () {};

        this.options = [];
        this.filtered = [];
        this.activeIndex = -1;
        this.locked = false;

        this.input.placeholder = this.placeholder;
        this.input.setAttribute('aria-autocomplete', 'list');
        this.panel.setAttribute('role', 'listbox');

        this.input.addEventListener('focus', () => this._open());
        this.input.addEventListener('click', () => this._open());
        this.input.addEventListener('input', () => this._onType());
        this.input.addEventListener('keydown', (e) => this._onKeyDown(e));
        document.addEventListener('click', (e) => {
            if (!this.root.contains(e.target)) this._close();
        });
    }

    /** Replaces the available option list. Always clears any current selection. */
    setOptions(options) {
        this.options = options || [];
        this.clear();
    }

    /** Disables the field, clears its value, shows a locked placeholder. */
    lock(lockedPlaceholderOverride) {
        this.locked = true;
        this.input.disabled = true;
        this.input.placeholder = lockedPlaceholderOverride || this.lockedPlaceholder;
        this._close();
        this.hiddenInput.value = '';
        this.input.value = '';
    }

    /** Enables the field for interaction. */
    unlock() {
        this.locked = false;
        this.input.disabled = false;
        this.input.placeholder = this.placeholder;
    }

    /** Clears the current selection without changing lock state. */
    clear() {
        this.hiddenInput.value = '';
        this.input.value = '';
        this._close();
        this.onChange(null, null);
    }

    getValue() {
        return this.hiddenInput.value || null;
    }

    _open() {
        if (this.locked) return;
        this._render(this.input.value);
        this.panel.hidden = false;
        this.root.classList.add('combobox--open');
    }

    _close() {
        this.panel.hidden = true;
        this.root.classList.remove('combobox--open');
        this.activeIndex = -1;
    }

    _onType() {
        if (this.locked) return;
        this.hiddenInput.value = '';
        this._render(this.input.value);
        this.panel.hidden = false;
    }

    _render(query) {
        var q = (query || '').trim().toLowerCase();
        this.filtered = !q
            ? this.options
            : this.options.filter(function (opt) { return opt.searchText.indexOf(q) !== -1; });

        this.panel.innerHTML = '';
        this.activeIndex = -1;

        if (this.filtered.length === 0) {
            var empty = document.createElement('div');
            empty.className = 'combobox-empty';
            empty.textContent = 'No matches';
            this.panel.appendChild(empty);
            return;
        }

        var self = this;
        this.filtered.forEach(function (opt) {
            var item = document.createElement('div');
            item.className = 'combobox-option';
            item.setAttribute('role', 'option');
            item.textContent = opt.label;
            // mousedown (not click) fires before the input's blur, so
            // the selection isn't lost to the panel closing first.
            item.addEventListener('mousedown', function (e) {
                e.preventDefault();
                self._select(opt);
            });
            self.panel.appendChild(item);
        });
    }

    _select(opt) {
        this.hiddenInput.value = opt.id;
        this.input.value = opt.label;
        this._close();
        this.onChange(opt.id, opt);
    }

    _onKeyDown(e) {
        if (this.locked) return;
        if (e.key === 'Escape') { this._close(); return; }
        if (e.key === 'Enter') {
            e.preventDefault();
            if (this.activeIndex >= 0 && this.filtered[this.activeIndex]) this._select(this.filtered[this.activeIndex]);
            return;
        }
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            if (this.panel.hidden) { this._open(); return; }
            var delta = e.key === 'ArrowDown' ? 1 : -1;
            this.activeIndex = Math.max(0, Math.min(this.filtered.length - 1, this.activeIndex + delta));
            this._highlightActive();
        }
    }

    _highlightActive() {
        var items = this.panel.querySelectorAll('.combobox-option');
        var self = this;
        items.forEach(function (el, i) { el.classList.toggle('combobox-option--active', i === self.activeIndex); });
        if (items[this.activeIndex]) items[this.activeIndex].scrollIntoView({ block: 'nearest' });
    }
}