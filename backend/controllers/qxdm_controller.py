import json
import subprocess
import time

import cv2
import numpy as np
from PIL import ImageGrab
from pathlib import Path
from typing import Optional

import psutil
from pywinauto import Application, Desktop, mouse
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

    COMMAND_TEMPLATE_PATH = (
        Path(__file__).resolve().parent
        / "qxdm_command_bar.png"
    )
    COMMAND_TEMPLATE_THRESHOLD = 0.78
    COMMAND_INPUT_X_RATIO = 0.56
    COMMAND_INPUT_Y_RATIO = 0.52

    # QXDM 5.2.640 Settings dialog positions, expressed as ratios
    # of the Settings window. These match the Item Store File layout.
    SETTINGS_ITEM_STORE_X_RATIO = 0.14
    SETTINGS_ITEM_STORE_Y_RATIO = 0.06
    SETTINGS_QUICK_SAVE_X_RATIO = 0.285
    SETTINGS_QUICK_SAVE_Y_RATIO = 0.105
    SETTINGS_BASE_NAME_X_RATIO = 0.55
    SETTINGS_BASE_NAME_Y_RATIO = 0.145
    SETTINGS_LOG_DIRECTORY_X_RATIO = 0.55
    SETTINGS_LOG_DIRECTORY_Y_RATIO = 0.19
    SETTINGS_ADVANCED_MODE_X_RATIO = 0.305
    SETTINGS_ADVANCED_MODE_Y_RATIO = 0.625
    SETTINGS_MAX_SIZE_X_RATIO = 0.74
    SETTINGS_MAX_SIZE_Y_RATIO = 0.665
    SETTINGS_AUTO_SAVE_X_RATIO = 0.325
    SETTINGS_AUTO_SAVE_Y_RATIO = 0.74
    SETTINGS_LOG_PATH_X_RATIO = 0.55
    SETTINGS_LOG_PATH_Y_RATIO = 0.945

    # QXDM is a Qt application and does not expose its internal controls
    # through pywinauto. These ratios point to the Command field relative
    # to the QXDM window. They match the QXDM 5.2.640 layout shown by the
    # user and can be adjusted later if the toolbar layout changes.
    # In the maximized 1708px-wide window, this lands near x=734, which
    # is inside the editable Command field rather than the toolbar buttons.
    # QXDM 5.2.640 toolbar geometry after maximizing the window.
    # The editable command area begins just after the "Command:" label.
    COMMAND_BOX_X_OFFSET = 700
    COMMAND_BOX_Y_OFFSET = 74

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
        "File->Load Configuration...",
        "File->Load Configuration",
    ]

    SETTINGS_MENU_PATHS = [
        "Options->Settings...",
        "Options->Settings",
        "Tools->Settings",
        "View->Settings",
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

        # Remember the last mask selected by the user. This allows future test
        # runs to load it automatically, while still falling back to a picker
        # if the file is moved, deleted, or cannot be loaded.
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

    def launch(self, wait_seconds: float = 12.0) -> bool:
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
        """
        Locate and return the main QXDM window.

        QXDM can launch its Qt window several seconds after QXDM.exe
        starts, and the final window may not be owned by the first PID.
        This method retries for 60 seconds and searches all top-level
        Win32 windows before falling back to process-based connection.
        """
        deadline = time.monotonic() + 60.0
        last_error = None

        while time.monotonic() < deadline:
            desktop = Desktop(
                backend="win32"
            )

            # Most reliable path for this Qt build: enumerate every
            # top-level window and select a visible title containing QXDM.
            try:
                for candidate in desktop.windows(
                    visible_only=False,
                    enabled_only=False,
                ):
                    try:
                        title = (
                            candidate.window_text()
                            or ""
                        ).strip()

                        if "qxdm" not in title.lower():
                            continue

                        if not candidate.is_visible():
                            continue

                        candidate.wait(
                            "visible",
                            timeout=3,
                        )

                        print(
                            "Located QXDM main window: "
                            f"{title}"
                        )

                        return candidate

                    except Exception:
                        continue

            except Exception as error:
                last_error = error

            # Fallback: connect to every running QXDM process and inspect
            # all windows owned by that process.
            for process in psutil.process_iter(
                ["pid", "name"]
            ):
                try:
                    process_name = (
                        process.info.get("name")
                        or ""
                    )

                    if (
                        process_name.lower()
                        != self.PROCESS_NAME.lower()
                    ):
                        continue

                    process_id = int(
                        process.info["pid"]
                    )

                    try:
                        application = Application(
                            backend="win32"
                        ).connect(
                            process=process_id,
                            timeout=3,
                        )

                        for candidate in application.windows():
                            title = (
                                candidate.window_text()
                                or ""
                            ).strip()

                            if "qxdm" not in title.lower():
                                continue

                            if not candidate.is_visible():
                                continue

                            print(
                                "Located QXDM window through process "
                                f"{process_id}: {title}"
                            )

                            return candidate

                    except Exception as error:
                        last_error = error

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                    ValueError,
                ):
                    continue

            time.sleep(1)

        raise RuntimeError(
            "QXDM opened, but no visible QXDM window could be found "
            "within 60 seconds. Make sure the backend terminal and QXDM "
            "are both running normally or both running as administrator."
        ) from last_error

    def focus_qxdm(self):
        """Bring the main QXDM window to the front."""
        window = self.get_window()

        if window.is_minimized():
            window.restore()

        window.set_focus()
        time.sleep(1)

        return window

    def open_qxdm_settings(self):
        """
        Open QXDM using:

            Options -> Settings...

        Then locate the Settings window by enumerating visible Win32
        top-level windows instead of using unsupported lookup arguments.
        """
        window = self.focus_qxdm()

        try:
            window.maximize()
            time.sleep(1)
            window.set_focus()
        except Exception:
            pass

        rectangle = window.rectangle()

        # Open the Options menu.
        options_x = rectangle.left + 105
        options_y = rectangle.top + 40

        mouse.click(
            button="left",
            coords=(options_x, options_y),
        )
        time.sleep(0.8)

        # Click Settings..., the second menu entry.
        settings_x = rectangle.left + 125
        settings_y = rectangle.top + 83

        mouse.click(
            button="left",
            coords=(settings_x, settings_y),
        )
        time.sleep(1.5)

        deadline = time.monotonic() + 20.0
        last_error = None

        while time.monotonic() < deadline:
            try:
                desktop = Desktop(
                    backend="win32"
                )

                for candidate in desktop.windows(
                    visible_only=False,
                    enabled_only=False,
                ):
                    try:
                        title = (
                            candidate.window_text()
                            or ""
                        ).strip()

                        if "settings" not in title.lower():
                            continue

                        if not candidate.is_visible():
                            continue

                        candidate.wait(
                            "visible",
                            timeout=3,
                        )

                        try:
                            candidate.set_focus()
                        except Exception:
                            pass

                        print(
                            "Located QXDM Settings window: "
                            f"{title}"
                        )

                        time.sleep(1)
                        return candidate

                    except Exception:
                        continue

            except Exception as error:
                last_error = error

            time.sleep(0.5)

        raise RuntimeError(
            "QXDM Options -> Settings was clicked, but no visible "
            "Settings window was found within 20 seconds."
        ) from last_error

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

        dialog = Desktop(backend="win32").window(
            title_re=title_pattern,
            top_level_only=True,
        )

        dialog.wait(
            "visible enabled",
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

        dialog = Desktop(backend="win32").window(
            title_re=r".*(Open|Save|Browse|Select).*",
            top_level_only=True,
        )

        dialog.wait(
            "visible enabled",
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

    def load_saved_mask_preference(self) -> Optional[Path]:
        """Return the last user-selected mask path, when it still exists."""
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
        ) as error:
            print(
                "Could not read the saved QXDM mask preference: "
                f"{error}"
            )
            return None

        saved_value = settings.get("qxdm_default_mask")

        if not saved_value:
            return None

        saved_path = Path(saved_value).expanduser()

        if not saved_path.exists() or not saved_path.is_file():
            print(
                "The previously selected QXDM mask is no longer "
                f"available: {saved_path}"
            )
            return None

        return saved_path.resolve()

    def save_mask_preference(
        self,
        mask_path: Path,
    ) -> None:
        """Persist the selected mask path for future test runs."""
        mask_path = Path(mask_path).resolve()

        self.mask_settings_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        settings = {
            "qxdm_default_mask": str(mask_path),
        }

        self.mask_settings_path.write_text(
            json.dumps(settings, indent=2),
            encoding="utf-8",
        )

        print(
            "Saved QXDM mask preference: "
            f"{mask_path}"
        )

    def prompt_for_default_mask(
        self,
        allow_cancel: bool = False,
    ) -> Optional[Path]:
        """
        Ask the user to select a QXDM mask or configuration file.

        When allow_cancel is True, cancelling the picker returns None so
        logging can continue without loading a mask.
        """
        try:
            from tkinter import Tk
            from tkinter.filedialog import askopenfilename
        except ImportError as error:
            if allow_cancel:
                print(
                    "Tkinter is unavailable. Continuing without "
                    "loading a QXDM mask."
                )
                return None

            raise RuntimeError(
                "The QXDM mask could not be loaded automatically, "
                "and the Tkinter file picker is unavailable."
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
            if allow_cancel:
                print(
                    "No QXDM mask was selected. "
                    "Continuing without a mask."
                )
                return None

            raise RuntimeError(
                "No QXDM mask was selected. "
                "The test was not started."
            )

        selected_mask = Path(selected_file).resolve()

        if not selected_mask.exists() or not selected_mask.is_file():
            if allow_cancel:
                print(
                    "The selected QXDM mask was not available. "
                    "Continuing without a mask."
                )
                return None

            raise FileNotFoundError(
                "The selected QXDM mask was not found:\n"
                f"{selected_mask}"
            )

        self.default_mask = selected_mask
        self.save_mask_preference(selected_mask)

        print(
            "Selected QXDM mask: "
            f"{selected_mask}"
        )

        return selected_mask

    def resolve_default_mask(self) -> Optional[Path]:
        """
        Resolve the mask to use without opening the picker when possible.

        Priority:
            1. The mask supplied through config.py or the constructor.
            2. The last mask selected by the user.
            3. No mask, which causes the caller to open the picker.
        """
        if self.default_mask is not None:
            configured_mask = Path(
                self.default_mask
            ).expanduser()

            if configured_mask.exists() and configured_mask.is_file():
                self.default_mask = configured_mask.resolve()
                return self.default_mask

            print(
                "Configured QXDM mask was not found: "
                f"{configured_mask}"
            )

        saved_mask = self.load_saved_mask_preference()

        if saved_mask is not None:
            self.default_mask = saved_mask
            print(
                "Using previously selected QXDM mask: "
                f"{saved_mask}"
            )
            return saved_mask

        self.default_mask = None
        return None

    def ensure_default_mask_loaded(
        self,
        retry_with_picker: bool = True,
        continue_without_mask: bool = False,
    ) -> bool:
        """
        Load the configured or remembered mask.

        If continue_without_mask is True, cancelling the picker or failing
        to load a selected mask does not stop logging.
        """
        resolved_mask = self.resolve_default_mask()

        if resolved_mask is None:
            selected_mask = self.prompt_for_default_mask(
                allow_cancel=continue_without_mask,
            )

            if selected_mask is None:
                return False

            try:
                return self.load_default_mask()
            except Exception as error:
                if continue_without_mask:
                    print(
                        "The selected QXDM mask could not be loaded. "
                        "Continuing without a mask. "
                        f"Details: {error}"
                    )
                    return False
                raise

        try:
            loaded = self.load_default_mask()

            if loaded:
                self.save_mask_preference(self.default_mask)
                return True

        except Exception as error:
            if not retry_with_picker:
                if continue_without_mask:
                    print(
                        "Automatic QXDM mask loading failed. "
                        "Continuing without a mask. "
                        f"Details: {error}"
                    )
                    return False
                raise

            print(
                "Automatic QXDM mask loading failed: "
                f"{error}"
            )
            print(
                "Please select a QXDM mask manually."
            )

        if not retry_with_picker:
            if continue_without_mask:
                return False

            raise RuntimeError(
                "The QXDM mask could not be loaded."
            )

        selected_mask = self.prompt_for_default_mask(
            allow_cancel=continue_without_mask,
        )

        if selected_mask is None:
            return False

        try:
            return self.load_default_mask()
        except Exception as error:
            if continue_without_mask:
                print(
                    "The manually selected QXDM mask could not be "
                    "loaded. Continuing without a mask. "
                    f"Details: {error}"
                )
                return False

            raise RuntimeError(
                "The manually selected QXDM mask could not be loaded. "
                "The test was not started."
            ) from error

    def load_default_mask(self) -> bool:
        """
        Load the configured .dmc file using QXDM's exact command:

            File -> Load Configuration...  (Ctrl+O)
        """
        if self.default_mask is None:
            print(
                "No default QXDM configuration was selected."
            )
            return False

        if not self.default_mask.exists():
            raise FileNotFoundError(
                "The default QXDM configuration was not found:\n"
                f"{self.default_mask}"
            )

        window = self.focus_qxdm()

        try:
            window.maximize()
            time.sleep(1)
            window.set_focus()
        except Exception:
            pass

        # QXDM's File menu shows Ctrl+O for Load Configuration...
        send_keys("^o")
        time.sleep(1.5)

        self.handle_file_dialog(
            self.default_mask
        )

        # Give QXDM time to apply the DMC configuration.
        time.sleep(4)

        print(
            "Loaded QXDM configuration: "
            f"{self.default_mask}"
        )

        return True

    def _settings_point(
        self,
        dialog,
        x_ratio: float,
        y_ratio: float,
    ) -> tuple[int, int]:
        """Convert Settings-dialog ratios into screen coordinates."""
        rectangle = dialog.rectangle()

        x = int(
            rectangle.left
            + rectangle.width() * x_ratio
        )
        y = int(
            rectangle.top
            + rectangle.height() * y_ratio
        )

        return x, y

    def _click_settings_point(
        self,
        dialog,
        x_ratio: float,
        y_ratio: float,
    ) -> None:
        """Click a position inside the QXDM Settings dialog."""
        x, y = self._settings_point(
            dialog,
            x_ratio,
            y_ratio,
        )

        mouse.click(
            button="left",
            coords=(x, y),
        )
        time.sleep(0.5)

    def _replace_active_text(
        self,
        value: str,
    ) -> None:
        """Replace text in the currently focused Settings field."""
        send_keys("^a")
        time.sleep(0.1)
        send_keys("{BACKSPACE}")
        time.sleep(0.1)
        send_keys(
            value,
            with_spaces=True,
            pause=0.03,
        )

    def configure_logging(
        self,
        log_path: Path,
    ) -> bool:
        """
        Configure QXDM Quick Saving through:

            Options > Settings... > Item Store File

        The Settings dialog is a Qt window, so its fields are addressed
        using positions relative to the Settings window.
        """
        log_path = self.prepare_log_path(
            log_path
        )

        dialog = self.open_qxdm_settings()

        try:
            dialog.set_focus()
        except Exception:
            pass

        time.sleep(1)

        # Select Item Store File.
        self._click_settings_point(
            dialog,
            self.SETTINGS_ITEM_STORE_X_RATIO,
            self.SETTINGS_ITEM_STORE_Y_RATIO,
        )

        # Enable Quick Saving.
        self._click_settings_point(
            dialog,
            self.SETTINGS_QUICK_SAVE_X_RATIO,
            self.SETTINGS_QUICK_SAVE_Y_RATIO,
        )

        # Set base filename.
        self._click_settings_point(
            dialog,
            self.SETTINGS_BASE_NAME_X_RATIO,
            self.SETTINGS_BASE_NAME_Y_RATIO,
        )
        self._replace_active_text(
            log_path.name
        )

        # Set log directory.
        self._click_settings_point(
            dialog,
            self.SETTINGS_LOG_DIRECTORY_X_RATIO,
            self.SETTINGS_LOG_DIRECTORY_Y_RATIO,
        )
        self._replace_active_text(
            str(log_path.parent)
        )

        # Select Advanced Mode.
        self._click_settings_point(
            dialog,
            self.SETTINGS_ADVANCED_MODE_X_RATIO,
            self.SETTINGS_ADVANCED_MODE_Y_RATIO,
        )

        # Set the maximum log size.
        self._click_settings_point(
            dialog,
            self.SETTINGS_MAX_SIZE_X_RATIO,
            self.SETTINGS_MAX_SIZE_Y_RATIO,
        )
        send_keys("^a")
        send_keys("{BACKSPACE}")

        size_value = (
            "1.0 Gigabytes"
            if self.max_log_size_mb >= 1024
            else f"{self.max_log_size_mb} Megabytes"
        )

        send_keys(
            size_value,
            with_spaces=True,
            pause=0.03,
        )
        send_keys("{ENTER}")

        # Enable automatic saving when the size limit is reached.
        self._click_settings_point(
            dialog,
            self.SETTINGS_AUTO_SAVE_X_RATIO,
            self.SETTINGS_AUTO_SAVE_Y_RATIO,
        )

        # Set the explicit log-file path.
        self._click_settings_point(
            dialog,
            self.SETTINGS_LOG_PATH_X_RATIO,
            self.SETTINGS_LOG_PATH_Y_RATIO,
        )
        self._replace_active_text(
            str(log_path)
        )

        print(
            f"QXDM base filename configured: {log_path.name}"
        )
        print(
            f"QXDM log directory configured: {log_path.parent}"
        )
        print(
            f"QXDM log path configured: {log_path}"
        )
        print(
            "QXDM maximum log size configured: "
            f"{self.max_log_size_mb} MB"
        )

        # Save settings. Alt+A applies when available; Enter closes the
        # dialog through the default OK button.
        send_keys("%a")
        time.sleep(0.5)
        send_keys("{ENTER}")
        time.sleep(2)

        return True

    def locate_command_box_with_opencv(
        self,
        window,
    ) -> tuple[int, int]:
        """
        Locate the complete QXDM Command widget using OpenCV.

        The template contains:
            Command: [large input box] [drop-down arrow]

        After matching the full widget, the click point is calculated
        proportionally so it lands inside the large editable input box.
        """
        template_path = self.COMMAND_TEMPLATE_PATH

        if not template_path.exists():
            raise FileNotFoundError(
                "The QXDM command-bar template was not found:\n"
                f"{template_path}"
            )

        try:
            window.maximize()
            time.sleep(1)
            window.set_focus()
        except Exception:
            pass

        rectangle = window.rectangle()

        screenshot = ImageGrab.grab(
            bbox=(
                rectangle.left,
                rectangle.top,
                rectangle.right,
                rectangle.bottom,
            )
        )

        screenshot_bgr = cv2.cvtColor(
            np.array(screenshot),
            cv2.COLOR_RGB2BGR,
        )

        template = cv2.imread(
            str(template_path),
            cv2.IMREAD_COLOR,
        )

        if template is None:
            raise RuntimeError(
                "OpenCV could not read the QXDM command-bar template."
            )

        screenshot_gray = cv2.cvtColor(
            screenshot_bgr,
            cv2.COLOR_BGR2GRAY,
        )
        template_gray = cv2.cvtColor(
            template,
            cv2.COLOR_BGR2GRAY,
        )

        result = cv2.matchTemplate(
            screenshot_gray,
            template_gray,
            cv2.TM_CCOEFF_NORMED,
        )

        _, maximum_score, _, maximum_location = (
            cv2.minMaxLoc(result)
        )

        if maximum_score < self.COMMAND_TEMPLATE_THRESHOLD:
            raise RuntimeError(
                "OpenCV could not confidently locate the complete "
                f"QXDM Command bar. Match score: {maximum_score:.3f}"
            )

        template_height, template_width = (
            template_gray.shape
        )

        matched_left = (
            rectangle.left
            + maximum_location[0]
        )
        matched_top = (
            rectangle.top
            + maximum_location[1]
        )

        click_x = int(
            matched_left
            + template_width
            * self.COMMAND_INPUT_X_RATIO
        )
        click_y = int(
            matched_top
            + template_height
            * self.COMMAND_INPUT_Y_RATIO
        )

        print(
            "OpenCV located the complete QXDM Command bar with "
            f"score {maximum_score:.3f}. "
            f"Clicking inside the large input box at ({click_x}, {click_y})."
        )

        return click_x, click_y

    def send_command(self, command: str) -> bool:
        """
        Locate QXDM's full Command bar with OpenCV, click inside the
        large input box, type the command, and execute it.
        """
        if not self.is_running():
            self.launch()

        window = self.focus_qxdm()
        x, y = self.locate_command_box_with_opencv(
            window
        )

        mouse.click(
            button="left",
            coords=(x, y),
        )
        time.sleep(0.7)

        send_keys("^a")
        time.sleep(0.15)
        send_keys("{BACKSPACE}")
        time.sleep(0.2)

        normalized_command = command.strip().lower()

        send_keys(
            normalized_command,
            with_spaces=True,
            pause=0.10,
        )
        time.sleep(0.4)
        send_keys("{ENTER}")

        print(
            f"Executed QXDM command: {normalized_command}"
        )

        time.sleep(3)
        return True


    def mode_lpm(self) -> bool:
        """Place the modem into low-power mode."""
        print("Sending mode lpm...")
        return self.send_command("mode lpm")

    def mode_online(self) -> bool:
        """Place the modem into online mode."""
        print("Sending mode online...")
        return self.send_command("mode online")

    def wait_for_usb_connection(
        self,
        timeout_seconds: float = 30.0,
        poll_interval: float = 1.0,
    ) -> bool:
        """
        Wait until QXDM's title indicates a diagnostic USB COM port.
        """
        deadline = time.monotonic() + timeout_seconds
        last_title = ""

        while time.monotonic() < deadline:
            window = self.get_window()
            last_title = (
                window.window_text()
                or ""
            )

            normalized_title = last_title.lower()

            if (
                "com" in normalized_title
                and "disconnected" not in normalized_title
            ):
                print(
                    "QXDM diagnostic USB connection detected: "
                    f"{last_title}"
                )
                return True

            time.sleep(poll_interval)

        raise TimeoutError(
            "QXDM opened, but the diagnostic USB connection "
            f"was not detected within {timeout_seconds:.1f} seconds. "
            f"Last window title: {last_title or 'Unavailable'}"
        )

    def start_logging(
        self,
        log_path: Path,
        transition_delay: float = 2.0,
        load_mask: bool = True,
        continue_without_mask: bool = False,
    ) -> bool:
        """
        Run the complete QXDM startup sequence.

        Sequence:
            Create output directory
            Launch QXDM
            Load mask
            Configure Quick Saving destination and maximum size
            mode lpm
            mode online
        """
        self.prepare_log_path(log_path)
        self.launch()

        # Allow QXDM time to attach to the Qualcomm diagnostic USB port.
        self.wait_for_usb_connection(
            timeout_seconds=45.0,
            poll_interval=1.0,
        )
        # Allow the diagnostic connection and QXDM toolbar to settle.
        time.sleep(5)

        if load_mask:
            self.ensure_default_mask_loaded(
                retry_with_picker=True,
                continue_without_mask=continue_without_mask,
            )
            time.sleep(3)

        self.configure_logging(log_path)
        time.sleep(3)

        self.mode_lpm()
        time.sleep(max(transition_delay, 5.0))

        self.mode_online()
        time.sleep(max(transition_delay, 5.0))

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
        load_saved_log: bool = False,
        save_timeout_seconds: float = 20.0,
    ) -> bool:
        """
        Put the modem into low-power mode and allow Quick Saving to flush.

        The QXDM file is saved according to the existing Item Store File
        settings configured inside QXDM.
        """
        self.mode_lpm()
        time.sleep(wait_seconds)

        print(
            "QXDM test stopped. Check the Quick Saving directory "
            "configured under Options > Settings > Item Store File."
        )

        return True

    def test_command_detection(self) -> tuple[int, int]:
        """
        Locate the complete Command bar with OpenCV and type mode lpm
        into the large input box without pressing Enter.
        """
        window = self.focus_qxdm()
        x, y = self.locate_command_box_with_opencv(
            window
        )

        mouse.click(
            button="left",
            coords=(x, y),
        )
        time.sleep(0.7)

        send_keys("^a")
        send_keys("{BACKSPACE}")
        send_keys(
            "mode lpm",
            with_spaces=True,
            pause=0.10,
        )

        print(
            "OpenCV found the complete QXDM Command bar and typed "
            "mode lpm into the large input box without pressing Enter."
        )

        return x, y


    def print_controls(self) -> None:
        """
        Print QXDM UI controls for troubleshooting.

        Run this if the logging dialog fields cannot be found.
        """
        window = self.focus_qxdm()
        window.print_control_identifiers()