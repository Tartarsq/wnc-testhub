from pathlib import Path
import subprocess
import psutil

from config import PCAT_EXECUTABLE


class PCATController:
    """Controls launching and monitoring Qualcomm PCAT."""

    PROCESS_NAME = "PCATApp.exe"

    def __init__(self, executable: Path = PCAT_EXECUTABLE):
        self.executable = executable
        self.process = None

    def exists(self) -> bool:
        """Return True if the PCAT executable exists."""
        return self.executable.exists()

    def is_running(self) -> bool:
        """Return True if PCAT is already running."""
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] == self.PROCESS_NAME:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return False

    def launch(self) -> bool:
        """
        Launch PCAT if it is not already running.
        Returns True if PCAT is running afterwards.
        """
        if not self.exists():
            raise FileNotFoundError(
                f"PCAT executable not found:\n{self.executable}"
            )

        if self.is_running():
            return True

        self.process = subprocess.Popen(
            [str(self.executable)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return True

    def close(self) -> bool:
        """Close PCAT if it was launched by this controller."""
        if self.process is not None:
            self.process.terminate()
            self.process.wait(timeout=10)
            self.process = None
            return True

        return False