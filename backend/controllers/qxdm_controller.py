import ctypes
import ctypes.wintypes
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
    COMMAND_TEMPLATE_THRESHOLD = 0.72

    # Exact point inside the large white input box in qxdm_command_bar.png.
    COMMAND_INPUT_X_OFFSET = 260
    COMMAND_INPUT_Y_OFFSET = 21

    # Only search the top toolbar region so OpenCV cannot match another box.
    COMMAND_SEARCH_HEIGHT = 140
    COMMAND_SEARCH_WIDTH_RATIO = 0.58

    MENU_BAR_TEMPLATE_PATH = (
        Path(__file__).resolve().parent
        / "qxdm_menu_bar.png"
    )
    LOAD_CONFIGURATION_TEMPLATE_PATH = (
        Path(__file__).resolve().parent
        / "qxdm_load_configuration_item.png"
    )
    SETTINGS_MENU_TEMPLATE_PATH = (
        Path(__file__).resolve().parent
        / "qxdm_options_settings_item.png"
    )

    # Click offsets inside qxdm_menu_bar.png.
    FILE_MENU_CLICK_X_OFFSET = 20
    OPTIONS_MENU_CLICK_X_OFFSET = 140
    MENU_BAR_CLICK_Y_RATIO = 0.50
    SETTINGS_ANCHOR_TEMPLATE_PATH = (
        Path(__file__).resolve().parent
        / "qxdm_settings_anchor.png"
    )
    SETTINGS_TEMPLATE_THRESHOLD = 0.72

    ITEM_STORE_ANCHOR_TEMPLATE_PATH = (
        Path(__file__).resolve().parent
        / "qxdm_item_store_anchor.png"
    )
    ITEM_STORE_ANCHOR_THRESHOLD = 0.72

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

    def locate_template_on_screen(
        self,
        template_path: Path,
        threshold: float,
    ) -> tuple[int, int, int, int, float]:
        """
        Locate an image template on the current Windows desktop.

        Returns:
            left, top, right, bottom, match_score
        """
        template_path = Path(
            template_path
        ).resolve()

        if not template_path.exists():
            raise FileNotFoundError(
                "QXDM UI template was not found:\n"
                f"{template_path}"
            )

        screenshot = ImageGrab.grab()
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
                "OpenCV could not read the QXDM UI template:\n"
                f"{template_path}"
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

        if maximum_score < threshold:
            raise RuntimeError(
                "OpenCV could not confidently locate the QXDM UI "
                f"template '{template_path.name}'. "
                f"Match score: {maximum_score:.3f}"
            )

        height, width = template_gray.shape

        left = int(maximum_location[0])
        top = int(maximum_location[1])
        right = left + int(width)
        bottom = top + int(height)

        return (
            left,
            top,
            right,
            bottom,
            float(maximum_score),
        )

    def open_main_menu(
        self,
        menu_name: str,
    ) -> None:
        """
        Open a QXDM top-level menu using keyboard access keys.

        This avoids OpenCV matching for the menu bar, which can vary
        with DPI scaling, theme, and window size.
        """
        self.focus_qxdm()

        normalized_name = menu_name.strip().lower()

        if normalized_name == "file":
            send_keys("%f")
        elif normalized_name == "options":
            send_keys("%o")
        else:
            raise ValueError(
                "Unsupported QXDM main menu: "
                f"{menu_name}"
            )

        time.sleep(0.8)


    def open_qxdm_settings(
        self,
    ) -> tuple[int, int, int, int]:
        """
        Open QXDM Settings using:

            Alt+O -> Down -> Enter

        In this QXDM build, Settings is a Qt child dialog inside the
        main QXDM window, so Windows continues to report the main QXDM
        title as the active window. Use the main-window rectangle and
        derive the Settings dialog position from it.
        """
        window = self.focus_qxdm()

        try:
            window.maximize()
            time.sleep(1)
            window.set_focus()
        except Exception:
            pass

        self.open_main_menu(
            "Options"
        )

        send_keys("{DOWN}")
        time.sleep(0.2)
        send_keys("{ENTER}")
        time.sleep(2)

        rectangle = window.rectangle()

        # QXDM 5.2.640 displays Settings as a centered Qt child dialog.
        # These ratios match the layout shown in the user's screenshots.
        settings_left = int(
            rectangle.left
            + rectangle.width() * 0.12
        )
        settings_top = int(
            rectangle.top
            + rectangle.height() * 0.07
        )
        settings_right = int(
            rectangle.left
            + rectangle.width() * 0.88
        )
        settings_bottom = int(
            rectangle.top
            + rectangle.height() * 0.96
        )

        print(
            "QXDM Settings opened as an embedded Qt dialog. "
            "Using derived dialog bounds: "
            f"({settings_left}, {settings_top}, "
            f"{settings_right}, {settings_bottom})"
        )

        return (
            settings_left,
            settings_top,
            settings_right,
            settings_bottom,
        )

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
        Load the selected .dmc configuration using QXDM's built-in
        shortcut for File -> Load Configuration...:

            Ctrl+O
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

        self.focus_qxdm()

        send_keys("^o")
        time.sleep(1.5)

        self.handle_file_dialog(
            self.default_mask
        )

        # Allow time for QXDM to apply the DMC configuration.
        time.sleep(4)

        print(
            "Loaded QXDM configuration: "
            f"{self.default_mask}"
        )

        return True

    def _click_absolute(
        self,
        x: int,
        y: int,
    ) -> None:
        mouse.click(
            button="left",
            coords=(int(x), int(y)),
        )
        time.sleep(0.45)

    def _replace_active_text(
        self,
        value: str,
    ) -> None:
        send_keys("^a")
        time.sleep(0.1)
        send_keys("{BACKSPACE}")
        time.sleep(0.1)
        send_keys(
            value,
            with_spaces=True,
            pause=0.03,
        )

    def locate_template_multiscale(
        self,
        template_path: Path,
        threshold: float = 0.50,
        minimum_scale: float = 0.70,
        maximum_scale: float = 1.35,
        scale_step: float = 0.05,
    ) -> tuple[int, int, int, int, float]:
        """
        Locate a UI template across multiple DPI/display scales.

        This is used for the Item Store File anchor because QXDM and
        Windows display scaling can make the live control larger or
        smaller than the saved template.
        """
        template_path = Path(template_path).resolve()

        if not template_path.exists():
            raise FileNotFoundError(
                "QXDM UI template was not found:\n"
                f"{template_path}"
            )

        screenshot = ImageGrab.grab()
        screenshot_bgr = cv2.cvtColor(
            np.array(screenshot),
            cv2.COLOR_RGB2BGR,
        )
        screenshot_gray = cv2.cvtColor(
            screenshot_bgr,
            cv2.COLOR_BGR2GRAY,
        )

        original_template = cv2.imread(
            str(template_path),
            cv2.IMREAD_GRAYSCALE,
        )

        if original_template is None:
            raise RuntimeError(
                "OpenCV could not read the QXDM UI template:\n"
                f"{template_path}"
            )

        best_score = -1.0
        best_location = None
        best_width = None
        best_height = None
        scale = minimum_scale

        while scale <= maximum_scale + 0.001:
            resized = cv2.resize(
                original_template,
                None,
                fx=scale,
                fy=scale,
                interpolation=(
                    cv2.INTER_AREA
                    if scale < 1.0
                    else cv2.INTER_CUBIC
                ),
            )

            height, width = resized.shape

            if (
                width >= screenshot_gray.shape[1]
                or height >= screenshot_gray.shape[0]
                or width < 20
                or height < 10
            ):
                scale += scale_step
                continue

            result = cv2.matchTemplate(
                screenshot_gray,
                resized,
                cv2.TM_CCOEFF_NORMED,
            )

            _, score, _, location = cv2.minMaxLoc(
                result
            )

            if score > best_score:
                best_score = float(score)
                best_location = location
                best_width = width
                best_height = height

            scale += scale_step

        if (
            best_location is None
            or best_width is None
            or best_height is None
            or best_score < threshold
        ):
            raise RuntimeError(
                "OpenCV could not confidently locate the QXDM UI "
                f"template '{template_path.name}' at any tested scale. "
                f"Best match score: {best_score:.3f}"
            )

        left = int(best_location[0])
        top = int(best_location[1])
        right = left + int(best_width)
        bottom = top + int(best_height)

        print(
            "Multiscale OpenCV located "
            f"{template_path.name} with score {best_score:.3f}."
        )

        return (
            left,
            top,
            right,
            bottom,
            best_score,
        )

    def configure_logging(
        self,
        log_path: Path,
    ) -> bool:
        """
        Configure QXDM Item Store File saving from one OpenCV anchor.

        OpenCV locates the Base File Name row once. The remaining fields
        are addressed by stable offsets from that matched row:

            Base File Name
            Log File Directory
            Log File Path
            Maximum Log File Size

        All other QXDM automation remains unchanged.
        """
        log_path = self.prepare_log_path(
            log_path
        )

        self.open_qxdm_settings()
        time.sleep(1)

        (
            anchor_left,
            anchor_top,
            anchor_right,
            anchor_bottom,
            anchor_score,
        ) = self.locate_template_multiscale(
            self.ITEM_STORE_ANCHOR_TEMPLATE_PATH,
            threshold=0.50,
            minimum_scale=0.70,
            maximum_scale=1.35,
            scale_step=0.05,
        )

        print(
            "Located QXDM Item Store File anchor with "
            f"score {anchor_score:.3f}."
        )

        # Positions measured from the clean Item Store File screenshot.
        base_filename_point = (
            anchor_left + 285,
            anchor_top + 24,
        )
        log_directory_point = (
            anchor_left + 330,
            anchor_top + 101,
        )
        log_file_path_point = (
            anchor_left + 315,
            anchor_top + 183,
        )
        maximum_size_point = (
            anchor_left + 420,
            anchor_top + 260,
        )

        # Base File Name receives only the filename stem.
        self._click_absolute(
            *base_filename_point
        )
        self._replace_active_text(
            log_path.stem
        )

        # Log File Directory receives only the selected folder.
        self._click_absolute(
            *log_directory_point
        )
        self._replace_active_text(
            str(log_path.parent)
        )

        # Log File Path receives the complete path.
        self._click_absolute(
            *log_file_path_point
        )
        self._replace_active_text(
            str(log_path)
        )

        # Preserve the configured maximum log size.
        self._click_absolute(
            *maximum_size_point
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

        print(
            f"QXDM base filename configured: {log_path.stem}"
        )
        print(
            f"QXDM log directory configured: {log_path.parent}"
        )
        print(
            f"QXDM full log path configured: {log_path}"
        )
        print(
            "QXDM maximum log size configured: "
            f"{self.max_log_size_mb} MB"
        )

        # Close Settings after applying the field values.
        send_keys("{ESC}")
        time.sleep(2)

        return True

    def locate_command_box_with_opencv(
        self,
        window,
    ) -> tuple[int, int]:
        """
        Locate QXDM's complete Command bar within the top toolbar only.

        Restricting the search to the top 140 pixels prevents OpenCV from
        matching another text box elsewhere in QXDM.
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

        search_bottom = min(
            rectangle.bottom,
            rectangle.top + self.COMMAND_SEARCH_HEIGHT,
        )

        # Search only the left side of the toolbar. The View Finder input
        # is on the right and is visually similar to the Command input.
        search_right = int(
            rectangle.left
            + rectangle.width()
            * self.COMMAND_SEARCH_WIDTH_RATIO
        )

        screenshot = ImageGrab.grab(
            bbox=(
                rectangle.left,
                rectangle.top,
                search_right,
                search_bottom,
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
                "OpenCV could not read qxdm_command_bar.png."
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
                "OpenCV could not confidently locate the QXDM "
                f"Command bar in the toolbar. Match score: "
                f"{maximum_score:.3f}"
            )

        matched_left = (
            rectangle.left
            + maximum_location[0]
        )
        matched_top = (
            rectangle.top
            + maximum_location[1]
        )

        click_x = (
            matched_left
            + self.COMMAND_INPUT_X_OFFSET
        )
        click_y = (
            matched_top
            + self.COMMAND_INPUT_Y_OFFSET
        )

        print(
            "OpenCV located the QXDM Command bar with "
            f"score {maximum_score:.3f}. "
            f"Clicking the large input box at ({click_x}, {click_y}). "
            "Search was restricted to the left side of the toolbar."
        )

        return click_x, click_y

    def send_command(self, command: str) -> bool:
        """
        Find the Command bar, click the large input box, and execute a
        modem command.
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
        time.sleep(0.8)

        send_keys("^a")
        time.sleep(0.2)
        send_keys("{BACKSPACE}")
        time.sleep(0.2)

        normalized_command = command.strip().lower()

        send_keys(
            normalized_command,
            with_spaces=True,
            pause=0.12,
        )
        time.sleep(0.5)
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

        # Give the modem enough time to enter low-power mode and for
        # QXDM to settle before sending the online command.
        time.sleep(max(transition_delay, 10.0))

        # QXDM can lose focus during the modem state transition.
        # Refocus it, then let send_command() re-run OpenCV detection
        # before typing mode online.
        self.focus_qxdm()
        time.sleep(2)

        self.mode_online()

        # Allow the modem and QXDM connection to stabilize.
        time.sleep(max(transition_delay, 3.0))

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