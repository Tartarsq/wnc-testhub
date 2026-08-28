// Copies the locally-cached Playwright Chromium browser into
// backend/playwright-browsers/ so electron-builder can bundle it into
// the installer as an extra resource (see package.json's
// `build.extraResources`). Installs Chromium first if it isn't already
// cached, so building the installer never requires a separate manual
// step beyond the normal `pip install -r requirements.txt` setup.
//
// Why this exists: PyInstaller bundles the `playwright` Python package
// into the compiled backend, but not the actual Chromium binary itself -
// that's a separate download Playwright normally fetches via
// `playwright install chromium`. An end-user machine that's only ever
// run the installer has no Python/pip to run that command, so without
// this step the two features that need a real browser (Syslog's
// automated login, and the Devices page's live radio-metrics login)
// would fail on a fresh install. Bundling the browser directly means
// nothing extra needs to be installed on the machine running the app -
// electron/main.cjs points PLAYWRIGHT_BROWSERS_PATH at the bundled copy
// at startup in a packaged build.

const fs = require("fs");
const path = require("path");
const os = require("os");
const { execFileSync } = require("child_process");

const DEFAULT_CACHE_DIR = path.join(
  os.homedir(),
  "AppData",
  "Local",
  "ms-playwright"
);

const sourceDir = process.env.PLAYWRIGHT_BROWSERS_PATH || DEFAULT_CACHE_DIR;
const destDir = path.resolve(
  __dirname,
  "..",
  "backend",
  "playwright-browsers"
);
const backendPython = path.resolve(
  __dirname,
  "..",
  "backend",
  ".venv",
  "Scripts",
  "python.exe"
);

function findChromiumEntries() {
  if (!fs.existsSync(sourceDir)) {
    return [];
  }

  return fs
    .readdirSync(sourceDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name.startsWith("chromium"));
}

let chromiumEntries = findChromiumEntries();

if (chromiumEntries.length === 0) {
  if (!fs.existsSync(backendPython)) {
    console.error(
      `No Chromium build was found under ${sourceDir}, and the backend ` +
        `virtual environment doesn't exist yet at ${backendPython} to ` +
        "install one automatically.\n" +
        "Set it up first: cd backend && python -m venv .venv && " +
        ".venv\\Scripts\\activate && pip install -r requirements.txt"
    );
    process.exit(1);
  }

  console.log(
    "No cached Chromium build found - installing it now " +
      "(playwright install chromium)..."
  );

  execFileSync(backendPython, ["-m", "playwright", "install", "chromium"], {
    stdio: "inherit",
  });

  chromiumEntries = findChromiumEntries();
}

if (chromiumEntries.length === 0) {
  console.error(
    "playwright install chromium ran, but still no chromium-* folder " +
      `was found under ${sourceDir}. Check the install output above ` +
      "for what went wrong."
  );
  process.exit(1);
}

// Only copy the chromium-* folder(s), not firefox/webkit if those also
// happen to be installed - this app only ever launches Chromium, so
// bundling the others would just bloat the installer for nothing.
fs.rmSync(destDir, { recursive: true, force: true });
fs.mkdirSync(destDir, { recursive: true });

for (const entry of chromiumEntries) {
  const from = path.join(sourceDir, entry.name);
  const to = path.join(destDir, entry.name);
  console.log(`Copying ${from}\n  -> ${to}`);
  fs.cpSync(from, to, { recursive: true });
}

console.log(
  `Bundled ${chromiumEntries.length} Chromium build(s) for packaging.`
);
