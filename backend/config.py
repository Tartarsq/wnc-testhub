from pathlib import Path


# ==========================================================
# Project folders
# ==========================================================

BACKEND_FOLDER = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_FOLDER.parent
RESULTS_FOLDER = PROJECT_ROOT / "results"


# ==========================================================
# Titan 3 defaults
# ==========================================================

DEFAULT_TITAN_IP = "192.168.1.1"
DEFAULT_TITAN_PORT = 80
DEFAULT_TITAN_PROTOCOL = "http"


# ==========================================================
# Test defaults
# ==========================================================

DEFAULT_CARRIER = "Verizon"
DEFAULT_TECHNOLOGY = "NR"
DEFAULT_MODE = "NSA"
DEFAULT_TEST_TYPE = "Wi-Fi Throughput"
DEFAULT_RESULT = "PASS"


# ==========================================================
# Connection settings
# ==========================================================

PING_TIMEOUT_SECONDS = 2


# ==========================================================
# Qualcomm tool executable paths
# ==========================================================

QXDM_EXECUTABLE = Path(
    r"C:\Program Files\Qualcomm\QXDM5\QXDM.exe"
)

PCAT_EXECUTABLE = Path(
    r"C:\Program Files (x86)\Qualcomm\PCAT\bin\PCATApp.exe"
)


# ==========================================================
# QXDM log mask
# ==========================================================

# Replace this path with the real default .dmc mask used by your team.
# Set it to None temporarily if you do not have the mask location yet.
QXDM_DEFAULT_MASK = None

# Example:
# QXDM_DEFAULT_MASK = Path(
#     r"C:\QXDM\Masks\default_mask.dmc"
# )


# ==========================================================
# QXDM logging settings
# ==========================================================

# Maximum allowed QXDM log size.
# 1024 MB = 1 GB.
QXDM_MAX_LOG_SIZE_MB = 1024

# Default QXDM log filename.
QXDM_DEFAULT_LOG_FILENAME = "Titan3_QXDM_Log.isf"


# ==========================================================
# QXDM automation delays
# ==========================================================

QXDM_LAUNCH_DELAY = 10
QXDM_COMMAND_DELAY = 2
QXDM_TRANSITION_DELAY = 2