if (window.location.pathname.startsWith('/wifi-database/')) {
  import('./wifi-main.js').then(({ startWifiData }) => startWifiData())
}
