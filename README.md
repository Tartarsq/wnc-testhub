# WNC TestHub

A modern web-based testing platform for managing WNC Titan 3 devices, automating Qualcomm QXDM logging, running throughput tests, and analyzing wireless network performance from a centralized dashboard.

---

## Overview

WNC TestHub provides a unified interface for wireless testing workflows. The application combines Titan 3 device management, throughput testing, QXDM automation, analytics, and session management into a single platform built with React and FastAPI.

The frontend is deployed publicly through Vercel, while the backend communicates with testing hardware and QXDM on a dedicated Windows test machine.

---

## Features

### Dashboard

- Real-time testing overview
- Device status monitoring
- Throughput summary
- Session tracking
- Recent activity feed
- Quick testing actions

### Devices

- Titan 3 connection management
- Firmware information
- Carrier information
- Radio technology
- Signal quality monitoring
- Direct access to the Titan Web GUI

### Throughput Testing

- Multi-run throughput tests
- Download speed
- Upload speed
- Latency measurements
- Live progress updates
- Automatic result storage

### QXDM Logs

- Start log capture
- Stop log capture
- Monitor QXDM status
- Session-based logging
- Automatic log management

### Analytics

- Historical throughput results
- Performance visualization
- Test history
- Session analytics

### Settings

- Application preferences
- Backend configuration
- Future expansion for testing options

---

# Technology Stack

## Frontend

- React
- Vite
- React Router
- Axios
- Recharts
- React Icons

## Backend

- FastAPI
- Python
- Uvicorn

## Hardware & Testing

- WNC Titan 3
- Qualcomm QXDM
- Throughput automation

---

# System Architecture

```text
                    React Frontend (Vercel)
                             │
                             ▼
                      FastAPI Backend
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                     ▼
     Titan 3 Device                      QXDM Controller
          │                                     │
          └──────────────────┬──────────────────┘
                             ▼
                    Session & Test Data
```

---

# Prerequisites

Before using WNC TestHub, ensure the following are installed or available:

- Python 3.11+
- Node.js
- Qualcomm QXDM
- WNC Titan 3
- Windows operating system

---

# Initial Setup

Before running any tests:

1. Clone the repository.
2. Install backend dependencies.
3. Install frontend dependencies.
4. Launch the backend.
5. Launch the frontend.
6. Connect to the Titan 3 device.
7. Enter the Titan 3 IP address in the **Devices** page.
8. Verify the device status changes to **Connected**.
9. Start testing.

**Note:** The application does not automatically discover Titan 3 devices. Users must manually enter the Titan 3 IP address before device monitoring, throughput testing, and QXDM automation can be used.

---

# Backend Setup

```bash
cd backend

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium

uvicorn api:app --reload
```

`playwright install chromium` is a one-time extra step (beyond `pip install`)
that downloads the actual browser Playwright drives for the Verizon GUI
syslog automation on the Syslog page.

---

# Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

Open:

```
http://localhost:5173
```

---

# Typical Workflow

1. Launch the backend.
2. Launch the frontend.
3. Connect to the Titan 3 device.
4. Enter the Titan 3 IP address.
5. Verify the connection.
6. Start QXDM logging if required.
7. Run throughput tests.
8. View results in Analytics.

---

# Current Capabilities

- Titan 3 monitoring
- Throughput testing
- QXDM automation
- Analytics dashboard
- Session management
- Public frontend deployment

---

# Future Improvements

- PCAT integration
- Crash dump collection
- Syslog automation
- User authentication
- Database integration
- Multi-device support
- Report generation
- Real-time backend connectivity over HTTPS


---


# Installation

## Clone the Repository

```bash
git clone https://github.com/Tartarsq/wnc-testhub.git

cd wnc-testhub
```

---

## Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a Python virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment:

### Windows Command Prompt

```cmd
.venv\Scripts\activate
```

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the required Python packages:

```bash
pip install -r requirements.txt
playwright install chromium
```

Start the backend server:

```bash
uvicorn api:app --reload
```

---

## Frontend Setup

Open a second terminal.

