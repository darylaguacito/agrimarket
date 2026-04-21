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

/* 2. Notification badge polling */
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
    .catch(function () {});
}

/* 3. Offline detection */
function updateOnlineStatus() {
  document.body.classList.toggle('offline', !navigator.onLine);
  if (navigator.onLine) flushOfflineQueue();
}
window.addEventListener('online',  updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);

/* 4. Offline delivery queue */
function queueOfflineDelivery(orderId) {
  const q = JSON.parse(localStorage.getItem('deliverQueue') || '[]');
  if (!q.includes(orderId)) { q.push(orderId); localStorage.setItem('deliverQueue', JSON.stringify(q)); }
}

async function flushOfflineQueue() {
  const q = JSON.parse(localStorage.getItem('deliverQueue') || '[]');
  if (!q.length) return;
  const remaining = [];
  for (const oid of q) {
    try {
      const r = await fetch(`/driver/api/stops/${oid}/deliver`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({note:'Delivered (synced from offline)'})
      });
      if (!r.ok) remaining.push(oid);
    } catch(e) { remaining.push(oid); }
  }
  localStorage.setItem('deliverQueue', JSON.stringify(remaining));
  if (remaining.length < q.length) fetchNotifCount();
}

document.addEventListener('DOMContentLoaded', function () {
  fetchNotifCount();
  setInterval(fetchNotifCount, 30000);
  updateOnlineStatus();

  /* Auto-dismiss flash messages */
  document.querySelectorAll('.flash').forEach(function (flash) {
    setTimeout(function () {
      flash.style.transition = 'opacity .5s ease';
      flash.style.opacity = '0';
      setTimeout(function () { flash.remove(); }, 500);
    }, 4000);
  });

  /* Register background sync if supported */
  if ('serviceWorker' in navigator && 'SyncManager' in window) {
    navigator.serviceWorker.ready.then(sw => {
      sw.sync.register('sync-deliveries').catch(() => {});
    });
  }
});
