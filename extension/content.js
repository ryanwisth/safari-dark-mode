// Darkens the page with one CSS filter on <html>, then flips media back.
// Runs at document_start so the page never paints white first.
(() => {
  'use strict';
  if (window.__sdmLoaded) return;
  window.__sdmLoaded = true;

  const root = document.documentElement;
  const host = location.hostname;
  const ON = 'sdm-on';
  const REV = 'data-sdm-rev';
  const systemDark = matchMedia('(prefers-color-scheme: dark)');

  // Media that must keep its real colors: flipped a second time. SVG images
  // are usually logos and icons drawn in dark ink, so they stay inverted.
  const REVERSE = [
    'img:not([src*=".svg"]):not([src^="data:image/svg"])', 'video', 'embed', 'object', 'svg image',
    'iframe[src*="youtube.com/embed"]', 'iframe[src*="youtube-nocookie.com"]',
    'iframe[src*="player.vimeo.com"]', 'iframe[src*="dailymotion.com/embed"]',
    'iframe[src*="player.twitch.tv"]', 'iframe[src*="google.com/maps"]',
    '[style*="background-image:url"]', '[style*="background-image: url"]',
    '[style*="background:url"]', '[style*="background: url"]',
    `[${REV}]`,
  ].join(',');

  let settings = null;
  let nativeDark = null;      // null until measured on this page
  let nativeCache = {};       // "host|light" / "host|dark" -> bool, remembered across visits
  let fullscreen = false;
  let styleEl = null;
  let scannedBody = false;

  // ---------- state ----------

  function siteMode() {
    return (settings && settings.sites[host]) || 'auto';
  }

  function scheme() {
    return systemDark.matches ? 'dark' : 'light';
  }

  function shouldDarken() {
    if (!settings || !settings.enabled || fullscreen) return false;
    const mode = siteMode();
    if (mode === 'off') return false;
    if (settings.followSystem && !systemDark.matches) return false;
    if (mode === 'on') return true;
    const known = nativeDark !== null ? nativeDark : nativeCache[`${host}|${scheme()}`];
    return !known;
  }

  function css() {
    return `html.${ON}{filter:${sdmFilter(settings)}!important;color-scheme:light!important}
html.${ON} :is(${REVERSE}){filter:${sdmTheme(settings).reverse}!important}
html.${ON} :is(${REVERSE}) :is(${REVERSE}){filter:none!important}`;
  }

  function update() {
    if (!settings) return;
    if (!shouldDarken()) {
      root.classList.remove(ON);
      return;
    }
    if (!styleEl) {
      styleEl = document.createElement('style');
      styleEl.id = 'sdm-style';
    }
    const text = css();
    if (styleEl.textContent !== text) styleEl.textContent = text;
    if (!styleEl.isConnected) (document.head || root).appendChild(styleEl);
    root.classList.add(ON);
    if (!scannedBody && document.body) {
      scannedBody = true;
      scheduleScan(document.body);
    }
  }

  // ---------- is the site already dark? ----------

  const probe = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
  const colorCache = new Map();

  // Any CSS color string -> [r, g, b, a] in 0..255 sRGB (handles oklch, p3, etc).
  function rgba(str) {
    if (colorCache.has(str)) return colorCache.get(str);
    probe.clearRect(0, 0, 1, 1);
    probe.fillStyle = '#000';
    probe.fillStyle = str;
    probe.fillRect(0, 0, 1, 1);
    const d = probe.getImageData(0, 0, 1, 1).data;
    const a = d[3] / 255;
    const out = a > 0 ? [d[0] / a, d[1] / a, d[2] / a, d[3]] : [0, 0, 0, 0];
    colorCache.set(str, out);
    return out;
  }

  function luminance([r, g, b]) {
    const lin = (c) => ((c /= 255) <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  }

  // A page with no background of its own shows the browser canvas, which is
  // dark only when the page opted into a dark color-scheme.
  function canvasColor() {
    let cs = getComputedStyle(root).colorScheme || 'normal';
    if (cs === 'normal') {
      const meta = document.querySelector('meta[name="color-scheme"]');
      cs = (meta && meta.content) || '';
    }
    const dark = /dark/.test(cs) && (!/light/.test(cs) || systemDark.matches);
    return dark ? [30, 30, 30, 255] : [255, 255, 255, 255];
  }

  // Background actually showing behind an element: first mostly-opaque one up the tree.
  function backdrop(el) {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const c = rgba(getComputedStyle(n).backgroundColor);
      if (c[3] >= 128) return c;
    }
    // With no background on <html>, the body's background paints the whole window.
    if (document.body) {
      const c = rgba(getComputedStyle(document.body).backgroundColor);
      if (c[3] >= 128) return c;
    }
    return canvasColor();
  }

  function measureNativeDark() {
    if (!document.body) return null;
    const w = innerWidth, h = innerHeight;
    if (!w || !h) return null;
    const points = [[0.5, 0.5], [0.25, 0.25], [0.75, 0.25], [0.25, 0.75], [0.75, 0.75]];
    let dark = 0, seen = 0;
    for (const [x, y] of points) {
      const el = document.elementFromPoint(w * x, h * y);
      if (!el) continue;
      seen++;
      if (luminance(backdrop(el)) < 0.18) dark++;
    }
    if (!seen) return null;
    // Light body text breaks a tie when the samples land on images.
    const bodyText = luminance(rgba(getComputedStyle(document.body).color));
    return dark * 2 > seen || (dark * 2 === seen && bodyText > 0.5);
  }

  // Our class forces color-scheme: light, so measure with it off. No paint
  // happens inside this synchronous block, so nothing flickers.
  function recheck() {
    root.classList.remove(ON);
    let measured = null;
    try { measured = measureNativeDark(); } catch (e) { /* page mid-teardown */ }
    if (measured !== null) {
      nativeDark = measured;
      const key = `${host}|${scheme()}`;
      if (nativeCache[key] !== measured) {
        nativeCache[key] = measured;
        const keys = Object.keys(nativeCache);
        if (keys.length > 600) keys.slice(0, keys.length - 500).forEach((k) => delete nativeCache[k]);
        sdmApi.storage.local.set({ sdmNative: nativeCache }).catch(() => {});
      }
    }
    update();
  }

  let recheckTimer = 0;
  function recheckSoon(ms = 150) {
    clearTimeout(recheckTimer);
    recheckTimer = setTimeout(recheck, ms);
  }

  // ---------- big background photos set from stylesheets ----------

  let pending = [];
  let cursor = 0;
  let scanTimer = 0;

  function scheduleScan(node) {
    if (!node || node.nodeType !== 1 || !root.classList.contains(ON)) return;
    pending.push(node);
    for (const el of node.getElementsByTagName('*')) pending.push(el);
    if (!scanTimer) scanTimer = setTimeout(runScan, 250);
  }

  function isPhotoBackground(el, docHeight) {
    if (el === document.body || el === root || el.hasAttribute(REV)) return false;
    const cs = getComputedStyle(el);
    if (!cs.backgroundImage.includes('url(')) return false;
    // Tiled textures stay inverted; photos are sized to cover/contain or not repeated.
    const photoLike = /cover|contain|%/.test(cs.backgroundSize) || cs.backgroundRepeat.startsWith('no-repeat');
    if (!photoLike) return false;
    const r = el.getBoundingClientRect();
    return r.width >= 100 && r.height >= 60 && r.height < docHeight * 0.9;
  }

  // 500 elements per tick so a huge page never stalls.
  function runScan() {
    scanTimer = 0;
    const docHeight = Math.max(root.scrollHeight, innerHeight);
    const end = Math.min(cursor + 500, pending.length);
    for (; cursor < end; cursor++) {
      const el = pending[cursor];
      if (el.isConnected && isPhotoBackground(el, docHeight)) el.setAttribute(REV, '');
    }
    if (cursor < pending.length) {
      scanTimer = setTimeout(runScan, 30);
    } else {
      pending = [];
      cursor = 0;
    }
  }

  // ---------- wiring ----------

  // The site switching its own theme shows up as a class/attribute change on
  // <html> or <body>. Ignore changes that are only our own class.
  const withoutOurs = (v) => (v || '').split(/\s+/).filter((c) => c && c !== ON).join(' ');
  const themeAttrs = ['class', 'style', 'data-theme', 'data-color-mode', 'data-mode', 'data-color-scheme'];
  const attrWatch = new MutationObserver((records) => {
    for (const r of records) {
      const now = r.target.getAttribute(r.attributeName);
      const changed = r.attributeName === 'class' ? withoutOurs(r.oldValue) !== withoutOurs(now) : r.oldValue !== now;
      if (changed) { recheckSoon(); return; }
    }
  });
  attrWatch.observe(root, { attributes: true, attributeFilter: themeAttrs, attributeOldValue: true });

  new MutationObserver((records) => {
    let added = 0;
    for (const r of records) {
      for (const n of r.addedNodes) {
        if (n.nodeType !== 1) continue;
        added++;
        if (n === document.body) {
          attrWatch.observe(n, { attributes: true, attributeFilter: themeAttrs, attributeOldValue: true });
          update();
        } else if (scannedBody) {
          scheduleScan(n);
        }
      }
    }
    // A big swap of content (single-page app navigation) may change the page's own colors.
    if (added > 40) recheckSoon(600);
  }).observe(root, { childList: true, subtree: true });
  if (document.body) attrWatch.observe(document.body, { attributes: true, attributeFilter: themeAttrs, attributeOldValue: true });

  const onFullscreen = () => {
    fullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement);
    update();
  };
  document.addEventListener('fullscreenchange', onFullscreen);
  document.addEventListener('webkitfullscreenchange', onFullscreen);

  systemDark.addEventListener('change', () => { nativeDark = null; update(); recheckSoon(400); });

  document.addEventListener('DOMContentLoaded', recheck, { once: true });
  window.addEventListener('load', () => {
    recheck();
    setTimeout(recheck, 800);
    setTimeout(recheck, 2500);
  }, { once: true });

  sdmApi.storage.onChanged.addListener((changes, area) => {
    if (area !== 'local' || !changes.sdm) return;
    settings = sdmNormalize(changes.sdm.newValue);
    update();
  });

  sdmApi.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (!msg || msg.type !== 'sdm-status') return;
    sendResponse({ host, active: root.classList.contains(ON), nativeDark: !!nativeDark, siteMode: siteMode() });
    return true;
  });

  sdmApi.storage.local.get(['sdm', 'sdmNative']).then((got) => {
    settings = sdmNormalize(got && got.sdm);
    nativeCache = (got && got.sdmNative) || {};
    if (document.readyState === 'loading') update();
    else recheck();
  });
})();
