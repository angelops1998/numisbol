/* Shared searchable-select: bottom sheet (touch) + scroll-on-open (desktop) */
(function () {
    'use strict';

    function norm(s) { return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
    function isTouch() { return window.matchMedia('(hover: none)').matches; }

    /* ── Singleton bottom sheet ─────────────────────────────── */
    var ssBackdrop = document.createElement('div');
    ssBackdrop.className = 'ss-backdrop';
    var ssSheet = document.createElement('div');
    ssSheet.className = 'ss-sheet';
    ssSheet.innerHTML =
        '<div class="ss-sheet-handle"></div>' +
        '<div class="ss-sheet-header">' +
            '<span class="ss-sheet-title"></span>' +
            '<button type="button" class="ss-sheet-close" aria-label="Cerrar">✕</button>' +
        '</div>' +
        '<div class="ss-sheet-search-wrap">' +
            '<input type="text" class="ss-sheet-search" placeholder="Buscar…">' +
        '</div>' +
        '<ul class="ss-sheet-list"></ul>';
    document.body.appendChild(ssBackdrop);
    document.body.appendChild(ssSheet);

    var _activeSS = null;
    var _savedScrollY = 0;

    /* ── Keyboard-aware height ──────────────────────────────── */
    function onViewportResize() {
        if (!ssSheet.classList.contains('ss-active')) return;
        var vv = window.visualViewport;
        if (!vv) return;
        var keyboardHeight = window.innerHeight - vv.height - vv.offsetTop;
        if (keyboardHeight > 50) {
            ssSheet.style.bottom = keyboardHeight + 'px';
            ssSheet.style.maxHeight = (vv.height - 16) + 'px';
        } else {
            ssSheet.style.bottom = '0';
            ssSheet.style.maxHeight = '';
        }
    }
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', onViewportResize);
        window.visualViewport.addEventListener('scroll', onViewportResize);
    }

    function lockBodyScroll() {
        _savedScrollY = window.scrollY;
        document.body.style.top = -_savedScrollY + 'px';
        document.body.style.position = 'fixed';
        document.body.style.width = '100%';
        document.body.style.overflow = 'hidden';
    }
    function unlockBodyScroll() {
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.width = '';
        document.body.style.overflow = '';
        window.scrollTo({ top: _savedScrollY, behavior: 'instant' });
    }

    function navHeight() {
        var el = document.querySelector('nav, header, .navbar');
        return el ? el.offsetHeight : 0;
    }
    function scrollToAnchor(ss) {
        requestAnimationFrame(function () {
            var anchor = ss.closest('.form-group, .filter-group') || ss;
            var top = anchor.getBoundingClientRect().top + window.scrollY - navHeight() - 16;
            window.scrollTo({ top: top, behavior: 'smooth' });
        });
    }

    /* ── Open sheet ─────────────────────────────────────────── */
    function openSheet(ss, label, freeTextFields) {
        _activeSS = ss;
        var hidden = ss.querySelector('input[type=hidden]');
        var fieldName = ss.dataset.name;
        var allowFree = (freeTextFields || []).indexOf(fieldName) !== -1;
        var curVal = hidden ? hidden.value : '';

        lockBodyScroll();
        ssSheet.querySelector('.ss-sheet-title').textContent = label || 'Seleccionar';
        ssSheet.style.bottom = '0';
        ssSheet.style.maxHeight = '';

        /* Replace search input to clear old listeners */
        var oldSearch = ssSheet.querySelector('.ss-sheet-search');
        var sheetSearch = oldSearch.cloneNode(true);
        oldSearch.replaceWith(sheetSearch);
        var sheetList = ssSheet.querySelector('.ss-sheet-list');
        sheetSearch.value = '';
        sheetList.innerHTML = '';

        /* Empty-state */
        var emptyMsg = document.createElement('li');
        emptyMsg.className = 'ss-sheet-empty ss-sheet-hidden';
        emptyMsg.textContent = 'Sin resultados';

        /* Build items */
        ss.querySelectorAll('.ss-option, .ss-group').forEach(function (node) {
            if (node.classList.contains('ss-group')) {
                var li = document.createElement('li');
                li.className = 'ss-sheet-group';
                li.dataset.ssGroup = '1';
                li.textContent = node.textContent;
                sheetList.appendChild(li);
                return;
            }
            if (node.classList.contains('ss-custom-opt')) return;
            var li = document.createElement('li');
            var sel = node.dataset.value === curVal;
            li.className = 'ss-sheet-option' + (sel ? ' ss-sheet-selected' : '');
            li.dataset.value = node.dataset.value;
            li.dataset.label = node.textContent.trim();
            li.innerHTML = '<span class="ss-sheet-check">✓</span>' + node.textContent.trim();
            li.addEventListener('click', function () { selectSheetOption(li.dataset.value, li.dataset.label); });
            sheetList.appendChild(li);
        });

        /* Free-text custom option */
        var sheetCustom = null;
        if (allowFree) {
            sheetCustom = document.createElement('li');
            sheetCustom.className = 'ss-sheet-option ss-sheet-custom ss-sheet-hidden';
            sheetCustom.innerHTML = '<span class="ss-sheet-check">✓</span><em></em>';
            sheetCustom.addEventListener('click', function () {
                var val = sheetSearch.value.trim();
                if (!val) return;
                selectSheetOption(val, val);
            });
            sheetList.appendChild(sheetCustom);
        }
        sheetList.appendChild(emptyMsg);

        /* Filter logic */
        function filterOptions() {
            var term = norm(sheetSearch.value.trim());
            var raw = sheetSearch.value.trim();
            sheetList.querySelectorAll('.ss-sheet-option:not(.ss-sheet-custom)').forEach(function (li) {
                li.classList.toggle('ss-sheet-hidden', term !== '' && !norm(li.dataset.label).includes(term));
            });
            sheetList.querySelectorAll('.ss-sheet-group').forEach(function (grp) {
                var next = grp.nextElementSibling;
                var allHidden = true;
                while (next && !next.dataset.ssGroup) {
                    if (!next.classList.contains('ss-sheet-hidden') &&
                        !next.classList.contains('ss-sheet-custom') &&
                        !next.classList.contains('ss-sheet-empty')) {
                        allHidden = false; break;
                    }
                    next = next.nextElementSibling;
                }
                grp.classList.toggle('ss-sheet-hidden', allHidden);
            });
            if (sheetCustom) {
                var hasExact = Array.prototype.some.call(
                    sheetList.querySelectorAll('.ss-sheet-option:not(.ss-sheet-custom)'),
                    function (li) { return norm(li.dataset.value) === term; }
                );
                if (raw && !hasExact) {
                    sheetCustom.querySelector('em').textContent = 'Usar «' + raw + '»';
                    sheetCustom.classList.remove('ss-sheet-hidden');
                } else {
                    sheetCustom.classList.add('ss-sheet-hidden');
                }
            }
            var anyVisible = Array.prototype.some.call(
                sheetList.querySelectorAll('.ss-sheet-option:not(.ss-sheet-custom)'),
                function (li) { return !li.classList.contains('ss-sheet-hidden'); }
            );
            var customVisible = sheetCustom && !sheetCustom.classList.contains('ss-sheet-hidden');
            emptyMsg.classList.toggle('ss-sheet-hidden', anyVisible || customVisible);
        }
        sheetSearch.addEventListener('input', filterOptions);

        ssBackdrop.classList.add('ss-active');
        requestAnimationFrame(function () { ssSheet.classList.add('ss-active'); });
        setTimeout(function () {
            var sel = sheetList.querySelector('.ss-sheet-selected');
            if (sel) sel.scrollIntoView({ block: 'center' });
        }, 300);
    }

    function selectSheetOption(val, label) {
        if (!_activeSS) return;
        var ss = _activeSS;
        var hidden = ss.querySelector('input[type=hidden]');
        var valueEl = ss.querySelector('.ss-value');
        ss.querySelectorAll('.ss-option').forEach(function (o) { o.classList.remove('ss-selected'); });
        var match = ss.querySelector('.ss-option[data-value="' + CSS.escape(val) + '"]');
        if (match) match.classList.add('ss-selected');
        if (hidden) { hidden.value = val; hidden.dispatchEvent(new Event('change')); }
        valueEl.textContent = label;
        valueEl.classList.remove('placeholder');
        closeSheet();
        scrollToAnchor(ss);
    }

    function closeSheet() {
        ssSheet.classList.remove('ss-active');
        ssBackdrop.classList.remove('ss-active');
        ssSheet.style.bottom = '0';
        ssSheet.style.maxHeight = '';
        _activeSS = null;
        unlockBodyScroll();
    }

    ssSheet.querySelector('.ss-sheet-close').addEventListener('click', closeSheet);
    ssBackdrop.addEventListener('click', closeSheet);

    /* ── Public API ─────────────────────────────────────────── */
    window.initSearchableSelects = function (opts) {
        opts = opts || {};
        var freeTextFields = opts.freeTextFields || [];
        var scope = opts.container || document;

        scope.querySelectorAll('.searchable-select').forEach(function (ss) {
            var display = ss.querySelector('.ss-display');
            var valueEl = ss.querySelector('.ss-value');
            var search = ss.querySelector('.ss-search');
            var options = ss.querySelectorAll('.ss-option');
            var hidden = ss.querySelector('input[type=hidden]');
            var list = ss.querySelector('.ss-list');
            var fieldName = ss.dataset.name;
            var allowFree = freeTextFields.indexOf(fieldName) !== -1;

            if (!display) return;

            /* Desktop-only free-text "Usar «...»" injected into the dropdown */
            var customOpt = null;
            if (allowFree && list) {
                customOpt = document.createElement('li');
                customOpt.className = 'ss-option ss-custom-opt ss-hidden';
                list.appendChild(customOpt);
                customOpt.addEventListener('click', function (e) {
                    e.stopPropagation();
                    var val = search ? search.value.trim() : '';
                    if (!val) return;
                    options.forEach(function (o) { o.classList.remove('ss-selected'); });
                    customOpt.classList.add('ss-selected');
                    if (hidden) hidden.value = val;
                    valueEl.textContent = val;
                    valueEl.classList.remove('placeholder');
                    ss.classList.remove('open');
                });
            }

            display.addEventListener('click', function (e) {
                e.stopPropagation();
                if (isTouch()) {
                    var groupEl = ss.closest('.form-group, .filter-group');
                    var labelEl = groupEl ? groupEl.querySelector('label') : null;
                    var label = labelEl ? labelEl.textContent.replace(/\s*\*\s*$/, '').trim() : '';
                    openSheet(ss, label, freeTextFields);
                    return;
                }
                var wasOpen = ss.classList.contains('open');
                document.querySelectorAll('.searchable-select').forEach(function (s) { s.classList.remove('open'); });
                if (!wasOpen) {
                    ss.classList.add('open');
                    if (search) {
                        search.value = '';
                        setTimeout(function () { search.focus(); }, 50);
                    }
                    options.forEach(function (o) { o.classList.remove('ss-hidden'); });
                    if (customOpt) customOpt.classList.add('ss-hidden');
                    /* Scroll so dropdown is fully visible */
                    requestAnimationFrame(function () {
                        var dropdown = ss.querySelector('.ss-dropdown');
                        if (!dropdown) return;
                        var rect = dropdown.getBoundingClientRect();
                        if (rect.bottom > window.innerHeight - 8) {
                            var anchor = ss.closest('.form-group, .filter-group') || ss;
                            var top = anchor.getBoundingClientRect().top + window.scrollY - navHeight() - 16;
                            window.scrollTo({ top: top, behavior: 'smooth' });
                        }
                    });
                }
            });

            if (search) {
                search.addEventListener('input', function () {
                    var term = norm(this.value.trim());
                    var raw = this.value.trim();
                    options.forEach(function (opt) {
                        opt.classList.toggle('ss-hidden', !norm(opt.textContent).includes(term));
                    });
                    ss.querySelectorAll('.ss-group').forEach(function (group) {
                        var next = group.nextElementSibling;
                        var allHidden = true;
                        while (next && !next.classList.contains('ss-group')) {
                            if (!next.classList.contains('ss-hidden') && !next.classList.contains('ss-custom-opt')) {
                                allHidden = false; break;
                            }
                            next = next.nextElementSibling;
                        }
                        group.classList.toggle('ss-hidden', allHidden);
                    });
                    if (customOpt) {
                        var hasExact = Array.prototype.some.call(options, function (o) {
                            return !o.classList.contains('ss-custom-opt') &&
                                o.dataset.value && o.dataset.value.toLowerCase() === term;
                        });
                        if (raw && !hasExact) {
                            customOpt.textContent = 'Usar «' + raw + '»';
                            customOpt.classList.remove('ss-hidden');
                        } else {
                            customOpt.classList.add('ss-hidden');
                        }
                    }
                });
                search.addEventListener('click', function (e) { e.stopPropagation(); });
            }

            options.forEach(function (opt) {
                if (opt === customOpt) return;
                opt.addEventListener('click', function (e) {
                    e.stopPropagation();
                    options.forEach(function (o) { o.classList.remove('ss-selected'); });
                    if (customOpt) customOpt.classList.remove('ss-selected');
                    opt.classList.add('ss-selected');
                    if (hidden) { hidden.value = opt.dataset.value; hidden.dispatchEvent(new Event('change')); }
                    valueEl.textContent = opt.textContent.trim();
                    valueEl.classList.remove('placeholder');
                    ss.classList.remove('open');
                });
            });
        });

        /* Close all dropdowns on outside click (register only once) */
        if (!window._ssClickListenerAdded) {
            window._ssClickListenerAdded = true;
            document.addEventListener('click', function () {
                document.querySelectorAll('.searchable-select').forEach(function (s) { s.classList.remove('open'); });
            });
        }
    };

    /* ── Generic search sheet for custom autocompletes (mobile) ─
       opts: {
         title:      string,
         placeholder: string,
         fetchFn:    function(query, callback)  — calls callback(items[])
                     each item: { label, sublabel, onSelect() }
         onClose:    optional function()
       }
    ─────────────────────────────────────────────────────────── */
    window.openSearchSheet = function (opts) {
        lockBodyScroll();

        var oldSearch = ssSheet.querySelector('.ss-sheet-search');
        var sheetSearch = oldSearch.cloneNode(true);
        oldSearch.replaceWith(sheetSearch);
        var sheetList = ssSheet.querySelector('.ss-sheet-list');
        sheetSearch.value = '';
        sheetSearch.placeholder = opts.placeholder || 'Buscar…';
        sheetList.innerHTML = '';
        ssSheet.querySelector('.ss-sheet-title').textContent = opts.title || 'Buscar';
        ssSheet.style.bottom = '0';
        ssSheet.style.maxHeight = '';

        var loadingMsg = document.createElement('li');
        loadingMsg.className = 'ss-sheet-empty ss-sheet-hidden';
        loadingMsg.textContent = 'Buscando…';
        var emptyMsg = document.createElement('li');
        emptyMsg.className = 'ss-sheet-empty ss-sheet-hidden';
        emptyMsg.textContent = 'Sin resultados';
        sheetList.appendChild(loadingMsg);
        sheetList.appendChild(emptyMsg);

        var debounce;
        sheetSearch.addEventListener('input', function () {
            var q = this.value.trim();
            clearTimeout(debounce);
            sheetList.querySelectorAll('.ss-sheet-dyn-item').forEach(function (el) { el.remove(); });
            if (!q) {
                loadingMsg.classList.add('ss-sheet-hidden');
                emptyMsg.classList.add('ss-sheet-hidden');
                return;
            }
            loadingMsg.classList.remove('ss-sheet-hidden');
            emptyMsg.classList.add('ss-sheet-hidden');
            debounce = setTimeout(function () {
                opts.fetchFn(q, function (items) {
                    loadingMsg.classList.add('ss-sheet-hidden');
                    sheetList.querySelectorAll('.ss-sheet-dyn-item').forEach(function (el) { el.remove(); });
                    if (!items.length) { emptyMsg.classList.remove('ss-sheet-hidden'); return; }
                    items.forEach(function (item) {
                        var li = document.createElement('li');
                        li.className = 'ss-sheet-option ss-sheet-dyn-item';
                        li.innerHTML =
                            (item.img ? '<img src="' + item.img + '" class="ss-sheet-dyn-img" alt="">' :
                                        '<div class="ss-sheet-dyn-img ss-sheet-dyn-img--placeholder">🪙</div>') +
                            '<span class="ss-sheet-dyn-info">' +
                                '<span class="ss-sheet-dyn-label">' + item.label + '</span>' +
                                (item.sublabel ? '<span class="ss-sheet-dyn-sub">' + item.sublabel + '</span>' : '') +
                            '</span>';
                        li.addEventListener('click', function () {
                            closeSheet();
                            item.onSelect();
                        });
                        sheetList.insertBefore(li, emptyMsg);
                    });
                });
            }, 220);
        });

        ssBackdrop.classList.add('ss-active');
        requestAnimationFrame(function () { ssSheet.classList.add('ss-active'); });
    };
})();
