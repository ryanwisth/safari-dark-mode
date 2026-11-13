// Settings shared by the content script, popup and background script.
// One object in storage.local under "sdm"; per-site choices live in `sites`
// as hostname -> "on" | "off" (absent = auto).
const SDM_DEFAULTS = {
  enabled: true,
  theme: 'dark',
  brightness: 100,
  contrast: 100,
  followSystem: false,
  sites: {},
};

const sdmApi = globalThis.browser || globalThis.chrome;

async function sdmLoad() {
  const got = await sdmApi.storage.local.get('sdm');
  return sdmNormalize(got && got.sdm);
}

function sdmNormalize(raw) {
  const s = Object.assign({}, SDM_DEFAULTS, raw || {});
  s.sites = Object.assign({}, (raw && raw.sites) || {});
  if (!SDM_THEMES.some((t) => t.id === s.theme)) s.theme = SDM_DEFAULTS.theme;
  return s;
}

async function sdmSave(settings) {
  await sdmApi.storage.local.set({ sdm: settings });
}

function sdmTheme(settings) {
  return SDM_THEMES.find((t) => t.id === settings.theme) || SDM_THEMES[0];
}

// The full CSS filter for a theme plus the user's brightness/contrast trim.
function sdmFilter(settings) {
  let f = sdmTheme(settings).filter;
  if (settings.brightness !== 100) f += ` brightness(${settings.brightness / 100})`;
  if (settings.contrast !== 100) f += ` contrast(${settings.contrast / 100})`;
  return f;
}
