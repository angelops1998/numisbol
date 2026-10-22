/* Me gusta de las piezas públicas.
   Funciona sobre cualquier elemento con data-like="<url del toggle>".
   El control vive dentro del <a> de la tarjeta, así que cancelamos la
   navegación y mandamos el POST por fetch. */
(function () {
    function csrfToken() {
        var input = document.querySelector('input[name="csrf_token"]');
        return input ? input.value : '';
    }

    function pintar(el, liked, total) {
        el.classList.toggle('coin-like--on', liked);
        el.setAttribute('aria-pressed', liked ? 'true' : 'false');
        el.setAttribute('title', liked ? 'Ya no me gusta' : 'Me gusta');
        var cuenta = el.querySelector('.coin-like-count');
        if (cuenta) {
            cuenta.textContent = total;
            cuenta.classList.toggle('coin-like-count--zero', !total);
        }
        if (liked) {
            el.classList.remove('coin-like--pop');
            void el.offsetWidth;            // reinicia la animación
            el.classList.add('coin-like--pop');
        }
    }

    function toggle(el) {
        if (el.dataset.busy) return;
        el.dataset.busy = '1';

        fetch(el.dataset.like, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'csrf_token=' + encodeURIComponent(csrfToken()),
            credentials: 'same-origin',
        })
            .then(function (res) {
                if (res.status === 401) {
                    return res.json().catch(function () { return {}; }).then(function (data) {
                        window.location.href = data.login_url || '/auth/login';
                        return null;
                    });
                }
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(function (data) {
                if (data) pintar(el, data.liked, data.likes);
            })
            .catch(function () {
                el.classList.add('coin-like--error');
                setTimeout(function () { el.classList.remove('coin-like--error'); }, 1400);
            })
            .finally(function () { delete el.dataset.busy; });
    }

    function desde(target) {
        return target && target.closest ? target.closest('[data-like]') : null;
    }

    document.addEventListener('click', function (e) {
        var el = desde(e.target);
        if (!el) return;
        e.preventDefault();
        e.stopPropagation();
        toggle(el);
    });

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        var el = desde(e.target);
        if (!el) return;
        e.preventDefault();
        e.stopPropagation();
        toggle(el);
    });
})();
