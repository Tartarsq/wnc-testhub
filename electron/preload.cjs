const { contextBridge, ipcRenderer } = require("electron");

// This is the actual preload script: it runs in an isolated context before
// the renderer loads, and its only job is to expose a small, safe surface
// to the frontend via contextBridge. It must not touch main-process-only
// modules like `app` or `BrowserWindow` — those live in electron/main.cjs.
contextBridge.exposeInMainWorld("wncTestHub", {
  isElectron: true,
  platform: process.platform,
  versions: {
    app: process.env.npm_package_version || null,
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node,
  },
  // Opens a URL in the OS's real default browser (e.g. the Titan's Web
  // GUI) instead of letting it navigate inside the app window - the Titan
  // serves a self-signed certificate Electron doesn't trust, so loading it
  // in-app fails and leaves the window blank.
  openExternal: (url) => ipcRenderer.invoke("open-external-url", url),
});
