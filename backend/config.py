from pathlib import Path
import shutil
import subprocess


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


# ==========================================================
# Ookla Speedtest CLI detection
# ==========================================================

def find_speedtest_executable() -> Path:
    """
    Locate an installed Speedtest executable.

    Search order:
        1. Windows PATH
        2. Common Ookla installation folders

    This function only locates the executable. It does not verify
    whether it is the official Ookla CLI.
    """

    possible_commands = [
        "speedtest.exe",
        "speedtest",
    ]

    for command in possible_commands:
        executable = shutil.which(command)

        if executable:
            return Path(executable).resolve()

    common_locations = [
        Path(
            r"C:\Program Files\Ookla\Speedtest CLI\speedtest.exe"
        ),
        Path(
            r"C:\Program Files (x86)\Ookla\Speedtest CLI\speedtest.exe"
        ),
        Path(
            r"C:\Ookla\speedtest.exe"
        ),
    ]

    for executable in common_locations:
        if executable.is_file():
            return executable.resolve()

    raise FileNotFoundError(
        "The official Ookla Speedtest CLI could not be found.\n\n"
        "Install the official Ookla Speedtest CLI and make sure "
        "speedtest.exe is available in the Windows PATH."
    )


def verify_speedtest_executable(
    executable: Path,
) -> str:
    """
    Verify that an executable is the official Ookla Speedtest CLI.

    Returns:
        The version output reported by the executable.

    Raises:
        FileNotFoundError:
            If the supplied executable path does not exist.

        RuntimeError:
            If the executable cannot be started, returns an error,
            or appears to be the Python speedtest-cli package.
    """

    executable = Path(executable).resolve()

    if not executable.is_file():
        raise FileNotFoundError(
            "The Speedtest executable does not exist:\n"
            f"{executable}"
        )

    try:
        completed_process = subprocess.run(
            [
                str(executable),
                "--version",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            encoding="utf-8",
            errors="replace",
        )

    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "Timed out while verifying the Speedtest executable:\n"
            f"{executable}"
        ) from error

    except OSError as error:
        raise RuntimeError(
            "Windows could not start the Speedtest executable:\n"
            f"{executable}\n\n"
            f"Details: {error}"
        ) from error

    version_output = "\n".join(
        output.strip()
        for output in [
            completed_process.stdout,
            completed_process.stderr,
        ]
        if output and output.strip()
    )

    if completed_process.returncode != 0:
        raise RuntimeError(
            "Unable to determine the Speedtest version.\n\n"
            f"Executable:\n{executable}\n\n"
            f"Exit code: {completed_process.returncode}\n\n"
            f"Output:\n"
            f"{version_output or 'No output was returned.'}"
        )

    normalized_output = version_output.lower()

    if "speedtest-cli" in normalized_output:
        raise RuntimeError(
            "The detected executable is the Python speedtest-cli "
            "package, not the official Ookla Speedtest CLI.\n\n"
            f"Executable:\n{executable}\n\n"
            f"Detected version:\n{version_output}"
        )

    if "ookla" not in normalized_output:
        raise RuntimeError(
            "The detected executable could not be verified as the "
            "official Ookla Speedtest CLI.\n\n"
            f"Executable:\n{executable}\n\n"
            f"Detected version:\n{version_output}"
        )

    return version_output