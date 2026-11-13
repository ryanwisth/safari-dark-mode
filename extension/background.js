// Keyboard shortcut (Option-Shift-D) and the toolbar icon's on/off look.

async function sdmSyncIcon() {
  const s = await sdmLoad();
  const v = s.enabled ? 'on' : 'off';
  const action = sdmApi.action || sdmApi.browserAction;
  if (!action || !action.setIcon) return;
  try {
    await action.setIcon({ path: { 16: `icons/toolbar-${v}-16.png`, 32: `icons/toolbar-${v}-32.png` } });
  } catch (e) { /* older Safari: keep the manifest icon */ }
}

if (sdmApi.commands && sdmApi.commands.onCommand) {
  sdmApi.commands.onCommand.addListener(async (command) => {
    if (command !== 'toggle-dark-mode') return;
    const s = await sdmLoad();
    s.enabled = !s.enabled;
    await sdmSave(s);
  });
}

sdmApi.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes.sdm) sdmSyncIcon();
});

sdmSyncIcon();
