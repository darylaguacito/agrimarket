/* ── AgriMarket App JS ── */

/* 1. User menu toggle */
function toggleMenu() {
  const menu = document.getElementById('userMenu');
  if (!menu) return;
  const isOpen = menu.style.display === 'block';
  menu.style.display = isOpen ? 'none' : 'block';
}

document.addEventListener('click', function (e) {
  const menu = document.getElementById('userMenu');
  const avatarBtn = document.querySelector('.avatar-btn');
  if (!menu) return;
  if (!menu.contains(e.target) && e.target !== avatarBtn) {
    menu.style.display = 'none';
  }
});

/* 2. Notification badge polling — works for all roles */
function fetchNotifCount() {
  fetch('/notifications/count')
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (data) {
      if (!data) return;
      const dot = document.getElementById('notifDot');
      if (!dot) return;
      if (data.count > 0) {
        dot.textContent = data.count > 99 ? '99+' : data.count;
        dot.style.display = 'inline-flex';
      } else {
        dot.style.display = 'none';
      }
    })
    .catch(function () { /* ignore */ });
}

document.addEventListener('DOMContentLoaded', function () {
  fetchNotifCount();
  setInterval(fetchNotifCount, 30000);

  /* Auto-dismiss flash messages after 4 seconds */
  document.querySelectorAll('.flash').forEach(function (flash) {
    setTimeout(function () {
      flash.style.transition = 'opacity .5s ease';
      flash.style.opacity = '0';
      setTimeout(function () { flash.remove(); }, 500);
    }, 4000);
  });
});
