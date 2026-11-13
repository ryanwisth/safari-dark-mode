(async () => {
  const $ = (id) => document.getElementById(id);
  let s = await sdmLoad();
  let tab = null;
  let host = null;

  try {
    [tab] = await sdmApi.tabs.query({ active: true, currentWindow: true });
  } catch (e) { /* no tab access */ }

  async function fetchStatus() {
    if (!tab) return null;
    try {
      return await sdmApi.tabs.sendMessage(tab.id, { type: 'sdm-status' });
    } catch (e) {
      return null; // Safari pages, PDFs, or the site isn't allowed yet
    }
  }

  // ---------- theme swatches ----------

  const grid = $('themes');
  for (const t of SDM_THEMES) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'theme';
    b.setAttribute('role', 'radio');
    b.dataset.id = t.id;
    b.innerHTML = `<span class="mini"><span class="mini-page">
        <span class="mini-title">Aa</span><span class="mini-line"></span><span class="mini-link"></span>
      </span></span><span class="name"></span>`;
    b.querySelector('.name').textContent = t.name;
    b.addEventListener('click', () => { s.theme = t.id; save(); render(); });
    grid.appendChild(b);
  }

  grid.addEventListener('keydown', (e) => {
    const step = { ArrowRight: 1, ArrowDown: 3, ArrowLeft: -1, ArrowUp: -3 }[e.key];
    if (!step) return;
    e.preventDefault();
    const i = SDM_THEMES.findIndex((t) => t.id === s.theme);
    const next = SDM_THEMES[(i + step + SDM_THEMES.length) % SDM_THEMES.length];
    s.theme = next.id;
    save();
    render();
    grid.querySelector(`[data-id="${next.id}"]`).focus();
  });

  // ---------- saving ----------

  let saveTimer = 0;
  function save(delay = 0) {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      await sdmSave(s);
      setTimeout(renderStatus, 120);
    }, delay);
  }

  // ---------- controls ----------

  $('enabled').addEventListener('change', (e) => { s.enabled = e.target.checked; save(); render(); });
  $('followSystem').addEventListener('change', (e) => { s.followSystem = e.target.checked; save(); render(); });

  for (const key of ['brightness', 'contrast']) {
    $(key).addEventListener('input', (e) => {
      s[key] = Number(e.target.value);
      render();
      save(150);
    });
    $(key).addEventListener('dblclick', () => { s[key] = 100; render(); save(); });
  }

  $('siteMode').addEventListener('click', (e) => {
    const mode = e.target.closest('button') && e.target.closest('button').dataset.mode;
    if (!mode || !host) return;
    if (mode === 'auto') delete s.sites[host];
    else s.sites[host] = mode;
    save();
    render();
  });

  // ---------- rendering ----------

  function render() {
    $('enabled').checked = s.enabled;
    $('main').classList.toggle('off', !s.enabled);
    $('followSystem').checked = s.followSystem;
    for (const b of grid.children) {
      b.setAttribute('aria-checked', String(b.dataset.id === s.theme));
      b.tabIndex = b.dataset.id === s.theme ? 0 : -1;
      b.querySelector('.mini').style.filter = sdmFilter(Object.assign({}, s, { theme: b.dataset.id }));
    }
    for (const key of ['brightness', 'contrast']) {
      $(key).value = s[key];
      $(`${key}Out`).textContent = `${s[key]}%`;
    }
    const mode = (host && s.sites[host]) || 'auto';
    for (const b of $('siteMode').children) b.setAttribute('aria-checked', String(b.dataset.mode === mode));
  }

  async function renderStatus() {
    const st = await fetchStatus();
    host = st ? st.host : null;
    $('host').textContent = host || 'This page';
    $('siteMode').classList.toggle('disabled', !host);
    let text;
    if (!st) text = 'Not available here';
    else if (st.active) text = 'Darkened';
    else if (!s.enabled) text = 'Dark mode is off';
    else if (st.siteMode === 'off') text = 'Off on this site';
    else if (s.followSystem && !matchMedia('(prefers-color-scheme: dark)').matches) text = 'Waiting for Dark Mode';
    else if (st.nativeDark) text = 'Already dark';
    else text = '';
    $('status').textContent = text;
    render();
  }

  render();
  renderStatus();
})();
