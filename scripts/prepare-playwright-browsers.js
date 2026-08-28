// Copies the locally-cached Playwright Chromium browser into
// backend/playwright-browsers/ so electron-builder can bundle it into
// the installer as an extra resource (see package.json's
// `build.extraResources`).
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
//
// Run this on whichever machine builds the installer - it must already
// have run `playwright install chromium` in the backend virtual
// environment at least once (see README).

const fs = require("fs");
const path = require("path");
const os = require("os");

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

if (!fs.existsSync(sourceDir)) {
  console.error(
    `Playwright browsers were not found at ${sourceDir}.\n` +
      'Run "playwright install chromium" in the backend virtual ' +
      "environment first, then re-run this build."
  );
  process.exit(1);
}

const entries = fs.readdirSync(sourceDir, { withFileTypes: true });

// Only copy the chromium-* folder(s), not firefox/webkit if those also
// happen to be installed - this app only ever launches Chromium, so
// bundling the others would just bloat the installer for nothing.
const chromiumEntries = entries.filter(
  (entry) => entry.isDirectory() && entry.name.startsWith("chromium")
);

if (chromiumEntries.length === 0) {
  console.error(
    `No chromium-* folder found under ${sourceDir}.\n` +
      'Run "playwright install chromium" in the backend virtual ' +
      "environment first, then re-run this build."
  );
  process.exit(1);
}

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
