// Toggle contraseña visible/oculta
document.querySelectorAll('.toggle-password').forEach(btn => {
    btn.addEventListener('click', () => {
        const input = document.getElementById(btn.dataset.target);
        if (!input) return;
        input.type = input.type === 'password' ? 'text' : 'password';
        btn.textContent = input.type === 'password' ? '👁' : '🙈';
    });
});

// Menú móvil
const navToggle  = document.getElementById('navToggle');
const navLinks   = document.querySelector('.nav-links');
const navOverlay = document.getElementById('navOverlay');

function closeNav() {
    navLinks?.classList.remove('open');
    navOverlay?.classList.remove('open');
}

if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
        const opening = !navLinks.classList.contains('open');
        navLinks.classList.toggle('open');
        navOverlay?.classList.toggle('open', opening);
    });
    navOverlay?.addEventListener('click', closeNav);
}

// Dropdown de usuario — abre/cierra con click
const navUser = document.querySelector('.nav-user');
if (navUser) {
    navUser.querySelector('.nav-username').addEventListener('click', (e) => {
        e.stopPropagation();
        navUser.classList.toggle('open');
    });
    // Cierra al hacer click en cualquier otro lado
    document.addEventListener('click', () => {
        navUser.classList.remove('open');
    });
    // Evita que clicks dentro del dropdown lo cierren
    navUser.querySelector('.nav-dropdown').addEventListener('click', (e) => {
        e.stopPropagation();
    });
}

// Auto-cerrar flash messages
document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => {
        el.style.transition = 'opacity .4s';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 400);
    }, 4000);
});

// Menú: se compacta y toma fondo al bajar
const navbar = document.querySelector('.navbar');
if (navbar) {
    const onScrollNav = () => navbar.classList.toggle('scrolled', window.scrollY > 12);
    window.addEventListener('scroll', onScrollNav, { passive: true });
    onScrollNav();
}
