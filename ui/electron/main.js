/**
 * electron/main.js — Electron Main Process
 *
 * Creates a frameless, dark HUD window that loads the React app.
 * Features: tray icon, Ctrl+Shift+J toggle, custom titlebar via IPC.
 */

const {
  app,
  BrowserWindow,
  globalShortcut,
  Tray,
  Menu,
  nativeImage,
  ipcMain,
} = require("electron");
const path = require("path");

let mainWindow = null;
let tray = null;

// ── Window Creation ──────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 800,
    minWidth: 1000,
    minHeight: 600,
    frame: false,
    backgroundColor: "#0a0a0f",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false, // Allow Leaflet tile CDN + YouTube iframe
    },
  });

  mainWindow.loadFile(path.join(__dirname, "..", "src", "index.html"));

  // Show when ready to avoid white flash
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    mainWindow.webContents.openDevTools({ mode: "detach" });
  });

  mainWindow.on("close", (e) => {
    // Hide to tray instead of closing
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

// ── Tray Icon ────────────────────────────────

function createTray() {
  // Create a simple 16x16 cyan circle icon
  const icon = nativeImage.createFromDataURL(
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAA" +
      "VElEQVQ4T2NkYPj/n4EBFTAyMjIwoDJQJDAwMPxHk2dgYGBgRBdjYGBgYERXw8DAwMCI" +
      "rglDnAHOZ8RQw4hhACM2NQwMDIyMDMQLMDAwoHsBAIi1FBFpXaS6AAAAAElFTkSuQmCC"
  );

  tray = new Tray(icon);
  tray.setToolTip("Jarvis HUD");

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Show HUD",
      click: () => {
        mainWindow.show();
        mainWindow.focus();
      },
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        app.isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);

  tray.on("click", () => {
    if (mainWindow.isVisible()) {
      mainWindow.focus();
    } else {
      mainWindow.show();
    }
  });
}

// ── IPC Handlers ─────────────────────────────

function setupIPC() {
  ipcMain.on("window-minimize", () => mainWindow.minimize());

  ipcMain.on("window-close", () => mainWindow.hide());

  ipcMain.on("window-toggle-ontop", () => {
    const isOnTop = mainWindow.isAlwaysOnTop();
    mainWindow.setAlwaysOnTop(!isOnTop);
    mainWindow.webContents.send("always-on-top-changed", !isOnTop);
  });

  // World Dashboard fullscreen toggle
  ipcMain.on("open-dashboard", () => {
    mainWindow.setFullScreen(true);
    mainWindow.focus();
  });

  ipcMain.on("close-dashboard", () => {
    mainWindow.setFullScreen(false);
  });
}

// ── App Lifecycle ────────────────────────────

app.whenReady().then(() => {
  createWindow();
  createTray();
  setupIPC();

  // Global shortcut: Ctrl+Shift+J to toggle HUD
  globalShortcut.register("Ctrl+Shift+J", () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});