Navigate to the frontend directory:

```bash
cd frontend
```

Install the required Node.js packages:

```bash
npm install
```

Run the React development server:

```bash
npm run dev
```

Open your browser to:

```
http://localhost:5173
```

---

## Required Software

Before using WNC TestHub, install:

- Python 3.11+
- Node.js 20+
- npm
- Git
- Qualcomm QXDM
- WNC Titan 3 device

# Screenshots

Coming soon.

---

**Live Demo:** https://wnc-testhub.vercel.app

> **Note:** The live demo showcases the frontend interface. Hardware-dependent features such as Titan 3 communication, throughput testing, and QXDM log capture require the FastAPI backend running on a configured Windows test machine.


## Throughput Testing Requirement

WNC TestHub uses the **Ookla Speedtest CLI** to perform automated throughput testing.

Before running throughput tests:

1. Download the **Ookla Speedtest CLI** for Windows.
2. Create a folder named **`tools`** in the location expected by the application.
3. Place the `speedtest.exe` executable inside the `tools` folder.

Example:

```text
C:\
└── tools
    └── speedtest.exe
```

> **Important:** The backend expects `speedtest.exe` to be located in the configured `tools` directory. If the executable is missing or stored in a different location, throughput testing will not function.


# Desktop App (Electron)

WNC TestHub can also run as a self-contained Windows desktop app: an Electron
shell that launches the FastAPI backend for you and loads the built React UI,
so nothing needs to be run from a terminal.

## Run in development

This runs the Electron shell against your local `.venv` Python backend and a
production build of the frontend:

```bash
# from the project root
cd frontend && npm install && cd ..
npm install
npm run electron:dev
```

`npm run electron:dev` builds `frontend/dist` and then launches Electron,
which spawns `backend/.venv/Scripts/python.exe -m uvicorn` and waits for it
to respond on `http://127.0.0.1:8000/` before opening the window.

## Build a distributable installer

End users don't have Python installed, so the backend first needs to be
compiled into a standalone executable with PyInstaller, and only then does
Electron get packaged around it. PyInstaller is included in
`backend/requirements.txt`, so no separate `pip install pyinstaller` step is
needed as long as the venv's dependencies are up to date.

The backend's virtual environment must also already have Chromium installed
via Playwright (`playwright install chromium` — see setup above) before
building, since the installer bundles that browser directly so end-user
machines don't need Python/pip to fetch it themselves for the Syslog and
Devices radio-metrics login steps.

```bash
# One-time, if not already done (see First-Time Setup above):
cd backend
python -m pip install -r requirements.txt
playwright install chromium
cd ..

# Then, every time you want a fresh installer:
npm install
npm run dist
```

`npm run dist` runs the full chain itself: compiles the backend
(`backend:build`), builds the frontend (`frontend:build`), copies the
locally-cached Chromium browser into `backend/playwright-browsers/` for
bundling (`playwright:bundle`, via `scripts/prepare-playwright-browsers.js`),
then runs `electron-builder`.

The installer is written to `release/`. `electron-builder` bundles
`backend/dist/WNCTestHubBackend/` and `backend/playwright-browsers/` as extra
resources; the packaged app launches `WNCTestHubBackend.exe` from there
instead of a Python venv, and points Playwright at the bundled browser
instead of the machine's normal per-user cache.

**Note:** All of this must be run on Windows — the backend depends on
`pywin32`/`pywinauto` for QXDM/PCAT automation, and both the PyInstaller
output and the Chromium build downloaded by Playwright are
platform-specific.

**If `npm run dist` fails on `winCodeSign` with a symbolic-link/certificate
error:** that's electron-builder trying to download macOS code-signing
tools this Windows-only build doesn't need. Set
`CSC_IDENTITY_AUTO_DISCOVERY=false` before running `npm run dist` to skip
it, and clear `%LOCALAPPDATA%\electron-builder\Cache` if a previous failed
attempt left a corrupted partial download behind.


# Author

**Tarun Sathyanarayana**

Electrical & Computer Engineering

Rutgers University

Field Application Engineer Intern — WNC



