const toggle = document.getElementById('menu-toggle');
if (toggle) toggle.addEventListener('click', () => {
  const open = document.body.classList.toggle('nav-open');
  toggle.setAttribute('aria-expanded', String(open));
});

document.addEventListener('keydown', event => { if (event.key === 'Escape') { document.body.classList.remove('nav-open'); toggle?.setAttribute('aria-expanded', 'false'); } });
