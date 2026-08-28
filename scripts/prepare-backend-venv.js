// Ensures the backend's Python virtual environment exists and has every
// requirement installed, so `npm run dist` and `npm run electron:dev`
// work from a fresh clone without any manual Python setup beyond having
// Python itself already installed on the machine (which, like Node.js
// itself, can't reasonably be bootstrapped by an npm script).

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const backendDir = path.resolve(__dirname, "..", "backend");
const venvDir = path.join(backendDir, ".venv");
const venvPython = path.join(venvDir, "Scripts", "python.exe");

function run(command, args) {
  console.log(`> ${command} ${args.join(" ")}`);
  execFileSync(command, args, { stdio: "inherit", cwd: backendDir });
}

if (!fs.existsSync(venvPython)) {
  console.log("Backend virtual environment not found - creating it...");

  try {
    run("python", ["-m", "venv", ".venv"]);
  } catch (error) {
    console.error(
      "Could not create the virtual environment. Is Python installed " +
        "and available as `python` on PATH?"
    );
    throw error;
  }
}

console.log("Installing/updating backend Python dependencies...");
run(venvPython, ["-m", "pip", "install", "--upgrade", "pip"]);
run(venvPython, ["-m", "pip", "install", "-r", "requirements.txt"]);

console.log("Backend virtual environment is ready.");
