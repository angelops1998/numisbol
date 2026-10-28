// Inicio "Casa de Moneda": prensa, cinta, contadores, capítulos, pila de
// tarjetas y vitrina giratoria. Todo vive dentro de #cm.
(() => {
  const cm = document.getElementById('cm');
  if (!cm) return;
  const motion = !matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fine = matchMedia('(hover: hover) and (pointer: fine)').matches;
  const $ = s => cm.querySelector(s), $$ = s => [...cm.querySelectorAll(s)];
  const IMG = name => cm.dataset['img-' + name] || cm.getAttribute('data-img-' + name);

  /* Brillo que sigue al cursor en paneles */
  $$('.glow').forEach(el => el.addEventListener('pointermove', e => {
    const b = el.getBoundingClientRect();
    el.style.setProperty('--mx', (e.clientX - b.left) + 'px');
    el.style.setProperty('--my', (e.clientY - b.top) + 'px');
  }));

  /* Botones magnéticos */
  if (fine && motion) $$('.magnet').forEach(el => {
    el.addEventListener('pointermove', e => {
      const b = el.getBoundingClientRect();
      const x = (e.clientX - b.left - b.width / 2) * 0.22, y = (e.clientY - b.top - b.height / 2) * 0.35;
      el.style.transition = 'transform 120ms linear'; el.style.transform = `translate(${x}px, ${y}px)`;
    });
    el.addEventListener('pointerleave', () => { el.style.transition = ''; el.style.transform = ''; });
  });

  /* ── Prensa: acuñación ─────────────────────── */
  const COINS = [
    { img: 'sol_a', alt: '8 Soles 1841, anverso con el busto de Bolívar', den: '8 Soles', year: '1841', mint: 'Potosí', note: '1.396.550 piezas' },
    { img: 'cuartillo_a', alt: '1/4 Sol 1852, anverso con el Cerro Rico', den: '1/4 Sol', year: '1852', mint: 'Potosí', note: 'Tipo llamita · Rara' },
    { img: 'cincuenta', alt: 'Cincuenta centavos 1980', den: '50 Centavos', year: '1980', mint: '—', note: 'Circulación' },
    { img: 'peso1980', alt: 'Un peso boliviano 1980', den: '1 Peso boliviano', year: '1980', mint: '—', note: 'Circulación' }
  ];
  const die = $('#die'), blank = $('#blank'), img = $('#coinImg'), flash = $('#flash'), ring = $('#ring');
  const wrap = $('#coinwrap'), coin3d = $('#coin3d'), stage = $('#stage'), dots = $$('#dots i');
  let idx = 0, busy = false, autoTimer = null, pressVisible = true;

  function scramble(el, text) {
    if (!motion) { el.textContent = text; return; }
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789·';
    let f = 0; const total = 14;
    const tick = () => {
      f++;
      el.textContent = text.split('').map((c, i) => c === ' ' || i < (f / total) * text.length ? c : chars[(Math.random() * chars.length) | 0]).join('');
      if (f < total) requestAnimationFrame(tick); else el.textContent = text;
    };
    tick();
  }
  function setDots() {
    dots.forEach((d, i) => { d.classList.toggle('done', i < idx); d.classList.remove('on'); });
    void dots[idx].offsetWidth; dots[idx].classList.add('on');
  }
  function sparks() {
    for (let i = 0; i < 10; i++) {
      const s = document.createElement('span'); s.className = 'spark';
      stage.appendChild(s);
      const a = (Math.PI * 2 * i) / 10 + Math.random() * .4, d = 120 + Math.random() * 70;
      s.animate([
        { opacity: 1, transform: 'translate(-50%,-50%) scale(1)' },
        { opacity: 0, transform: `translate(calc(-50% + ${Math.cos(a) * d}px), calc(-50% + ${Math.sin(a) * d * .6 + 20}px)) scale(.4)` }
      ], { duration: 650 + Math.random() * 250, easing: 'cubic-bezier(0.23, 1, 0.32, 1)' }).onfinish = () => s.remove();
    }
  }
  async function strike(next) {
    if (busy) return; busy = true;
    const c = COINS[next];
    wrap.classList.remove('idle');
    if (!motion) { img.src = IMG(c.img); img.alt = c.alt; finish(next, c); return; }
    const E = 'cubic-bezier(0.23, 1, 0.32, 1)';
    // la pieza anterior sale, entra el cospel liso
    await img.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateX(60px) rotate(25deg) scale(.9)' }], { duration: 320, easing: 'cubic-bezier(0.55, 0, 1, 0.45)', fill: 'forwards' }).finished;
    img.src = IMG(c.img); img.alt = c.alt;
    blank.style.opacity = 1;
    await blank.animate([{ opacity: 0, transform: 'translateX(-70px) scale(.92)' }, { opacity: 1, transform: 'none' }], { duration: 420, easing: E }).finished;
    // baja el cuño
    const fall = { duration: 230, easing: 'cubic-bezier(0.55, 0, 1, 0.45)', fill: 'forwards' };
    const dieH = die.offsetHeight, target = stage.offsetHeight / 2 - wrap.offsetHeight / 2;
    await die.animate([{ translate: '-50% -82%' }, { translate: `-50% ${target - dieH}px` }], fall).finished;
    // impacto
    stage.animate([{ transform: 'translate(0,0)' }, { transform: 'translate(2px,3px)' }, { transform: 'translate(-2px,-1px)' }, { transform: 'translate(0,0)' }], { duration: 160 });
    coin3d.animate([{ transform: 'scale(1.04, .96)' }, { transform: 'none' }], { duration: 260, easing: E });
    flash.animate([{ opacity: .9 }, { opacity: 0 }], { duration: 420, easing: E });
    ring.animate([{ opacity: .8, transform: 'scale(.9)' }, { opacity: 0, transform: 'scale(1.7)' }], { duration: 750, easing: E });
    sparks();
    img.getAnimations().forEach(a => a.cancel());
    img.animate([{ opacity: 0, filter: 'brightness(1.8) contrast(.6)' }, { opacity: 1, filter: 'none' }], { duration: 380, easing: E });
    blank.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 300, easing: E }).onfinish = () => { blank.style.opacity = 0; };
    // sube el cuño
    die.animate([{ translate: `-50% ${target - dieH}px` }, { translate: '-50% -82%' }], { duration: 650, easing: E, fill: 'forwards', delay: 90 });
    finish(next, c);
  }
  function finish(next, c) {
    idx = next;
    $('#pressCount').textContent = `Pieza ${idx + 1} de ${COINS.length}`;
    $$('.readout dd').forEach((dd, i) => setTimeout(() => scramble(dd, c[dd.dataset.k]), i * 70));
    setDots();
    setTimeout(() => { wrap.classList.add('idle'); busy = false; }, 700);
    schedule();
  }
  function schedule() {
    clearTimeout(autoTimer);
    if (motion) autoTimer = setTimeout(() => {
      if (pressVisible && document.visibilityState === 'visible') strike((idx + 1) % COINS.length); else schedule();
    }, 6000);
  }
  if (stage) {
    $('#strike').addEventListener('click', () => strike((idx + 1) % COINS.length));
    new IntersectionObserver(([e]) => { pressVisible = e.isIntersecting; }).observe($('#press'));
    setDots();
    if (cm.classList.contains('anim')) setTimeout(() => strike(0), 900); else schedule();

    // inclinación con el cursor
    $('#press').addEventListener('pointermove', e => {
      if (!fine || !motion) return;
      const b = wrap.getBoundingClientRect();
      const px = (e.clientX - b.left) / b.width, py = (e.clientY - b.top) / b.height;
      coin3d.style.setProperty('--rx', ((0.5 - py) * 16).toFixed(1) + 'deg');
      coin3d.style.setProperty('--ry', ((px - 0.5) * 16).toFixed(1) + 'deg');
      coin3d.style.setProperty('--gx', (px * 100).toFixed(0) + '%');
      coin3d.style.setProperty('--gy', (py * 100).toFixed(0) + '%');
    });
    $('#press').addEventListener('pointerleave', () => { coin3d.style.setProperty('--rx', '0deg'); coin3d.style.setProperty('--ry', '0deg'); });
  }

  /* ── Cinta de leyendas ─────────────────────── */
  const LEG = ['Libre por la Constitución', 'sol_a', 'República Boliviana', 'cuartillo_a', 'Potosí 1852', 'cincuenta', 'Un peso boliviano', 'peso1980', 'Casa de Moneda'];
  const half = LEG.map(x => IMG(x) ? `<img src="${IMG(x)}" alt="" width="38" height="38">` : `<span>${x}</span>`).join('');
  $('#ticker').innerHTML = half + half;

  /* ── Revelado al hacer scroll ─────────────────────── */
  const reveals = $$('.reveal');
  reveals.forEach(el => { if (el.getBoundingClientRect().top > innerHeight * 0.92 && motion) el.classList.add('pending'); });
  const io = new IntersectionObserver(entries => entries.forEach(e => {
    if (!e.isIntersecting) return;
    e.target.classList.remove('pending'); io.unobserve(e.target);
  }), { rootMargin: '0px 0px -8% 0px' });
  reveals.forEach(el => io.observe(el));

  function whenSeen(el, fn, margin = '-15%') {
    const o = new IntersectionObserver(([e]) => { if (e.isIntersecting) { fn(); o.disconnect(); } }, { rootMargin: `0px 0px ${margin} 0px` });
    o.observe(el);
  }

  /* ── Odómetros ─────────────────────── */
  $$('.odo').forEach(el => {
    const to = el.dataset.to;
    if (!motion) return;
    el.setAttribute('aria-label', to);
    el.innerHTML = to.split('').map((d, i) => `<span class="col" aria-hidden="true" style="--d:${i * 120}ms">${'0123456789'.split('').map(n => `<span>${n}</span>`).join('')}</span>`).join('');
    whenSeen(el, () => el.querySelectorAll('.col').forEach((c, i) => { c.style.transform = `translateY(-${+to[i]}em)`; }), '-10%');
  });

  /* Conteo del valor de la colección (ejemplo) */
  $$('.countup').forEach(el => {
    if (!motion) return;
    const to = +el.dataset.to; el.textContent = '0';
    whenSeen(el, () => {
      const t0 = performance.now(), D = 1400;
      const step = t => { const p = Math.min(1, (t - t0) / D), e = 1 - Math.pow(1 - p, 4); el.textContent = Math.round(to * e).toLocaleString('es-BO'); if (p < 1) requestAnimationFrame(step); };
      requestAnimationFrame(step);
    });
  });

  /* ── Capítulos: scroll horizontal anclado ─────────────────────── */
  const etrack = $('#etrack'), rail = $('#rail'), epochsEl = $('#catalogo');
  if (etrack) {
    const ecards = [...etrack.children], rbtns = [...rail.children];
    const pinned = motion;
    const epochFx = () => {
      if (!pinned) return;
      const r = epochsEl.getBoundingClientRect(), total = epochsEl.offsetHeight - innerHeight;
      const p = Math.max(0, Math.min(1, -r.top / total));
      const maxX = etrack.scrollWidth - etrack.parentElement.clientWidth;
      etrack.style.transform = `translate3d(${(-p * maxX).toFixed(1)}px, 0, 0)`;
      rail.style.setProperty('--p', p.toFixed(4));
      const mid = innerWidth / 2;
      let best = 0, bestD = Infinity;
      ecards.forEach((c, i) => {
        const b = c.getBoundingClientRect(), d = (b.left + b.width / 2 - mid) / innerWidth, ad = Math.min(1, Math.abs(d));
        c.style.setProperty('--es', (1 - ad * 0.08).toFixed(3));
        c.style.setProperty('--eo', (1 - ad * 0.45).toFixed(3));
        c.style.setProperty('--er', (d * 50).toFixed(1) + 'deg');
        c.style.setProperty('--ex', (d * -120).toFixed(1) + 'px');
        if (Math.abs(d) < bestD) { bestD = Math.abs(d); best = i; }
      });
      rbtns.forEach((b, i) => b.classList.toggle('on', i === best));
    };
    rbtns.forEach((b, i) => b.addEventListener('click', () => {
      if (!pinned) { ecards[i].scrollIntoView({ behavior: 'smooth', inline: 'start', block: 'nearest' }); return; }
      const total = epochsEl.offsetHeight - innerHeight;
      const maxX = etrack.scrollWidth - etrack.parentElement.clientWidth;
      const p = Math.min(1, ecards[i].offsetLeft / maxX);
      scrollTo({ top: epochsEl.getBoundingClientRect().top + scrollY + p * total, behavior: 'smooth' });
    }));
    if (pinned) { addEventListener('scroll', () => requestAnimationFrame(epochFx), { passive: true }); addEventListener('resize', epochFx); epochFx(); }
  }

  /* ── Pila de tarjetas ─────────────────────── */
  const cards = $$('.card');
  function stackFx() {
    cards.forEach((c, i) => {
      const next = cards[i + 1];
      if (!next) return;
      const cb = c.getBoundingClientRect(), nb = next.getBoundingClientRect();
      const p = Math.max(0, Math.min(1, 1 - (nb.top - cb.top) / cb.height));
      c.style.setProperty('--sc', (1 - p * 0.05).toFixed(4));
      c.style.setProperty('--br', (1 - p * 0.25).toFixed(3));
    });
  }
  if (motion) { addEventListener('scroll', () => requestAnimationFrame(stackFx), { passive: true }); stackFx(); }

  /* ── Escala de rareza ─────────────────────── */
  const scale = $('#scale');
  if (scale) { if (motion) whenSeen(scale, () => scale.classList.remove('pending')); else scale.classList.remove('pending'); }

  /* ── Vitrina giratoria ─────────────────────── */
  const PIECES = [
    ['cuartillo_r', '1/4 Sol', '1852 · Potosí'], ['sol_r', '8 Soles', '1841 · Potosí'], ['bolivar_plata', 'Simón Bolívar', 'Libertador de Colombia'],
    ['republica', 'República de Bolivia', 'Cerro y llama'], ['escudo', 'Escudo nacional', 'República de Bolivia'],
    ['cincuenta', '50 Centavos', '1980'], ['peso1980', '1 Peso boliviano', '1980'], ['sol_a', '8 Soles', '1841 · anverso']
  ];
  const cring = $('#cring'), car = $('#carousel'), cap = $('#ccap');
  if (car) {
    const N = PIECES.length, step = 360 / N;
    const items = PIECES.map(([src, t, s]) => {
      const el = document.createElement('div'); el.className = 'carousel-item';
      el.innerHTML = `<img src="${IMG(src)}" alt="${t}, ${s}" draggable="false" loading="lazy">`;
      cring.appendChild(el); return el;
    });
    let angle = 0, vel = motion ? -0.12 : 0, dragX = null, lastX = 0, lastT = 0, front = -1, carVisible = false;
    const radius = () => Math.min(340, car.offsetWidth * 0.36);
    const layout = () => {
      const R = radius();
      items.forEach((el, i) => {
        const a = (i * step + angle) * Math.PI / 180;
        const z = Math.cos(a), s = 0.62 + (z + 1) * 0.24;
        el.style.transform = `translate3d(${Math.sin(a) * R}px, ${(1 - z) * -18}px, ${z * R * 0.5}px) scale(${s.toFixed(3)})`;
        el.style.zIndex = Math.round((z + 1) * 100);
        el.style.opacity = (0.35 + (z + 1) * 0.325).toFixed(2);
        el.style.filter = `brightness(${(0.55 + (z + 1) * 0.225).toFixed(2)})`;
      });
      const f = ((Math.round(-angle / step) % N) + N) % N;
      if (f !== front) {
        front = f; cap.classList.add('swap');
        setTimeout(() => { cap.innerHTML = `<b>${PIECES[f][1]}</b><span>${PIECES[f][2]}</span>`; cap.classList.remove('swap'); }, 160);
      }
    };
    const loop = () => {
      if (dragX === null) {
        if (Math.abs(vel) > 0.13) vel *= 0.95; else if (motion) vel += ((vel < 0 ? -0.12 : 0.12) - vel) * 0.05;
        angle += vel;
      }
      layout();
      if (carVisible) requestAnimationFrame(loop);
    };
    new IntersectionObserver(([e]) => { const was = carVisible; carVisible = e.isIntersecting; if (carVisible && !was) requestAnimationFrame(loop); }).observe(car);
    layout();
    car.addEventListener('pointerdown', e => { dragX = e.clientX; lastX = e.clientX; lastT = performance.now(); car.setPointerCapture(e.pointerId); });
    car.addEventListener('pointermove', e => {
      if (dragX === null) return;
      const now = performance.now(), dx = e.clientX - lastX;
      angle += dx * 0.35; vel = dx * 0.35 / Math.max(1, (now - lastT) / 16);
      lastX = e.clientX; lastT = now; if (!carVisible) layout();
    });
    const release = () => { dragX = null; };
    car.addEventListener('pointerup', release); car.addEventListener('pointercancel', release);
    car.addEventListener('keydown', e => {
      if (e.key === 'ArrowLeft') { vel = 0; angle += step; layout(); }
      if (e.key === 'ArrowRight') { vel = 0; angle -= step; layout(); }
    });
  }
})();
