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

def verify_speedtest_executable(
    executable: Path,
) -> str:
    """
    Verify that an executable is the official Ookla Speedtest CLI.

    Returns:
        The complete version output reported by the executable.

    Raises:
        FileNotFoundError:
            If the executable does not exist.

        RuntimeError:
            If the executable cannot be started, returns an error,
            or is not the official Ookla Speedtest CLI.
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


def find_speedtest_executable() -> Path:
    """
    Locate and verify the official Ookla Speedtest CLI.

    Search order:
        1. C:\\Tools\\OoklaSpeedtest
        2. Common Program Files locations
        3. Other common manual-install locations
        4. Windows PATH

    The Python speedtest-cli executable inside a virtual environment
    is ignored.
    """

    preferred_locations = [
        Path(
            r"C:\Tools\OoklaSpeedtest\speedtest.exe"
        ),
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

    candidates: list[Path] = []

    # Check known official/manual installation locations first.
    for location in preferred_locations:
        if location.is_file():
            candidates.append(
                location.resolve()
            )

    # Check Windows PATH after the preferred locations.
    for command in [
        "speedtest.exe",
        "speedtest",
    ]:
        path_result = shutil.which(command)

        if not path_result:
            continue

        path_candidate = Path(
            path_result
        ).resolve()

        path_text = str(
            path_candidate
        ).lower()

        virtual_environment_markers = [
            r"\.venv\scripts\\",
            r"\venv\scripts\\",
            r"\env\scripts\\",
            r"\virtualenv\scripts\\",
        ]

        is_virtual_environment_executable = any(
            marker in path_text
            for marker in virtual_environment_markers
        )

        if not is_virtual_environment_executable:
            candidates.append(
                path_candidate
            )

    checked_paths: set[Path] = set()
    rejected_candidates: list[str] = []

    for candidate in candidates:
        if candidate in checked_paths:
            continue

        checked_paths.add(candidate)

        try:
            verify_speedtest_executable(
                candidate
            )

            return candidate

        except (
            FileNotFoundError,
            RuntimeError,
        ) as error:
            rejected_candidates.append(
                f"{candidate}\n{error}"
            )

    rejection_details = ""

    if rejected_candidates:
        rejection_details = (
            "\n\nRejected candidates:\n"
            + "\n\n".join(
                rejected_candidates
            )
        )

    raise FileNotFoundError(
        "The official Ookla Speedtest CLI could not be found.\n\n"
        "Expected location:\n"
        r"C:\Tools\OoklaSpeedtest\speedtest.exe"
        "\n\nMake sure the official speedtest.exe is inside that folder."
        f"{rejection_details}"
    )