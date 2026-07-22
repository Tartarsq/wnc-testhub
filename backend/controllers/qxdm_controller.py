import subprocess
import time
from pathlib import Path

import psutil
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

from config import QXDM_EXECUTABLE


class QXDMController:
    """Launch QXDM and send commands through its Command box."""

    PROCESS_NAME = "QXDM.exe"
    WINDOW_TITLE_PATTERN = r".*QXDM.*"

    def __init__(self, executable: Path = QXDM_EXECUTABLE) -> None:
        self.executable = executable
        self.process: subprocess.Popen | None = None

    def executable_exists(self) -> bool:
        """Return True if the QXDM executable exists."""
        return self.executable.exists()

    def is_running(self) -> bool:
        """Return True if QXDM is running."""
        for process in psutil.process_iter(["name"]):
            try:
                process_name = process.info.get("name", "")

                if process_name.lower() == self.PROCESS_NAME.lower():
                    return True

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

        return False

    def launch(self, wait_seconds: float = 8.0) -> bool:
        """Launch QXDM if it is not already running."""
        if not self.executable_exists():
            raise FileNotFoundError(
                f"QXDM executable was not found:\n{self.executable}"
            )

        if self.is_running():
            return True

        self.process = subprocess.Popen([str(self.executable)])
        time.sleep(wait_seconds)

        return self.is_running()

    def get_window(self):
        """Locate and return the main QXDM window."""
        window = Desktop(backend="uia").window(
            title_re=self.WINDOW_TITLE_PATTERN
        )

        window.wait(
            "visible enabled ready",
            timeout=15,
        )

        return window

    def focus_qxdm(self):
        """Bring the main QXDM window to the front."""
        window = self.get_window()

        if window.is_minimized():
            window.restore()

        window.set_focus()
        time.sleep(1)

        return window

    def get_command_box(self, window):
        """
        Locate QXDM's Command combo box.

        QXDM has multiple combo boxes, so this selects the widest one
        near the top of the main window.
        """
        combo_boxes = window.descendants(control_type="ComboBox")

        if not combo_boxes:
            raise RuntimeError(
                "Could not locate any QXDM combo boxes."
            )

        window_top = window.rectangle().top
        candidates = []

        for combo_box in combo_boxes:
            rectangle = combo_box.rectangle()
            width = rectangle.width()

            # The Command box is located near the top toolbar.
            distance_from_top = rectangle.top - window_top

            if 0 <= distance_from_top <= 180:
                candidates.append((width, combo_box))

        if not candidates:
            raise RuntimeError(
                "Could not locate the QXDM Command box."
            )

        # The Command box appears to be the widest top toolbar combo box.
        candidates.sort(
            key=lambda candidate: candidate[0],
            reverse=True,
        )

        return candidates[0][1]

    def send_command(self, command: str) -> bool:
        """Enter a command in QXDM's Command box and press Enter."""
        if not self.is_running():
            if not self.launch():
                raise RuntimeError("QXDM could not be launched.")

        window = self.focus_qxdm()
        command_box = self.get_command_box(window)

        command_box.click_input()
        time.sleep(0.5)

        # Select and replace anything already inside the box.
        send_keys("^a")
        send_keys(command, with_spaces=True)
        send_keys("{ENTER}")

        time.sleep(2)

        return True

    def mode_lpm(self) -> bool:
        """Place the modem into low-power/offline mode."""
        return self.send_command("ModeLPM")

    def mode_online(self) -> bool:
        """Place the modem into online mode."""
        return self.send_command("ModeOnline")

    def start_logging(self, transition_delay: float = 2.0) -> bool:
        """
        Start the logging sequence.

        Sequence:
        ModeLPM -> ModeOnline
        """
        self.mode_lpm()
        time.sleep(transition_delay)

        self.mode_online()
        time.sleep(transition_delay)

        return True

    def stop_logging(self, wait_seconds: float = 2.0) -> bool:
        """Stop/finalize logging by entering ModeLPM."""
        self.mode_lpm()
        time.sleep(wait_seconds)

        return True