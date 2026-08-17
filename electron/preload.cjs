const { contextBridge } = require("electron");

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
});
