// ── Live updates: reload if new photos have shown up ──────────────────────
function pollForNewPhotos(startCount, intervalMs) {
  setInterval(async () => {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data.count !== startCount) location.reload();
    } catch (e) { /* venue wifi hiccup — just try again next tick */ }
  }, intervalMs || 6000);
}

// ── Download: sequential <a download> clicks (works on Android Chrome; on
// iOS Safari these generally land in Files, not Photos — see shareFiles). ──
function downloadSequential(urls) {
  let i = 0;
  function next() {
    if (i >= urls.length) return;
    const a = document.createElement('a');
    a.href = urls[i];
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
    i += 1;
    setTimeout(next, 400);
  }
  next();
}

// ── Share: Web Share API with real files — the reliable "save to Photos"
// path on iOS Safari 15+. Returns true if the share sheet was shown. ──────
async function shareFiles(urls, title, onProgress) {
  try {
    const files = [];
    for (let i = 0; i < urls.length; i++) {
      if (onProgress) onProgress(i + 1, urls.length);
      const res = await fetch(urls[i]);
      const blob = await res.blob();
      files.push(new File([blob], urls[i].split('/').pop(), { type: blob.type }));
    }
    if (navigator.canShare && navigator.canShare({ files })) {
      await navigator.share({ files, title: title || 'Photos' });
      return true;
    }
  } catch (e) { /* user cancelled, or share not supported — caller falls back */ }
  return false;
}

// ── Index page: "SELECT PHOTOS" multi-select + batch download ─────────────
function initSelectMode() {
  const toggle = document.getElementById('select-toggle');
  const bar = document.getElementById('select-bar');
  if (!toggle || !bar) return;

  const countEl = document.getElementById('select-count');
  const selected = new Set();

  function refresh() {
    countEl.textContent = selected.size;
    bar.style.display = selected.size > 0 ? 'flex' : 'none';
  }

  toggle.addEventListener('click', () => {
    const on = document.body.classList.toggle('selecting');
    toggle.textContent = on ? 'CANCEL' : 'SELECT PHOTOS';
    if (!on) {
      selected.clear();
      document.querySelectorAll('.thumb.selected').forEach((el) => el.classList.remove('selected'));
      refresh();
    }
  });

  document.querySelectorAll('.thumb').forEach((el) => {
    el.addEventListener('click', (e) => {
      if (!document.body.classList.contains('selecting')) return;
      e.preventDefault();
      const url = el.dataset.download;
      if (selected.has(url)) { selected.delete(url); el.classList.remove('selected'); }
      else { selected.add(url); el.classList.add('selected'); }
      refresh();
    });
  });

  document.getElementById('select-download').addEventListener('click', () => {
    downloadSequential(Array.from(selected));
  });
}

// ── Single-photo page: swipe left/right to move prev/next ─────────────────
function initSwipe(prevHref, nextHref) {
  const el = document.querySelector('.photo-main');
  if (!el) return;
  let startX = null;

  el.addEventListener('touchstart', (e) => { startX = e.touches[0].clientX; }, { passive: true });
  el.addEventListener('touchend', (e) => {
    if (startX === null) return;
    const dx = e.changedTouches[0].clientX - startX;
    startX = null;
    if (Math.abs(dx) < 40) return;
    if (dx < 0 && nextHref) window.location.href = nextHref;
    if (dx > 0 && prevHref) window.location.href = prevHref;
  }, { passive: true });
}
