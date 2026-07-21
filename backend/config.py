


from pathlib import Path


# Project folders
BACKEND_FOLDER = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_FOLDER.parent
RESULTS_FOLDER = PROJECT_ROOT / "results"


# Titan 3 defaults
DEFAULT_TITAN_IP = "192.168.1.1"
DEFAULT_TITAN_PORT = 80
DEFAULT_TITAN_PROTOCOL = "http"


# Test defaults
DEFAULT_CARRIER = "Verizon"
DEFAULT_TECHNOLOGY = "NR"
DEFAULT_MODE = "NSA"
DEFAULT_TEST_TYPE = "Wi-Fi throughput"
DEFAULT_RESULT = "PASS"


# Connection settings
PING_TIMEOUT_SECONDS = 2


# Qualcomm tool executable paths
QXDM_EXECUTABLE = Path(
    r"C:\Program Files\Qualcomm\QXDM5\QXDM.exe"
)

PCAT_EXECUTABLE = Path(
    r"C:\Program Files (x86)\Qualcomm\PCAT\bin\PCATAPP.exe"
)