import ctypes
import ctypes.wintypes
import json
import re
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

from tool_settings import ToolSettings


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
        # Portable QXDM executable handling:
        # 1. Prefer a valid machine/user-specific path saved by TestHub.
        # 2. Fall back to the existing QXDM_EXECUTABLE value from config.py.
        #
        # This does not change any of the existing QXDM logging, mask,
        # USB, command, or mode-transition behavior.
        self.tool_settings = ToolSettings()

        configured_executable = Path(executable).expanduser()
        saved_executable = self.tool_settings.get_valid_path(
            "qxdm_executable"
        )

        if saved_executable is not None:
            self.executable = saved_executable
        else:
            self.executable = configured_executable

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

    def resolve_executable(self) -> Path:
        """
        Resolve the QXDM executable path for this computer.

        Priority:
            1. Valid qxdm_executable path saved in tool_settings.py storage
            2. Existing config.py QXDM_EXECUTABLE fallback
        """
        saved_executable = self.tool_settings.get_valid_path(
            "qxdm_executable"
        )

        if saved_executable is not None:
            self.executable = saved_executable

        return Path(self.executable).expanduser()

    def set_executable(
        self,
        executable_path: Path,
        persist: bool = True,
    ) -> Path:
        """
        Set the QXDM executable path.

        If persist=True, remember the selected executable for future TestHub
        runs on this computer/user account.
        """
        executable_path = (
            Path(executable_path)
            .expanduser()
            .resolve()
        )

        if not executable_path.exists():
            raise FileNotFoundError(
                "The selected QXDM executable was not found:\n"
                f"{executable_path}"
            )

        if not executable_path.is_file():
            raise ValueError(
                "The selected QXDM executable path is not a file:\n"
                f"{executable_path}"
            )

        self.executable = executable_path

        if persist:
            self.tool_settings.set_path(
                "qxdm_executable",
                executable_path,
            )

        print(
            "QXDM executable configured for this computer: "
            f"{self.executable}"
        )

        return self.executable

    def prompt_for_executable(self) -> Optional[Path]:
        """
        Let the user browse for QXDM.exe and remember it for this computer.
        """
        try:
            from tkinter import Tk
            from tkinter.filedialog import askopenfilename
        except ImportError as error:
            raise RuntimeError(
                "Tkinter is required to browse for QXDM.exe."
            ) from error

        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        try:
            selected_file = askopenfilename(
                parent=root,
                title="Select QXDM Executable",
                filetypes=[
                    ("QXDM executable", "QXDM.exe"),
                    ("Executable files", "*.exe"),
                    ("All files", "*.*"),
                ],
            )
        finally:
            root.destroy()

        if not selected_file:
            return None

        return self.set_executable(
            Path(selected_file),
            persist=True,
        )

    def executable_exists(self) -> bool:
        """Return True if the resolved QXDM executable exists."""
        executable = self.resolve_executable()
        return executable.exists() and executable.is_file()

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
        self.resolve_executable()

        if not self.executable_exists():
            raise FileNotFoundError(
                "QXDM executable was not found. Configure it for this "
                "computer or update config.py:\n"
                f"{self.executable}"
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
    ):
        """
        Open QXDM Settings via Options -> Settings... and return the
        actual Settings dialog window.

        Confirmed live: pywinauto's menu_select() cannot see QXDM's menu
        bar at all ("There is no menu", for every path tried) - it is
        not a native Win32 menu, so menu_select() never worked here
        regardless of which label or position was used. This uses the
        same keyboard-accelerator approach as open_main_menu()/
        load_default_mask() instead: Alt+O opens the Options menu, then
        typing 's' jumps directly to the first item starting with "S"
        (Settings..., which comes before Sort on Timestamp... in this
        menu) rather than pressing Down a fixed number of times - so it
        isn't tied to how many items happen to be above it.

        Also confirmed from a real screenshot of QXDM_Pro 5.2.680:
        Settings is its own separate top-level window (own title bar,
        own close button), not a Qt panel embedded inside the main QXDM
        window - so this locates it directly with find_dialog() instead
        of deriving a bounding box from the main window's rectangle.
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

        send_keys("s")
        time.sleep(0.3)
        send_keys("{ENTER}")
        time.sleep(2)

        dialog = self.find_dialog(
            title_pattern=r".*Settings.*"
        )

        print(
            "QXDM Settings opened as its own top-level window."
        )

        return dialog

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

    def find_dialog(
        self,
        title_pattern: str = r".*",
        timeout_seconds: float = 10.0,
    ):
        """
        Find a visible top-level window matching title_pattern that
        belongs to the QXDM process specifically.

        Confirmed live: searching the whole Desktop for a loose pattern
        like ".*Settings.*" can match more than one window at once (any
        other app/window on the machine with "Settings" in its title),
        which pywinauto refuses to resolve automatically. Scoping to
        windows owned by QXDM.exe avoids that collision.
        """
        pattern = re.compile(
            title_pattern,
            re.IGNORECASE,
        )

        deadline = time.monotonic() + timeout_seconds
        seen_titles: set[str] = set()

        while time.monotonic() < deadline:
            for process in psutil.process_iter(["pid", "name"]):
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
                            timeout=2,
                        )
                    except Exception:
                        continue

                    for candidate in application.windows(
                        top_level_only=True,
                    ):
                        try:
                            title = (
                                candidate.window_text()
                                or ""
                            )

                            if not candidate.is_visible():
                                continue

                            if title:
                                seen_titles.add(title)

                            if not pattern.search(title):
                                continue

                            # Only require visibility, not "enabled" -
                            # a window can be visible but briefly report
                            # not-enabled while it finishes drawing, which
                            # would otherwise cause a false negative here.
                            return candidate

                        except Exception:
                            continue

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                    ValueError,
                ):
                    continue

            time.sleep(0.5)

        titles_found = (
            "; ".join(sorted(seen_titles))
            if seen_titles
            else "none"
        )

        raise RuntimeError(
            "Could not find a QXDM window matching "
            f"'{title_pattern}' within {timeout_seconds:.0f} seconds. "
            f"Visible QXDM window titles seen instead: {titles_found}"
        )

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

    def wait_for_manual_log_settings(
        self,
        wait_seconds: float = 60.0,
    ) -> None:
        """
        Give the user a fixed amount of time to configure QXDM Item Store File
        settings manually.

        No image template or coordinate detection is used. After the delay,
        TestHub continues automatically with the existing mode lpm -> online
        startup sequence.
        """
        wait_seconds = max(float(wait_seconds), 1.0)

        print("")
        print("==========================================================")
        print("QXDM MANUAL SAVE CONFIGURATION")
        print("==========================================================")
        print(
            f"You have {int(wait_seconds)} seconds to configure "
            "the QXDM Item Store File settings."
        )
        print(
            "Enter the Base File Name, Log File Directory, Log File Path, "
            "and Maximum Log File Size."
        )
        print(
            "When the timer ends, TestHub will continue automatically."
        )
        print("==========================================================")
        print("")

        time.sleep(wait_seconds)

        print(
            "Manual QXDM setup delay completed. Continuing the test."
        )


    def configure_logging(
        self,
        log_path: Path,
    ) -> bool:
        """
        Open QXDM Item Store File Settings and allow one minute for the user
        to enter the save configuration manually.

        TestHub does not click or type into QXDM fields. After 60 seconds,
        the workflow continues automatically to mode lpm and mode online.
        """
        log_path = self.prepare_log_path(
            log_path
        )

        expected_directory = str(
            log_path.parent
        )
        expected_base_name = log_path.stem

        self.open_qxdm_settings()

        # Give the Settings window a moment to finish drawing.
        time.sleep(3)

        print("")
        print("Suggested values:")
        print(f"Base File Name:     {expected_base_name}")
        print(f"Log File Directory: {expected_directory}")
        print(f"Log File Path:      {expected_directory}")
        print(f"Maximum Log Size:   {self.max_log_size_mb} MB")
        print("")

        self.wait_for_manual_log_settings(
            wait_seconds=60.0
        )

        # Try to close Settings before resuming the mode commands. If the user
        # already closed it, Escape is harmless.
        try:
            send_keys("{ESC}")
            time.sleep(1)
        except Exception:
            pass

        self.focus_qxdm()
        time.sleep(2)

        print(
            "Manual QXDM save configuration window completed."
        )

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

    def prompt_for_saved_log(
        self,
    ) -> Optional[Path]:
        """
        Let the user select the actual QXDM log that was saved on disk.

        This is intentionally separate from the existing logging workflow.
        It is a fallback for cases where the user chose a different filename
        or directory inside QXDM Settings than the path suggested by TestHub.
        """
        try:
            from tkinter import Tk
            from tkinter.filedialog import askopenfilename
        except ImportError as error:
            raise RuntimeError(
                "Tkinter is required to select the saved QXDM log."
            ) from error

        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        initial_directory = None
        if self.current_log_path is not None:
            try:
                candidate_parent = Path(
                    self.current_log_path
                ).expanduser().resolve().parent
                if candidate_parent.exists():
                    initial_directory = str(candidate_parent)
            except OSError:
                initial_directory = None

        dialog_options = {
            "parent": root,
            "title": "Select Saved QXDM Log",
            "filetypes": [
                (
                    "QXDM log files",
                    "*.isf *.dlf *.qmdl *.qmdl2 *.bin",
                ),
                ("All files", "*.*"),
            ],
        }

        if initial_directory:
            dialog_options["initialdir"] = initial_directory

        try:
            selected_file = askopenfilename(
                **dialog_options
            )
        finally:
            root.destroy()

        if not selected_file:
            return None

        selected_log = Path(selected_file).resolve()

        if not selected_log.exists() or not selected_log.is_file():
            raise FileNotFoundError(
                "The selected QXDM log was not found:\n"
                f"{selected_log}"
            )

        self.current_log_path = selected_log

        print(
            "Selected saved QXDM log: "
            f"{selected_log}"
        )

        return selected_log

    def open_saved_log_folder(
        self,
        log_path: Optional[Path] = None,
    ) -> bool:
        """
        Open Windows File Explorer and select the saved QXDM log.
        """
        selected_log = (
            Path(log_path).resolve()
            if log_path is not None
            else self.current_log_path
        )

        if selected_log is None:
            raise RuntimeError(
                "No saved QXDM log has been selected."
            )

        selected_log = Path(selected_log).resolve()

        if not selected_log.exists() or not selected_log.is_file():
            raise FileNotFoundError(
                "The saved QXDM log was not found:\n"
                f"{selected_log}"
            )

        subprocess.Popen(
            [
                "explorer.exe",
                "/select,",
                str(selected_log),
            ]
        )

        return True

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

    def _wait_for_saving_dialog_to_close(
        self,
        timeout_seconds: float = 30.0,
    ) -> None:
        """
        Confirmed against the real device: File > Save Items pops up an
        "Information" dialog reading "Please wait, saving log files is
        in progress" with an OK button, while QXDM writes the file. This
        waits for that dialog to close instead of racing ahead - and if
        it's still open once the timeout passes (saving has almost
        certainly finished by then), clicks OK to dismiss it.
        """
        try:
            dialog = Desktop(backend="win32").window(
                title="Information",
                top_level_only=True,
            )
            dialog.wait("visible", timeout=5)
        except Exception:
            # No dialog appeared at all - saving may have finished
            # instantly, or QXDM saved silently with no prompt.
            return

        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            try:
                if not dialog.exists() or not dialog.is_visible():
                    return
            except Exception:
                return

            time.sleep(1)

        try:
            self.click_button_by_keywords(
                dialog,
                ["ok"],
            )
        except Exception:
            pass

    def save_items(self, dialog_timeout_seconds: float = 30.0) -> bool:
        """
        Use QXDM's File -> Save Items... to write the captured Item Store
        data to disk, via its keyboard shortcut (Ctrl+I).

        This uses the shortcut instead of menu_select() for the same
        reason load_default_mask() uses Ctrl+O: QXDM is a Qt application
        and does not reliably expose File menu items to pywinauto.
        """
        self.focus_qxdm()

        send_keys("^i")
        time.sleep(1)

        self._wait_for_saving_dialog_to_close(
            timeout_seconds=dialog_timeout_seconds
        )

        print(
            "Saved QXDM Item Store data via File > Save Items (Ctrl+I)."
        )

        return True

    def stop_logging(
        self,
        load_saved_log: bool = False,
        save_timeout_seconds: float = 20.0,
    ) -> bool:
        """
        Use File -> Save Items to finalize the QXDM log, then wait for
        the saved file to actually appear and stop changing size before
        returning.

        This intentionally does not send mode lpm - stopping capture
        should not put the modem into low-power/airplane mode.
        """
        self.save_items()

        saved_path = None

        try:
            saved_path = self.wait_for_saved_log(
                timeout_seconds=save_timeout_seconds
            )
            print(
                f"QXDM log confirmed saved: {saved_path}"
            )
        except TimeoutError as error:
            print(
                "Could not confirm the QXDM log was saved within "
                f"{save_timeout_seconds:.0f} seconds: {error}"
            )

        if load_saved_log and saved_path is not None:
            try:
                self.load_saved_log(saved_path)
            except Exception as error:
                print(
                    "Saved the QXDM log, but could not reopen it in "
                    f"QXDM automatically: {error}"
                )

        print(
            "QXDM test stopped and the log was saved via "
            "File > Save Items."
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