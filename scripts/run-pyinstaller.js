// Runs PyInstaller through the backend venv's own `python -m PyInstaller`
// instead of relying on a bare `pyinstaller` command being resolvable on
// PATH - that only works if the venv happens to already be activated in
// the current shell, which is exactly what caused
// "'pyinstaller' is not recognized as an internal or external command"
// on a fresh machine that had never activated the venv first. Invoking
// it through the venv's own python.exe works the same regardless of
// whether the venv is activated.

const path = require("path");
const { execFileSync } = require("child_process");

const backendDir = path.resolve(__dirname, "..", "backend");
const venvPython = path.join(backendDir, ".venv", "Scripts", "python.exe");

execFileSync(
  venvPython,
  ["-m", "PyInstaller", "WNCTestHubBackend.spec", "--noconfirm"],
  { stdio: "inherit", cwd: backendDir }
);
