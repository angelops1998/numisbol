/* Lightbox con zoom: rueda, pinch, arrastre, botones y teclado.
   Compartido por monedas (colección, mercado, pública) y galería del blog.

   El transform es `translate(ox,oy) scale(s)` con transform-origin centrado,
   así que todos los cálculos son relativos al centro del marco. */
(function () {
    'use strict';

    var MIN = 1;        // 1 = imagen ajustada al marco
    var MAX_MIN = 4;    // zoom máximo mínimo garantizado
    var MAX_CAP = 10;   // tope absoluto

    function byId(id) { return id ? document.getElementById(id) : null; }

    function initLightboxZoom(cfg) {
        var lb   = byId(cfg.lb);
        var wrap = byId(cfg.wrap);
        var img  = byId(cfg.img);
        if (!lb || !wrap || !img) return null;

        var label    = byId(cfg.label);
        var caption  = byId(cfg.caption);
        var btnClose = byId(cfg.close);
        var btnPrev  = byId(cfg.prev);
        var btnNext  = byId(cfg.next);
        var triggers = cfg.triggers
            ? Array.prototype.slice.call(document.querySelectorAll(cfg.triggers))
            : [];

        var sources = triggers.map(function (el) {
            var inner = el.querySelector('img');
            return el.dataset.src || (inner ? (inner.dataset.full || inner.currentSrc || inner.src) : '');
        }).filter(Boolean);
        if (!sources.length) return null;

        /* Pie de foto: data-caption del disparador o el texto de cfg.captionFrom */
        function captionOf(trigger) {
            if (!trigger) return '';
            if (trigger.dataset.caption) return trigger.dataset.caption;
            var el = cfg.captionFrom ? trigger.querySelector(cfg.captionFrom) : null;
            return el ? el.textContent.trim() : '';
        }

        var cur = 0, scale = MIN, ox = 0, oy = 0;
        var pts = new Map();   // pointerId -> {x, y}
        var pan = null;        // arrastre con un puntero
        var pinch = null;      // estado inicial del gesto de dos dedos
        var didPan = false;    // hubo movimiento real: el click no debe hacer zoom

        /* Hasta el tamaño real de la foto, con un mínimo útil */
        function maxScale() {
            var disp = img.offsetWidth, nat = img.naturalWidth;
            if (!disp || !nat) return MAX_MIN;
            return Math.min(MAX_CAP, Math.max(MAX_MIN, nat / disp));
        }

        /* Límite de arrastre: la imagen escalada no deja huecos dentro del marco.
           offsetWidth/Height = tamaño ya ajustado por CSS, sin contar el transform. */
        function clampOffset(s, x, y) {
            var maxX = Math.max(0, (img.offsetWidth  * s - wrap.clientWidth)  / 2);
            var maxY = Math.max(0, (img.offsetHeight * s - wrap.clientHeight) / 2);
            return {
                x: Math.min(maxX, Math.max(-maxX, x)),
                y: Math.min(maxY, Math.max(-maxY, y))
            };
        }

        function apply(s, x, y) {
            scale = Math.min(maxScale(), Math.max(MIN, s));
            var c = clampOffset(scale, x, y);
            ox = c.x; oy = c.y;
            img.style.transform = 'translate(' + ox + 'px,' + oy + 'px) scale(' + scale + ')';
            if (label) label.textContent = Math.round(scale * 100) + '%';
            wrap.classList.toggle('lb-zoomed', scale > MIN);
        }

        function reset() { apply(MIN, 0, 0); }

        /* Zoom anclado: el punto (cx,cy) de la pantalla se queda donde está */
        function zoomAt(s, cx, cy) {
            var target = Math.min(maxScale(), Math.max(MIN, s));
            if (target === scale) return;
            var r  = wrap.getBoundingClientRect();
            var dx = cx - (r.left + r.width  / 2) - ox;   // distancia al centro de la imagen
            var dy = cy - (r.top  + r.height / 2) - oy;
            var k  = target / scale - 1;
            apply(target, ox - dx * k, oy - dy * k);
        }

        function zoomBy(f) {
            var r = wrap.getBoundingClientRect();
            zoomAt(scale * f, r.left + r.width / 2, r.top + r.height / 2);
        }

        /* ── Abrir / cerrar / navegar ────────────────────────── */
        function show(i) {
            cur = (i + sources.length) % sources.length;
            reset();
            img.src = sources[cur];
            var trigger = triggers[cur];
            var inner = trigger && trigger.querySelector('img');
            img.alt = inner ? inner.alt : '';
            if (caption) caption.textContent = captionOf(trigger);
            lb.classList.add('lb-open');
            document.body.style.overflow = 'hidden';
            var multi = sources.length > 1;
            if (btnPrev) btnPrev.style.display = multi ? '' : 'none';
            if (btnNext) btnNext.style.display = multi ? '' : 'none';
            if (cfg.onOpen) cfg.onOpen(cur);
        }

        function close() {
            lb.classList.remove('lb-open');
            document.body.style.overflow = '';
            pts.clear(); pan = null; pinch = null;
            reset();
            if (cfg.onClose) cfg.onClose(cur);
        }

        /* Al cargar la nueva imagen ya se conoce su tamaño: recalcular límites */
        img.addEventListener('load', reset);

        triggers.forEach(function (el, i) {
            el.style.cursor = 'zoom-in';
            el.addEventListener('click', function () { show(i); });
        });

        if (btnClose) btnClose.addEventListener('click', function (e) { e.stopPropagation(); close(); });
        if (btnPrev)  btnPrev.addEventListener('click',  function (e) { e.stopPropagation(); show(cur - 1); });
        if (btnNext)  btnNext.addEventListener('click',  function (e) { e.stopPropagation(); show(cur + 1); });

        [[cfg.zoomIn, 1.5], [cfg.zoomOut, 1 / 1.5]].forEach(function (pair) {
            var b = byId(pair[0]);
            if (b) b.addEventListener('click', function (e) { e.stopPropagation(); zoomBy(pair[1]); });
        });
        var btnReset = byId(cfg.zoomReset);
        if (btnReset) btnReset.addEventListener('click', function (e) { e.stopPropagation(); reset(); });

        lb.addEventListener('click', function (e) { if (e.target === lb) close(); });

        /* Con captura de puntero el click llega al marco y no a la imagen,
           así que se decide por geometría y no por e.target. */
        function overImage(cx, cy) {
            var r = img.getBoundingClientRect();
            return cx >= r.left && cx <= r.right && cy >= r.top && cy <= r.bottom;
        }

        /* Click en la imagen: alterna zoom en el punto pulsado.
           Click en el hueco del marco: cierra. */
        wrap.addEventListener('click', function (e) {
            var panned = didPan;
            didPan = false;
            if (panned) return;              // fue un arrastre, no un click
            if (!img.naturalWidth) return;   // aún cargando: no cerrar por error
            if (overImage(e.clientX, e.clientY)) {
                if (scale > MIN) reset();
                else zoomAt(2.5, e.clientX, e.clientY);
            } else {
                close();
            }
        });

        /* ── Rueda ───────────────────────────────────────────── */
        wrap.addEventListener('wheel', function (e) {
            e.preventDefault();
            var unit = e.deltaMode === 1 ? 16 : (e.deltaMode === 2 ? wrap.clientHeight : 1);
            zoomAt(scale * Math.exp(-e.deltaY * unit * 0.002), e.clientX, e.clientY);
        }, { passive: false });

        /* ── Arrastre y pinch (pointer events: ratón, dedo y lápiz) ── */
        function startPan(p) { pan = { x: p.x, y: p.y, ox: ox, oy: oy }; }

        function startPinch() {
            var a = Array.from(pts.values());
            var r = wrap.getBoundingClientRect();
            pinch = {
                dist: Math.hypot(a[1].x - a[0].x, a[1].y - a[0].y) || 1,
                mx: (a[0].x + a[1].x) / 2,
                my: (a[0].y + a[1].y) / 2,
                scale: scale, ox: ox, oy: oy,
                cx: r.left + r.width  / 2,
                cy: r.top  + r.height / 2
            };
            pan = null;
        }

        wrap.addEventListener('pointerdown', function (e) {
            if (e.pointerType === 'mouse' && e.button !== 0) return;
            didPan = false;
            pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
            if (pts.size === 2) startPinch();
            else if (pts.size === 1 && scale > MIN) { e.preventDefault(); startPan({ x: e.clientX, y: e.clientY }); }
            // Capturar solo durante arrastre/pinch: el puntero puede salir del marco
            if (pan || pinch) { try { wrap.setPointerCapture(e.pointerId); } catch (err) { /* sin captura */ } }
        });

        wrap.addEventListener('pointermove', function (e) {
            if (!pts.has(e.pointerId)) return;
            pts.set(e.pointerId, { x: e.clientX, y: e.clientY });

            if (pts.size >= 2 && pinch) {
                var a  = Array.from(pts.values());
                var d  = Math.hypot(a[1].x - a[0].x, a[1].y - a[0].y);
                var mx = (a[0].x + a[1].x) / 2;
                var my = (a[0].y + a[1].y) / 2;
                var ns = Math.min(maxScale(), Math.max(MIN, pinch.scale * d / pinch.dist));
                // punto de la imagen que estaba bajo los dedos al empezar el gesto
                var ix = (pinch.mx - pinch.cx - pinch.ox) / pinch.scale;
                var iy = (pinch.my - pinch.cy - pinch.oy) / pinch.scale;
                didPan = true;
                apply(ns, mx - pinch.cx - ix * ns, my - pinch.cy - iy * ns);
            } else if (pan && pts.size === 1) {
                if (Math.abs(e.clientX - pan.x) + Math.abs(e.clientY - pan.y) > 4) didPan = true;
                apply(scale, pan.ox + e.clientX - pan.x, pan.oy + e.clientY - pan.y);
            }
        });

        function endPointer(e) {
            pts.delete(e.pointerId);
            if (pts.size < 2) pinch = null;
            if (pts.size === 1 && scale > MIN) startPan(Array.from(pts.values())[0]);
            else if (pts.size === 0) pan = null;
        }
        wrap.addEventListener('pointerup', endPointer);
        wrap.addEventListener('pointercancel', endPointer);

        /* ── Teclado ─────────────────────────────────────────── */
        document.addEventListener('keydown', function (e) {
            if (!lb.classList.contains('lb-open')) return;
            var step = 60;
            switch (e.key) {
                case 'Escape': close(); break;
                case 'ArrowLeft':  if (scale > MIN) apply(scale, ox + step, oy); else show(cur - 1); break;
                case 'ArrowRight': if (scale > MIN) apply(scale, ox - step, oy); else show(cur + 1); break;
                case 'ArrowUp':    if (scale > MIN) { e.preventDefault(); apply(scale, ox, oy + step); } break;
                case 'ArrowDown':  if (scale > MIN) { e.preventDefault(); apply(scale, ox, oy - step); } break;
                case '+': case '=': zoomBy(1.3); break;
                case '-': case '_': zoomBy(1 / 1.3); break;
                case '0': reset(); break;
            }
        });

        /* Al cambiar el tamaño de la ventana el marco cambia: re-ajustar */
        window.addEventListener('resize', function () {
            if (lb.classList.contains('lb-open')) apply(scale, ox, oy);
        });

        return { open: show, close: close, reset: reset };
    }

    window.initLightboxZoom = initLightboxZoom;
})();
