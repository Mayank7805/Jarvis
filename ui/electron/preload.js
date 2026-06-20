/**
 * electron/preload.js — Context Bridge
 *
 * Exposes safe window-control APIs to the renderer process.
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  minimize: () => ipcRenderer.send("window-minimize"),
  close: () => ipcRenderer.send("window-close"),
  toggleAlwaysOnTop: () => ipcRenderer.send("window-toggle-ontop"),
  onAlwaysOnTopChanged: (callback) =>
    ipcRenderer.on("always-on-top-changed", (_event, value) => callback(value)),

  // World Dashboard fullscreen
  openDashboard: () => ipcRenderer.send("open-dashboard"),
  closeDashboard: () => ipcRenderer.send("close-dashboard"),
});
