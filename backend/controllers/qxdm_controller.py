import json
import subprocess
import time
from pathlib import Path
from typing import Optional

import psutil
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

from config import (
    QXDM_EXECUTABLE,
    QXDM_DEFAULT_MASK,
    QXDM_MAX_LOG_SIZE_MB,
)


class QXDMController:
    """
    Automate the basic QXDM logging workflow.

    Workflow:
        1. Create the output directory.
        2. Launch QXDM.
        3. Load the default log mask, when available.
        4. Open the logging configuration.
        5. Set the output path.
        6. Set the maximum log size.
        7. Start QXDM logging.
        8. Send mode lpm.
        9. Send mode online.
       10. Stop capture and finalize the log.
       11. Reopen the completed log in QXDM.
    """

    PROCESS_NAME = "QXDM.exe"
    WINDOW_TITLE_PATTERN = r".*QXDM.*"

    # QXDM menu names may differ by version.
    START_LOGGING_MENU_PATHS = [
        "File->Start Logging",
        "Logging->Start Logging",
        "Log->Start Logging",
        "Tools->Start Logging",
    ]

    STOP_LOGGING_MENU_PATHS = [
        "File->Stop Logging",
        "Logging->Stop Logging",
        "Log->Stop Logging",
        "Tools->Stop Logging",
    ]

    LOAD_MASK_MENU_PATHS = [
        "File->Load Configuration",
        "File->Load Log Mask",
        "File->Open Configuration",
        "Logging->Load Log Mask",
        "Tools->Load Log Mask",
    ]

    # Used after capture stops so the completed log becomes the active log
    # displayed in QXDM. Menu wording varies between QXDM versions.
    OPEN_LOG_MENU_PATHS = [
        "File->Open Log",
        "File->Open Log File",
        "File->Open",
        "Log->Open Log",
        "Logging->Open Log",
    ]

    def __init__(
        self,
        executable: Path = QXDM_EXECUTABLE,
        default_mask: Optional[Path] = QXDM_DEFAULT_MASK,
        max_log_size_mb: int = QXDM_MAX_LOG_SIZE_MB,
    ) -> None:
        self.executable = Path(executable)

        self.default_mask = (
            Path(default_mask)
            if default_mask is not None
            else None
        )

        # Never allow the requested size to exceed 1 GB.
        self.max_log_size_mb = min(
            max(int(max_log_size_mb), 1),
            1024,
        )

        self.process: subprocess.Popen | None = None
        self.current_log_path: Optional[Path] = None

        # Stores the last successfully selected QXDM mask.
        self.mask_settings_path = (
            Path.home()
            / ".wnc_testhub"
            / "qxdm_settings.json"
        )

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

    def prepare_log_path(self, log_path: Path) -> Path:
        """
        Create the QXDM output directory before logging starts.

        The supplied path should include the desired log filename.
        """
        log_path = Path(log_path).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        self.current_log_path = log_path

        return log_path

    def launch(self, wait_seconds: float = 8.0) -> bool:
        """Launch QXDM if it is not already running."""
        if not self.executable_exists():
            raise FileNotFoundError(
                f"QXDM executable was not found:\n{self.executable}"
            )

        if self.is_running():
            self.focus_qxdm()
            return True

        self.process = subprocess.Popen(
            [str(self.executable)],
            cwd=str(self.executable.parent),
        )

        time.sleep(wait_seconds)

        if not self.is_running():
            raise RuntimeError(
                "QXDM did not start successfully."
            )

        self.focus_qxdm()
        return True

    def get_window(self):
        """Locate and return the main QXDM window."""
        window = Desktop(backend="uia").window(
            title_re=self.WINDOW_TITLE_PATTERN
        )

        window.wait(
            "visible enabled ready",
            timeout=20,
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

    def select_first_available_menu(
        self,
        window,
        menu_paths: list[str],
    ) -> str:
        """
        Try several possible menu paths.

        Returns the path that worked.
        """
        errors = []

        for menu_path in menu_paths:
            try:
                window.menu_select(menu_path)
                time.sleep(1)
                return menu_path

            except Exception as error:
                errors.append(
                    f"{menu_path}: {error}"
                )

        raise RuntimeError(
            "Could not locate the required QXDM menu item.\n"
            "Tried:\n"
            + "\n".join(errors)
        )

    def find_dialog(self, title_pattern: str = r".*"):

        dialog = Desktop(backend="uia").window(
            title_re=title_pattern,
            top_level_only=True,
        )

        dialog.wait(
            "visible enabled ready",
            timeout=10,
        )

        return dialog

    def find_edit_by_keywords(
        self,
        dialog,
        keywords: list[str],
    ):
        """
        Find an Edit control whose nearby label contains a keyword.
        """
        edit_controls = dialog.descendants(
            control_type="Edit"
        )

        for edit in edit_controls:
            try:
                parent = edit.parent()
                parent_text = " ".join(
                    parent.texts()
                ).lower()

                if any(
                    keyword.lower() in parent_text
                    for keyword in keywords
                ):
                    return edit

            except Exception:
                continue

        return None

    def set_edit_value(
        self,
        edit_control,
        value: str,
    ) -> None:
        """Replace the contents of an Edit control."""
        edit_control.click_input()
        time.sleep(0.3)

        send_keys("^a")
        send_keys(
            value,
            with_spaces=True,
            pause=0.01,
        )

    def click_button_by_keywords(
        self,
        dialog,
        keywords: list[str],
    ) -> bool:
        """Click the first button matching one of the keywords."""
        buttons = dialog.descendants(
            control_type="Button"
        )

        for button in buttons:
            try:
                button_text = button.window_text().strip().lower()

                if any(
                    keyword.lower() == button_text
                    or keyword.lower() in button_text
                    for keyword in keywords
                ):
                    button.click_input()
                    time.sleep(1)
                    return True

            except Exception:
                continue

        return False

    def handle_file_dialog(
        self,
        file_path: Path,
    ) -> bool:
        """Fill in a standard Windows Open/Save dialog."""
        file_path = Path(file_path).resolve()

        dialog = Desktop(backend="uia").window(
            title_re=r".*(Open|Save|Browse|Select).*",
            top_level_only=True,
        )

        dialog.wait(
            "visible enabled ready",
            timeout=10,
        )

        file_name_edit = self.find_edit_by_keywords(
            dialog,
            [
                "file name",
                "filename",
                "name",
            ],
        )

        if file_name_edit is None:
            edit_controls = dialog.descendants(
                control_type="Edit"
            )

            if not edit_controls:
                raise RuntimeError(
                    "Could not locate the file path field."
                )

            file_name_edit = edit_controls[-1]

        self.set_edit_value(
            file_name_edit,
            str(file_path),
        )

        if not self.click_button_by_keywords(
            dialog,
            ["open", "save", "select", "ok"],
        ):
            send_keys("{ENTER}")

        time.sleep(2)
        return True

    def _load_saved_mask_path(self) -> Optional[Path]:
        """Return the last selected mask path when it still exists."""
        if not self.mask_settings_path.exists():
            return None

        try:
            settings = json.loads(
                self.mask_settings_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
        ):
            return None

        saved_value = settings.get("qxdm_default_mask")

        if not saved_value:
            return None

        saved_path = Path(saved_value).expanduser()

        if not saved_path.exists() or not saved_path.is_file():
            return None

        return saved_path.resolve()

    def _save_mask_path(self, mask_path: Path) -> None:
        """Remember the selected mask for the next test run."""
        mask_path = Path(mask_path).resolve()

        self.mask_settings_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.mask_settings_path.write_text(
            json.dumps(
                {
                    "qxdm_default_mask": str(mask_path),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _prompt_for_mask(self) -> Path:
        """Ask the user to select a QXDM mask/configuration file."""
        try:
            from tkinter import Tk
            from tkinter.filedialog import askopenfilename
        except ImportError as error:
            raise RuntimeError(
                "A QXDM mask must be selected, but the Windows "
                "file picker is unavailable."
            ) from error

        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        try:
            selected_file = askopenfilename(
                parent=root,
                title="Select QXDM Default Mask",
                filetypes=[
                    (
                        "QXDM mask/configuration files",
                        "*.dmc *.cfg *.xml *.qcn *.txt",
                    ),
                    ("All files", "*.*"),
                ],
            )
        finally:
            root.destroy()

        if not selected_file:
            raise RuntimeError(
                "No QXDM mask was selected. "
                "The test was not started."
            )

        selected_mask = Path(selected_file).resolve()

        if not selected_mask.exists() or not selected_mask.is_file():
            raise FileNotFoundError(
                "The selected QXDM mask was not found:\n"
                f"{selected_mask}"
            )

        self.default_mask = selected_mask
        self._save_mask_path(selected_mask)

        return selected_mask

    def _open_mask_file(self, mask_path: Path) -> bool:
        """Open a specific mask file through the QXDM user interface."""
        mask_path = Path(mask_path).resolve()

        if not mask_path.exists() or not mask_path.is_file():
            raise FileNotFoundError(
                "The QXDM mask was not found:\n"
                f"{mask_path}"
            )

        window = self.focus_qxdm()

        selected_menu = self.select_first_available_menu(
            window,
            self.LOAD_MASK_MENU_PATHS,
        )

        print(
            f"Opened QXDM mask menu: {selected_menu}"
        )
        print(
            f"Loading QXDM mask: {mask_path}"
        )

        self.handle_file_dialog(mask_path)

        # Give QXDM time to apply the selected packet mask before logging starts.
        time.sleep(3)

        self.default_mask = mask_path
        self._save_mask_path(mask_path)

        print(
            f"Loaded QXDM mask: {mask_path}"
        )

        return True

    def load_default_mask(self) -> bool:
        """
        Load the configured QXDM mask.

        Resolution order:
            1. Mask supplied through config.py or the constructor.
            2. Last mask selected by the user.
            3. File picker.

        If automatic loading fails, the user is asked to choose a mask.
        Logging does not continue until a mask loads successfully.
        """
        candidates: list[Path] = []

        if self.default_mask is not None:
            candidates.append(
                Path(self.default_mask).expanduser()
            )

        saved_mask = self._load_saved_mask_path()

        if (
            saved_mask is not None
            and all(
                saved_mask.resolve() != candidate.resolve()
                for candidate in candidates
                if candidate.exists()
            )
        ):
            candidates.append(saved_mask)

        last_error: Optional[Exception] = None

        for candidate in candidates:
            if not candidate.exists() or not candidate.is_file():
                print(
                    "QXDM mask path is unavailable: "
                    f"{candidate}"
                )
                continue

            try:
                return self._open_mask_file(candidate)
            except Exception as error:
                last_error = error
                print(
                    "Automatic QXDM mask loading failed for "
                    f"{candidate}: {error}"
                )

        if last_error is not None:
            print(
                "Please select a QXDM mask manually."
            )
        else:
            print(
                "No usable default QXDM mask was found. "
                "Please select one."
            )

        selected_mask = self._prompt_for_mask()

        try:
            return self._open_mask_file(selected_mask)
        except Exception as error:
            raise RuntimeError(
                "The selected QXDM mask could not be loaded. "
                "The test was not started."
            ) from error

    def open_start_logging_dialog(self):
        """Open QXDM's Start Logging dialog."""
        window = self.focus_qxdm()

        selected_menu = self.select_first_available_menu(
            window,
            self.START_LOGGING_MENU_PATHS,
        )

        print(
            f"Opened QXDM logging menu: {selected_menu}"
        )

        time.sleep(1)

        return self.find_dialog(
            title_pattern=r".*(Log|Logging|Save|Capture).*"
        )

    def configure_logging(
        self,
        log_path: Path,
    ) -> bool:
        """
        Set the QXDM log destination and maximum file size.

        The destination directory is created before the dialog opens.
        """
        log_path = self.prepare_log_path(
            log_path
        )

        dialog = self.open_start_logging_dialog()

        path_edit = self.find_edit_by_keywords(
            dialog,
            [
                "file",
                "path",
                "location",
                "output",
                "destination",
                "log name",
            ],
        )

        if path_edit is not None:
            self.set_edit_value(
                path_edit,
                str(log_path),
            )

        else:
            browse_clicked = self.click_button_by_keywords(
                dialog,
                [
                    "browse",
                    "select",
                    "choose",
                ],
            )

            if not browse_clicked:
                raise RuntimeError(
                    "Could not locate the QXDM log file "
                    "location field or Browse button."
                )

            self.handle_file_dialog(
                log_path
            )

            # The logging dialog may still be active.
            dialog = self.find_dialog(
                title_pattern=r".*(Log|Logging|Save|Capture).*"
            )

        size_edit = self.find_edit_by_keywords(
            dialog,
            [
                "maximum size",
                "max size",
                "file size",
                "log size",
                "size limit",
            ],
        )

        if size_edit is None:
            raise RuntimeError(
                "Could not locate the QXDM maximum "
                "log-size field."
            )

        self.set_edit_value(
            size_edit,
            str(self.max_log_size_mb),
        )

        print(
            f"QXDM log destination: {log_path}"
        )
        print(
            "QXDM maximum log size: "
            f"{self.max_log_size_mb} MB"
        )

        if not self.click_button_by_keywords(
            dialog,
            [
                "start",
                "begin",
                "ok",
                "apply",
            ],
        ):
            raise RuntimeError(
                "Could not locate the QXDM Start "
                "Logging button."
            )

        time.sleep(2)
        return True

    def get_command_box(self, window):
        """
        Locate QXDM's Command combo box.

        QXDM has multiple combo boxes, so this selects the widest one
        near the top of the main window.
        """
        combo_boxes = window.descendants(
            control_type="ComboBox"
        )

        if not combo_boxes:
            raise RuntimeError(
                "Could not locate any QXDM combo boxes."
            )

        window_top = window.rectangle().top
        candidates = []

        for combo_box in combo_boxes:
            rectangle = combo_box.rectangle()
            width = rectangle.width()

            distance_from_top = (
                rectangle.top - window_top
            )

            if 0 <= distance_from_top <= 180:
                candidates.append(
                    (width, combo_box)
                )

        if not candidates:
            raise RuntimeError(
                "Could not locate the QXDM Command box."
            )

        candidates.sort(
            key=lambda candidate: candidate[0],
            reverse=True,
        )

        return candidates[0][1]

    def send_command(self, command: str) -> bool:
        """Enter a command in QXDM's Command box."""
        if not self.is_running():
            self.launch()

        window = self.focus_qxdm()
        command_box = self.get_command_box(
            window
        )

        command_box.click_input()
        time.sleep(0.5)

        send_keys("^a")
        send_keys(
            command,
            with_spaces=True,
        )
        send_keys("{ENTER}")

        time.sleep(2)
        return True

    def mode_lpm(self) -> bool:
        """Place the modem into low-power mode."""
        print("Sending mode lpm...")
        return self.send_command("mode lpm")

    def mode_online(self) -> bool:
        """Place the modem into online mode."""
        print("Sending mode online...")
        return self.send_command("mode online")

    def start_logging(
        self,
        log_path: Path,
        transition_delay: float = 2.0,
        load_mask: bool = True,
    ) -> bool:
        """
        Run the complete QXDM startup sequence.

        Sequence:
            Create output directory
            Launch QXDM
            Load mask
            Set destination
            Set maximum size
            Start QXDM logging
            mode lpm
            mode online
        """
        self.prepare_log_path(log_path)
        self.launch()

        if load_mask:
            self.load_default_mask()

        self.configure_logging(log_path)

        self.mode_lpm()
        time.sleep(transition_delay)

        self.mode_online()
        time.sleep(transition_delay)

        print("QXDM logging sequence started.")
        return True

    def stop_qxdm_capture(self) -> bool:
        """Use the QXDM menu to stop capture."""
        window = self.focus_qxdm()

        selected_menu = self.select_first_available_menu(
            window,
            self.STOP_LOGGING_MENU_PATHS,
        )

        print(
            f"Stopped QXDM using: {selected_menu}"
        )

        time.sleep(2)
        return True

    def _find_completed_log(self) -> Optional[Path]:
        """Return the completed log file created for the current capture.

        QXDM may append an extension or create a numbered/segmented file, so
        this checks the exact configured path first and then nearby matches.
        """
        if self.current_log_path is None:
            return None

        expected_path = self.current_log_path

        if expected_path.exists() and expected_path.is_file():
            return expected_path

        candidates = [
            path
            for path in expected_path.parent.glob(f"{expected_path.stem}*")
            if path.is_file()
        ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda path: path.stat().st_mtime,
        )

    def wait_for_saved_log(
        self,
        timeout_seconds: float = 20.0,
        poll_interval: float = 0.5,
    ) -> Path:
        """Wait until QXDM has finalized the log on disk.

        Stopping capture is what saves/finalizes a QXDM log because the output
        destination was selected before logging started. This method confirms
        that the resulting file exists and that its size has stopped changing.
        """
        if self.current_log_path is None:
            raise RuntimeError(
                "No QXDM log path has been configured."
            )

        deadline = time.monotonic() + timeout_seconds
        previous_size: Optional[int] = None
        stable_checks = 0

        while time.monotonic() < deadline:
            completed_log = self._find_completed_log()

            if completed_log is not None:
                try:
                    current_size = completed_log.stat().st_size
                except OSError:
                    time.sleep(poll_interval)
                    continue

                if current_size == previous_size:
                    stable_checks += 1
                else:
                    previous_size = current_size
                    stable_checks = 0

                # Two unchanged checks reduce the chance of reopening a file
                # while QXDM is still flushing its final data.
                if stable_checks >= 2:
                    self.current_log_path = completed_log
                    print(f"QXDM log saved: {completed_log}")
                    return completed_log

            time.sleep(poll_interval)

        raise TimeoutError(
            "QXDM stopped capture, but the completed log file was not "
            f"confirmed within {timeout_seconds:.1f} seconds. Expected near: "
            f"{self.current_log_path}"
        )

    def load_saved_log(
        self,
        log_path: Optional[Path] = None,
    ) -> bool:
        """Open a completed log so it becomes QXDM's active/default view."""
        selected_log = (
            Path(log_path).resolve()
            if log_path is not None
            else self._find_completed_log()
        )

        if selected_log is None or not selected_log.exists():
            raise FileNotFoundError(
                "Could not find the completed QXDM log to reopen."
            )

        window = self.focus_qxdm()
        selected_menu = self.select_first_available_menu(
            window,
            self.OPEN_LOG_MENU_PATHS,
        )

        print(f"Opened QXDM log menu: {selected_menu}")
        self.handle_file_dialog(selected_log)
        self.current_log_path = selected_log
        print(f"Loaded completed QXDM log: {selected_log}")
        return True

    def stop_logging(
        self,
        wait_seconds: float = 2.0,
        load_saved_log: bool = True,
        save_timeout_seconds: float = 20.0,
    ) -> bool:
        """Stop capture, finalize the log, and optionally reopen it in QXDM."""
        self.mode_lpm()
        time.sleep(wait_seconds)

        self.stop_qxdm_capture()
        completed_log = self.wait_for_saved_log(
            timeout_seconds=save_timeout_seconds,
        )

        if load_saved_log:
            self.load_saved_log(completed_log)

        print("QXDM logging stopped and finalized.")
        return True

    def print_controls(self) -> None:
        """
        Print QXDM UI controls for troubleshooting.

        Run this if the logging dialog fields cannot be found.
        """
        window = self.focus_qxdm()
        window.print_control_identifiers()