(() => {
  const feed = document.querySelector('.community-page');
  if (!feed) return;
  let lastUpdate = feed.dataset.lastUpdate || '';
  let checking = false;
  window.setInterval(async () => {
    if (checking || document.hidden || document.querySelector('dialog[open]')) return;
    checking = true;
    try {
      const response = await fetch(feed.dataset.updatesUrl, { headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!response.ok) return;
      const data = await response.json();
      if (data.updated_at && lastUpdate && data.updated_at !== lastUpdate) window.location.reload();
      lastUpdate = data.updated_at || lastUpdate;
    } catch (_) {
      // The normal page remains usable if this optional refresh check is unavailable.
    } finally {
      checking = false;
    }
  }, 5000);
})();
