const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("testHubDesktop", {
  isElectron: true,
});