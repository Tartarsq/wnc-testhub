from pathlib import Path
import subprocess
import psutil

from config import QXDM_EXECUTABLE


class QXDMController:
    """Controls launching and monitoring QXDM."""

    PROCESS_NAME = "QXDM.exe"

    def __init__(self, executable: Path = QXDM_EXECUTABLE):
        self.executable = executable
        self.process = None

    def exists(self) -> bool:
        """Return True if the QXDM executable exists."""
        return self.executable.exists()

    def is_running(self) -> bool:
        """Return True if QXDM is already running."""
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] == self.PROCESS_NAME:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    def launch(self) -> bool:
        """
        Launch QXDM if it is not already running.
        Returns True if QXDM is running afterwards.
        """
        if not self.exists():
            raise FileNotFoundError(
                f"QXDM executable not found:\n{self.executable}"
            )

        if self.is_running():
            return True

        self.process = subprocess.Popen([str(self.executable)])

        return True