/* Admin de series: lista (/admin/series) y detalle (/admin/series/{id}).
   Todo es mejora progresiva: sin JS los formularios siguen funcionando con
   recarga de página. */
(function () {
    'use strict';

    function norm(s) { return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
    function $(sel, root) { return (root || document).querySelector(sel); }
    function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

    /* POST de un form sin recargar. El backend responde JSON si ve X-Fetch. */
    function enviar(form) {
        return fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Fetch': '1' },
            credentials: 'same-origin',
        }).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (data) {
                if (!r.ok || data.ok === false) throw new Error(data.error || 'No se pudo guardar');
                return data;
            });
        });
    }

    /* ── Comunes ──────────────────────────────────────────── */

    // Botones que muestran/ocultan uno o más elementos: data-toggle="#a,#b"
    $$('[data-toggle]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            $$(btn.dataset.toggle).forEach(function (el) {
                el.hidden = !el.hidden;
                if (!el.hidden) {
                    var campo = el.querySelector('input:not([type=hidden]), textarea');
                    if (campo) campo.focus();
                    $$('.sx-autogrow', el).forEach(crecer);
                }
            });
        });
    });

    // Textareas que crecen con el contenido
    function crecer(ta) {
        ta.style.height = 'auto';
        ta.style.height = (ta.scrollHeight + 2) + 'px';
    }
    $$('.sx-autogrow').forEach(function (ta) {
        crecer(ta);
        ta.addEventListener('input', function () { crecer(ta); });
    });

    // Los avisos de "guardado" se van solos
    $$('.sx-flash.alert-success').forEach(function (el) {
        setTimeout(function () { el.classList.add('is-saliendo'); }, 2500);
        setTimeout(function () { el.remove(); }, 3000);
    });
    // Sacar ?saved=1 de la URL para que recargar no repita el aviso
    if (/[?&](saved|last|open)=/.test(location.search)) {
        history.replaceState(null, '', location.pathname + location.hash);
    }

    // Filtro de texto genérico sobre filas con data-buscar
    function filtrar(input, filas, vacio, extra) {
        var q = norm(input ? input.value.trim() : '');
        var visibles = 0;
        filas.forEach(function (tr) {
            var ok = (!q || norm(tr.dataset.buscar).indexOf(q) !== -1) && (!extra || extra(tr));
            tr.hidden = !ok;
            if (ok) visibles++;
        });
        if (vacio) vacio.hidden = visibles > 0;
        return visibles;
    }

    // "/" enfoca el buscador (como en GitHub/Gmail)
    function atajoBuscar(input) {
        if (!input) return;
        document.addEventListener('keydown', function (e) {
            var t = e.target.tagName;
            if (e.key === '/' && t !== 'INPUT' && t !== 'TEXTAREA' && t !== 'SELECT') {
                e.preventDefault();
                input.focus();
            }
        });
    }

    /* ── Lista de series ──────────────────────────────────── */

    var tabla = $('#sx-tabla');
    if (tabla) {
        var buscar = $('#sx-buscar');
        var filas = $$('tbody tr', tabla);
        var vacio = $('#sx-sin-resultados');
        var filtro = '';
        var reglas = {
            '':              function () { return true; },
            'sin-variantes': function (tr) { return tr.dataset.variantes === '0'; },
            'sin-precios':   function (tr) { return tr.dataset.precios === '0'; },
            'ocultas':       function (tr) { return tr.dataset.activo === '0'; },
        };
        function aplicar() { filtrar(buscar, filas, vacio, reglas[filtro]); }
        buscar.addEventListener('input', aplicar);
        buscar.addEventListener('keydown', function (e) {
            // Enter con un solo resultado abre la serie
            if (e.key === 'Enter') {
                var vis = filas.filter(function (tr) { return !tr.hidden; });
                if (vis.length === 1) location.href = vis[0].dataset.href;
            }
            if (e.key === 'Escape') { buscar.value = ''; aplicar(); }
        });
        $$('.sx-chip').forEach(function (chip) {
            chip.addEventListener('click', function () {
                $$('.sx-chip').forEach(function (c) { c.classList.toggle('is-on', c === chip); });
                filtro = chip.dataset.filtro;
                aplicar();
            });
        });
        atajoBuscar(buscar);

        // Toda la fila es clickeable (salvo el campo de orden y los botones)
        filas.forEach(function (tr) {
            tr.addEventListener('click', function (e) {
                if (e.target.closest('a, button, input, form')) return;
                if (window.getSelection().toString()) return;   // está seleccionando texto
                location.href = tr.dataset.href;
            });
        });

        // El orden se guarda solo al cambiarlo
        $$('.sx-orden-form').forEach(function (form) {
            var input = form.querySelector('.sx-orden');
            var original = input.value;
            form.addEventListener('submit', function (e) { e.preventDefault(); input.blur(); });
            input.addEventListener('change', function () {
                if (input.value === original || input.value === '') return;
                input.classList.remove('is-ok', 'is-error');
                enviar(form).then(function () {
                    original = input.value;
                    input.classList.add('is-ok');
                    setTimeout(function () { input.classList.remove('is-ok'); }, 1500);
                }).catch(function () { input.classList.add('is-error'); });
            });
        });
    }

    /* ── Detalle de una serie ─────────────────────────────── */

    var forms = $$('.sd-vform');
    var barra = $('#sd-barra');

    // Descripción larga: plegada con "ver más"
    var desc = $('#sd-desc'), mas = $('#sd-mas');
    if (desc && mas && desc.scrollHeight > desc.clientHeight + 4) {
        mas.hidden = false;
        mas.addEventListener('click', function () {
            var plegada = desc.classList.toggle('is-plegada');
            mas.textContent = plegada ? 'Ver descripción completa ▾' : 'Mostrar menos ▴';
        });
    } else if (desc) {
        desc.classList.remove('is-plegada');
    }

    // Filtro de variantes
    var sdBuscar = $('#sd-buscar');
    if (sdBuscar) {
        var vfilas = $$('.sd-fila');
        sdBuscar.addEventListener('input', function () {
            filtrar(sdBuscar, vfilas, $('#sd-sin-resultados'));
            // La fila de precios sigue a su variante
            vfilas.forEach(function (tr) {
                var p = document.getElementById('vp-' + tr.dataset.vid);
                if (p && tr.hidden) p.hidden = true;
            });
        });
        sdBuscar.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') { sdBuscar.value = ''; sdBuscar.dispatchEvent(new Event('input')); }
        });
        atajoBuscar(sdBuscar);
    }

    // Mostrar / ocultar los precios de una variante
    $$('[data-toggle-precios]').forEach(function (btn) {
        var fila = document.getElementById('vp-' + btn.dataset.togglePrecios);
        btn.setAttribute('aria-expanded', String(!fila.hidden));
        btn.addEventListener('click', function () {
            fila.hidden = !fila.hidden;
            btn.setAttribute('aria-expanded', String(!fila.hidden));
            if (!fila.hidden) fila.querySelector('input[name=monto]').focus();
        });
    });

    // Al pegar un enlace se completa la fuente
    var DOMINIOS = [
        [/ebay\./, 'eBay'], [/mercadolibre\.|mercadolivre\./, 'MercadoLibre'],
        [/facebook\.com\/marketplace|fb\.com\/marketplace/, 'Facebook Marketplace'],
        [/facebook\.|fb\.com/, 'Grupo de Facebook'], [/wa\.me|whatsapp/, 'WhatsApp'],
        [/numista\./, 'Numista'], [/ha\.com|heritage/, 'Heritage Auctions'],
        [/sixbid|numisbids|acsearch|catawiki|delcampe|vcoins|ma-shops/, null],
    ];
    // Precio en Bs: mostrar el tipo de cambio que se va a usar
    $$('.pz-moneda').forEach(function (sel) {
        var tasa = sel.form.querySelector('.pz-tasa');
        if (!tasa) return;
        sel.addEventListener('change', function () { tasa.hidden = sel.value !== 'BOB'; });
    });

    $$('.pz-url').forEach(function (url) {
        url.addEventListener('change', function () {
            var fuente = url.form.querySelector('.pz-fuente');
            if (!fuente || fuente.value) return;
            var host = '';
            try { host = new URL(url.value).hostname.replace(/^www\./, ''); } catch (e) { return; }
            for (var i = 0; i < DOMINIOS.length; i++) {
                if (DOMINIOS[i][0].test(url.value)) {
                    fuente.value = DOMINIOS[i][1] || host.split('.')[0].replace(/^./, function (c) { return c.toUpperCase(); });
                    return;
                }
            }
            fuente.value = host;
        });
    });

    // Variantes: se marca la fila al editarla y se guarda sin recargar
    var sucias = {};
    function actualizarBarra() {
        var n = Object.keys(sucias).length;
        if (!barra) return;
        barra.hidden = n === 0;
        $('#sd-barra-texto').textContent = n === 1 ? '1 variante sin guardar' : n + ' variantes sin guardar';
    }
    function fila(vid) { return document.getElementById('v-' + vid); }
    function campos(form) { return $$('[form="' + form.id + '"]').filter(function (el) { return el.name; }); }
    function valores(form) { return campos(form).map(function (el) { return el.value; }).join('\u0001'); }
    var guardado = {};   // vid → valores tal como están en la base

    // Una fila está "sucia" si difiere de lo guardado (si se deshace el
    // cambio, deja de estarlo)
    function revisar(form) {
        var vid = form.dataset.vid, tr = fila(vid);
        var sucia = valores(form) !== guardado[vid];
        if (sucia) sucias[vid] = true; else delete sucias[vid];
        tr.classList.toggle('is-sucia', sucia);
        if (sucia) {
            tr.classList.remove('is-guardada');
            tr.querySelector('.sd-estado').textContent = '';
        }
        tr.querySelector('.sd-guardar').disabled = !sucia;
        actualizarBarra();
    }
    function guardar(form) {
        var vid = form.dataset.vid, tr = fila(vid);
        var btn = tr.querySelector('.sd-guardar'), estado = tr.querySelector('.sd-estado');
        var enviados = valores(form);
        btn.disabled = true;
        estado.textContent = 'Guardando…';
        return enviar(form).then(function () {
            guardado[vid] = enviados;
            delete sucias[vid];
            tr.classList.remove('is-sucia');
            tr.classList.add('is-guardada');
            estado.textContent = '✓';
            tr.dataset.buscar = campos(form).map(function (el) {
                return el.name === 'mintage' ? '' : el.value;
            }).join(' ');
            revisar(form);   // por si se siguió escribiendo mientras se guardaba
            setTimeout(function () {
                tr.classList.remove('is-guardada');
                if (estado.textContent === '✓') estado.textContent = '';
            }, 2000);
        }).catch(function (err) {
            btn.disabled = false;
            estado.textContent = '⚠ ' + err.message;
        }).then(actualizarBarra);
    }

    forms.forEach(function (form) {
        guardado[form.dataset.vid] = valores(form);
        campos(form).forEach(function (el) {
            el.addEventListener('input', function () { revisar(form); });
            el.addEventListener('change', function () { revisar(form); });
            // Ctrl+Enter en la nota guarda la fila
            el.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); guardar(form); }
            });
        });
        form.addEventListener('submit', function (e) { e.preventDefault(); guardar(form); });
    });

    function guardarTodo() {
        Object.keys(sucias).forEach(function (vid) { guardar(document.getElementById('edit-v-' + vid)); });
    }
    if (barra) $('#sd-guardar-todo').addEventListener('click', guardarTodo);

    document.addEventListener('keydown', function (e) {
        if (forms.length && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
            e.preventDefault();
            guardarTodo();
        }
        // Alt+← / Alt+→ cambia de serie (si no hay nada sin guardar)
        if (e.altKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
            var t = e.target.tagName;
            if (t === 'INPUT' || t === 'TEXTAREA') return;
            var link = $$('.sd-flechas a').filter(function (a) {
                return a.textContent.indexOf(e.key === 'ArrowLeft' ? 'Anterior' : 'Siguiente') !== -1;
            })[0];
            if (link) { e.preventDefault(); link.click(); }
        }
    });

    // Avisar antes de irse con cambios sin guardar. Los formularios que
    // recargan la página (agregar variante, precio…) preguntan ellos mismos.
    var enviando = false;
    $$('form').forEach(function (f) {
        if (f.classList.contains('sd-vform')) return;
        f.addEventListener('submit', function (e) {
            if (e.defaultPrevented) return;   // el usuario canceló un confirm()
            var n = Object.keys(sucias).length;
            if (n && !confirm(n + (n === 1 ? ' variante tiene' : ' variantes tienen') +
                              ' cambios sin guardar que se van a perder. ¿Seguir igual?')) {
                e.preventDefault();
                return;
            }
            enviando = true;
        });
    });
    window.addEventListener('beforeunload', function (e) {
        if (!enviando && Object.keys(sucias).length) { e.preventDefault(); e.returnValue = ''; }
    });

    // Volver a donde estaba tras recargar (#v-123, #nueva-variante, #precios).
    // El navegador lo intenta solo, pero el aviso de "guardado" que aparece
    // arriba lo corre; mejor centrarlo a mano.
    var ancla = location.hash && document.getElementById(location.hash.slice(1));
    if (ancla) {
        setTimeout(function () {
            ancla.scrollIntoView({ block: ancla.tagName === 'TR' ? 'start' : 'center', behavior: 'instant' });
            // Seguir cargando: foco en el año de la nueva variante o en el
            // monto del panel de precios que quedó abierto
            var foco = null;
            if (ancla.id === 'nueva-variante') {
                foco = ancla.querySelector('input[name=anio]');
            } else if (ancla.dataset.vid) {
                var panel = document.getElementById('vp-' + ancla.dataset.vid);
                if (panel && !panel.hidden) foco = panel.querySelector('input[name=monto]');
            }
            if (foco) foco.focus({ preventScroll: true });
        }, 0);
    }

    // Resaltar la variante recién agregada / la que se acaba de tocar
    var nueva = $('.sd-fila.is-nueva');
    if (nueva) setTimeout(function () { nueva.classList.remove('is-nueva'); }, 2500);
})();
