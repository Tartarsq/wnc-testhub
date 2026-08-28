const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");

const path = require("node:path");
const fs = require("node:fs");
const http = require("node:http");
const { spawn } = require("node:child_process");

let mainWindow;
let backendProcess = null;

const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = "8000";
const BACKEND_HEALTH_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}/`;

/**
 * Decide how to launch the FastAPI backend.
 *
 * - In a packaged build, run the PyInstaller-compiled executable that
 *   electron-builder ships as an extra resource (see package.json's
 *   `build.extraResources`). End users don't have Python installed, so
 *   this must be a standalone .exe.
 * - In dev, run the backend straight out of the project's virtual
 *   environment so `npm run electron` works against live source.
 */
function resolveBackendCommand() {
  if (app.isPackaged) {
    const backendExecutable = path.join(
      process.resourcesPath,
      "backend",
      "WNCTestHubBackend.exe"
    );

    // Playwright (used for the Syslog and Devices radio-metrics login
    // steps) needs a real Chromium binary, which PyInstaller doesn't
    // bundle on its own - end-user machines normally have no Python/pip
    // to run `playwright install chromium` themselves. electron-builder
    // instead bundles a pre-downloaded Chromium as an extra resource
    // (see package.json's `build.extraResources` and
    // scripts/prepare-playwright-browsers.js), and this env var is how
    // Playwright's own Python library is told to look there instead of
    // its normal per-user cache folder.
    const bundledBrowsersPath = path.join(
      process.resourcesPath,
      "playwright-browsers"
    );

    return {
      command: backendExecutable,
      args: [],
      cwd: path.dirname(backendExecutable),
      env: fs.existsSync(bundledBrowsersPath)
        ? { PLAYWRIGHT_BROWSERS_PATH: bundledBrowsersPath }
        : {},
    };
  }

  const projectRoot = path.resolve(__dirname, "..");
  const backendDirectory = path.join(projectRoot, "backend");

  const pythonExecutable = path.join(
    backendDirectory,
    ".venv",
    "Scripts",
    "python.exe"
  );

  return {
    command: pythonExecutable,
    args: [
      "-m",
      "uvicorn",
      "api:app",
      "--host",
      BACKEND_HOST,
      "--port",
      BACKEND_PORT,
    ],
    cwd: backendDirectory,
    env: {},
  };
}

function startBackend() {
  const { command, args, cwd, env } = resolveBackendCommand();

  if (!fs.existsSync(command)) {
    const message = app.isPackaged
      ? `Could not find the backend executable:\n${command}\n\nTry reinstalling the application.`
      : `Could not find the backend Python interpreter:\n${command}\n\n` +
        "Set up the virtual environment first:\n" +
        "cd backend && python -m venv .venv && " +
        ".venv\\Scripts\\activate && pip install -r requirements.txt";

    console.error(message);
    dialog.showErrorBox("WNC TestHub Backend Not Found", message);
    return;
  }

  console.log("Starting backend:", command);

  backendProcess = spawn(command, args, {
    cwd,
    windowsHide: true,
    env: { ...process.env, ...env },
  });

  backendProcess.stdout?.on("data", (data) => {
    console.log(`[Backend] ${data}`);
  });

  backendProcess.stderr?.on("data", (data) => {
    console.error(`[Backend] ${data}`);
  });

  backendProcess.on("error", (error) => {
    console.error("Failed to start backend:", error);
  });

  backendProcess.on("close", (code) => {
    console.log(`Backend exited with code ${code}`);
    backendProcess = null;
  });
}

function stopBackend() {
  if (!backendProcess) {
    return;
  }

  console.log("Stopping backend...");

  backendProcess.kill();
  backendProcess = null;
}

/**
 * Poll the backend until it responds or the timeout elapses, so the
 * window doesn't come up before the API is ready to serve requests.
 */
function waitForBackend(timeoutMs = 20000, intervalMs = 300) {
  const deadline = Date.now() + timeoutMs;

  return new Promise((resolve) => {
    const attempt = () => {
      const request = http.get(BACKEND_HEALTH_URL, (response) => {
        response.resume();
        resolve(true);
      });

      request.on("error", () => {
        if (Date.now() >= deadline) {
          resolve(false);
          return;
        }

        setTimeout(attempt, intervalMs);
      });

      request.setTimeout(intervalMs, () => request.destroy());
    };

    attempt();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1500,
    height: 950,
    minWidth: 1100,
    minHeight: 700,
    title: "WNC TestHub",

    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const frontendPath = path.join(
    __dirname,
    "..",
    "frontend",
    "dist",
    "index.html"
  );

  console.log("Loading frontend:", frontendPath);

  mainWindow.loadFile(frontendPath);

  // Links like "Open Titan Web GUI" (a plain <a target="_blank"> in the
  // frontend, pointed at the Titan's https:// admin page) must never open
  // inside this window - the Titan serves a self-signed certificate that
  // Electron doesn't trust, so an in-app navigation to it fails and leaves
  // the app blank instead of showing an error. Hand every such request off
  // to the OS's real default browser instead.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  // Safety net: if anything ever tries to navigate this window itself
  // (rather than opening a new one) away from the loaded app file, redirect
  // that to the external browser too instead of letting the app go blank.
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith("file://")) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

ipcMain.handle("open-external-url", (_event, url) => {
  if (typeof url !== "string" || !/^https?:\/\//i.test(url)) {
    console.error("Refused to open a non-http(s) external URL:", url);
    return false;
  }

  shell.openExternal(url);
  return true;
});

app.whenReady().then(async () => {
  startBackend();

  const backendReady = await waitForBackend();

  if (!backendReady) {
    console.error(
      "Backend did not respond before starting the UI; loading anyway."
    );
  }

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("before-quit", () => {
  stopBackend();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
