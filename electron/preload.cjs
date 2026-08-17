const {
  app,
  BrowserWindow,
} = require("electron");

const path = require("node:path");
const { spawn } = require("node:child_process");

let mainWindow;
let backendProcess = null;

const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = "8000";

function startBackend() {
  const projectRoot = path.resolve(
    __dirname,
    ".."
  );

  const backendDirectory = path.join(
    projectRoot,
    "backend"
  );

  const pythonExecutable = path.join(
    projectRoot,
    ".venv",
    "Scripts",
    "python.exe"
  );

  console.log(
    "Starting FastAPI backend..."
  );

  backendProcess = spawn(
    pythonExecutable,
    [
      "-m",
      "uvicorn",
      "api:app",
      "--host",
      BACKEND_HOST,
      "--port",
      BACKEND_PORT,
    ],
    {
      cwd: backendDirectory,
      windowsHide: true,
    }
  );

  backendProcess.stdout.on(
    "data",
    (data) => {
      console.log(
        `[FastAPI] ${data}`
      );
    }
  );

  backendProcess.stderr.on(
    "data",
    (data) => {
      console.error(
        `[FastAPI] ${data}`
      );
    }
  );

  backendProcess.on(
    "error",
    (error) => {
      console.error(
        "Failed to start FastAPI:",
        error
      );
    }
  );

  backendProcess.on(
    "close",
    (code) => {
      console.log(
        `FastAPI exited with code ${code}`
      );

      backendProcess = null;
    }
  );
}

function stopBackend() {
  if (!backendProcess) {
    return;
  }

  console.log(
    "Stopping FastAPI backend..."
  );

  backendProcess.kill();

  backendProcess = null;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1500,
    height: 950,

    minWidth: 1100,
    minHeight: 700,

    title: "WNC TestHub",

    webPreferences: {
      preload: path.join(
        __dirname,
        "preload.cjs"
      ),

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

  console.log(
    "Loading frontend:",
    frontendPath
  );

  mainWindow.loadFile(
    frontendPath
  );

  mainWindow.on(
    "closed",
    () => {
      mainWindow = null;
    }
  );
}

app.whenReady().then(() => {
  startBackend();

  createWindow();

  app.on(
    "activate",
    () => {
      if (
        BrowserWindow
          .getAllWindows()
          .length === 0
      ) {
        createWindow();
      }
    }
  );
});

app.on(
  "before-quit",
  () => {
    stopBackend();
  }
);

app.on(
  "window-all-closed",
  () => {
    if (
      process.platform !== "darwin"
    ) {
      app.quit();
    }
  }
);