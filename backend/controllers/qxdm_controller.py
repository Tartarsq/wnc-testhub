
import json
import os
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
        prefer_direct_automation: bool = True,
    ) -> None:
        self.executable = Path(executable)

        self.default_mask = (
            Path(default_mask)
            if default_mask is not None
            else None
        )

        # Allow a QXDM size value from 0 through 1024 MB.
        # QXDM commonly uses 0 for its zero/unlimited setting.
        self.max_log_size_mb = min(
            max(int(max_log_size_mb), 0),
            1024,
        )

        self.process: subprocess.Popen | None = None
        self.current_log_path: Optional[Path] = None

        # Experimental direct QXDM automation. When unavailable or incompatible,
        # the controller automatically falls back to the existing pywinauto flow.
        self.prefer_direct_automation = bool(prefer_direct_automation)
        self.direct_qxdm = None
        self.direct_logger = None
        self.direct_logging_active = False
        self.direct_automation_error: Optional[str] = None
        self.direct_debug_path = (
            Path.home()
            / ".wnc_testhub"
            / "qxdm_direct_automation_debug.txt"
        )

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

    def _ask_yes_no(
        self,
        title: str,
        message: str,
    ) -> bool:
        """Display a simple Yes/No dialog."""
        try:
            from tkinter import Tk, messagebox
        except ImportError as error:
            raise RuntimeError(
                "The confirmation dialog is unavailable."
            ) from error

        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        try:
            return bool(
                messagebox.askyesno(
                    title,
                    message,
                    parent=root,
                )
            )
        finally:
            root.destroy()

    def prompt_for_max_log_size(self) -> int:
        """
        Ask the user for the desired QXDM maximum log size in MB.

        The value must be between 0 MB and 1024 MB.
        Cancelling keeps the currently configured value.
        """
        try:
            from tkinter import Tk, simpledialog
        except ImportError as error:
            raise RuntimeError(
                "The QXDM log-size dialog is unavailable."
            ) from error

        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        try:
            selected_size = simpledialog.askinteger(
                "QXDM Log Size",
                (
                    "Enter the maximum QXDM log file size in MB "
                    "(0-1024):"
                ),
                initialvalue=self.max_log_size_mb,
                minvalue=0,
                maxvalue=1024,
                parent=root,
            )
        finally:
            root.destroy()

        if selected_size is not None:
            self.max_log_size_mb = selected_size

        print(
            "QXDM maximum log size selected: "
            f"{self.max_log_size_mb} MB"
        )

        return self.max_log_size_mb

    def prompt_for_logging_setup(
        self,
        suggested_log_path: Optional[Path] = None,
    ) -> tuple[Path, bool]:
        """
        Display one setup window for the complete QXDM logging configuration.

        The user can:
            - choose a QXDM mask/configuration file,
            - choose the log folder,
            - enter the log filename,
            - choose a maximum size from 0 through 1024 MB,
            - choose to use a configuration already loaded in QXDM.

        Returns:
            (resolved_log_path, should_load_mask)
        """
        try:
            from tkinter import (
                BooleanVar,
                Button,
                Checkbutton,
                Entry,
                Frame,
                IntVar,
                Label,
                Spinbox,
                StringVar,
                Tk,
                messagebox,
            )
            from tkinter.filedialog import askdirectory, askopenfilename
        except ImportError as error:
            raise RuntimeError(
                "The QXDM logging setup dialog is unavailable."
            ) from error

        suggested_path = (
            Path(suggested_log_path).expanduser()
            if suggested_log_path is not None
            else Path.cwd() / "QXDM_Logs" / "qxdm_log.hdf"
        )

        if suggested_path.suffix:
            initial_folder = suggested_path.parent
            initial_filename = suggested_path.name
        else:
            initial_folder = suggested_path
            initial_filename = "qxdm_log.hdf"

        saved_mask = self._load_saved_mask_path()
        initial_mask = ""

        if self.default_mask is not None:
            candidate = Path(self.default_mask).expanduser()
            if candidate.exists() and candidate.is_file():
                initial_mask = str(candidate.resolve())
        elif saved_mask is not None:
            initial_mask = str(saved_mask)

        root = Tk()
        root.title("QXDM Logging Setup")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        mask_var = StringVar(value=initial_mask)
        folder_var = StringVar(value=str(initial_folder))
        filename_var = StringVar(value=initial_filename)
        size_var = IntVar(value=self.max_log_size_mb)
        use_loaded_var = BooleanVar(value=False)

        result: dict[str, object] = {}

        def browse_mask() -> None:
            selected = askopenfilename(
                parent=root,
                title="Select QXDM Log Mask / Configuration",
                filetypes=[
                    (
                        "QXDM mask/configuration files",
                        "*.dmc *.cfg *.xml *.qcn *.txt",
                    ),
                    ("All files", "*.*"),
                ],
            )
            if selected:
                mask_var.set(selected)
                use_loaded_var.set(False)

        def browse_folder() -> None:
            selected = askdirectory(
                parent=root,
                title="Select QXDM Log Folder",
                initialdir=folder_var.get() or str(Path.cwd()),
            )
            if selected:
                folder_var.set(selected)

        def update_mask_state() -> None:
            state = "disabled" if use_loaded_var.get() else "normal"
            mask_entry.configure(state=state)
            mask_button.configure(state=state)

        def submit() -> None:
            folder_text = folder_var.get().strip()
            filename_text = filename_var.get().strip()
            mask_text = mask_var.get().strip()

            if not folder_text:
                messagebox.showerror(
                    "Missing Folder",
                    "Choose a folder for the QXDM log.",
                    parent=root,
                )
                return

            if not filename_text:
                messagebox.showerror(
                    "Missing File Name",
                    "Enter a file name for the QXDM log.",
                    parent=root,
                )
                return

            invalid_filename_chars = set('<>:"/\\|?*')
            if any(char in filename_text for char in invalid_filename_chars):
                messagebox.showerror(
                    "Invalid File Name",
                    (
                        "The file name cannot contain any of these "
                        'characters: < > : " / \\ | ? *'
                    ),
                    parent=root,
                )
                return

            try:
                selected_size = int(size_var.get())
            except (TypeError, ValueError):
                messagebox.showerror(
                    "Invalid File Size",
                    "Enter a whole number from 0 through 1024 MB.",
                    parent=root,
                )
                return

            if not 0 <= selected_size <= 1024:
                messagebox.showerror(
                    "Invalid File Size",
                    "The maximum file size must be from 0 through 1024 MB.",
                    parent=root,
                )
                return

            should_load_mask = not use_loaded_var.get()

            if should_load_mask:
                if not mask_text:
                    messagebox.showerror(
                        "Missing Log Mask",
                        (
                            "Choose a QXDM log mask/configuration or select "
                            "'Use configuration already loaded in QXDM'."
                        ),
                        parent=root,
                    )
                    return

                mask_path = Path(mask_text).expanduser()

                if not mask_path.exists() or not mask_path.is_file():
                    messagebox.showerror(
                        "Log Mask Not Found",
                        f"The selected QXDM mask was not found:\n{mask_path}",
                        parent=root,
                    )
                    return

                resolved_mask = mask_path.resolve()
                self.default_mask = resolved_mask
                self._save_mask_path(resolved_mask)

            folder_path = Path(folder_text).expanduser().resolve()
            folder_path.mkdir(parents=True, exist_ok=True)

            log_path = folder_path / filename_text

            self.max_log_size_mb = selected_size
            self.current_log_path = log_path

            result["log_path"] = log_path
            result["should_load_mask"] = should_load_mask
            root.destroy()

        def cancel() -> None:
            root.destroy()

        container = Frame(root, padx=14, pady=14)
        container.grid(row=0, column=0)

        Label(
            container,
            text="Log Mask / Configuration:",
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        mask_entry = Entry(
            container,
            textvariable=mask_var,
            width=62,
        )
        mask_entry.grid(row=1, column=0, columnspan=2, padx=(0, 8), pady=(3, 10))

        mask_button = Button(
            container,
            text="Browse...",
            command=browse_mask,
            width=12,
        )
        mask_button.grid(row=1, column=2, pady=(3, 10))

        Checkbutton(
            container,
            text="Use configuration already loaded in QXDM",
            variable=use_loaded_var,
            command=update_mask_state,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 12))

        Label(
            container,
            text="Preferred Save Folder:",
            anchor="w",
        ).grid(row=3, column=0, columnspan=3, sticky="w")

        folder_entry = Entry(
            container,
            textvariable=folder_var,
            width=62,
        )
        folder_entry.grid(row=4, column=0, columnspan=2, padx=(0, 8), pady=(3, 10))

        Button(
            container,
            text="Browse...",
            command=browse_folder,
            width=12,
        ).grid(row=4, column=2, pady=(3, 10))

        Label(
            container,
            text="Log File Name:",
            anchor="w",
        ).grid(row=5, column=0, columnspan=3, sticky="w")

        Entry(
            container,
            textvariable=filename_var,
            width=62,
        ).grid(row=6, column=0, columnspan=3, sticky="we", pady=(3, 10))

        Label(
            container,
            text="Maximum File Size (MB, 0-1024):",
            anchor="w",
        ).grid(row=7, column=0, columnspan=3, sticky="w")

        Spinbox(
            container,
            from_=0,
            to=1024,
            textvariable=size_var,
            width=12,
        ).grid(row=8, column=0, sticky="w", pady=(3, 4))

        Label(
            container,
            text="0 uses QXDM's zero/unlimited setting.",
            anchor="w",
        ).grid(row=9, column=0, columnspan=3, sticky="w", pady=(0, 14))

        button_frame = Frame(container)
        button_frame.grid(row=10, column=0, columnspan=3, sticky="e")

        Button(
            button_frame,
            text="Cancel",
            command=cancel,
            width=12,
        ).grid(row=0, column=0, padx=(0, 8))

        Button(
            button_frame,
            text="Start Test",
            command=submit,
            width=12,
        ).grid(row=0, column=1)

        root.protocol("WM_DELETE_WINDOW", cancel)
        update_mask_state()
        root.mainloop()

        if "log_path" not in result:
            raise RuntimeError(
                "The QXDM logging setup was cancelled. "
                "The test was not started."
            )

        selected_log_path = Path(result["log_path"])
        should_load_mask = bool(result["should_load_mask"])

        print(f"QXDM log folder: {selected_log_path.parent}")
        print(f"QXDM log file: {selected_log_path.name}")
        print(
            "QXDM maximum log size selected: "
            f"{self.max_log_size_mb} MB"
        )

        return selected_log_path, should_load_mask

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
        Ensure that QXDM has the required configuration before testing.

        Behavior:
            1. Try the configured or previously selected mask automatically.
            2. If loading fails, ask whether the correct configuration is
               already loaded in QXDM.
            3. If it is not loaded, open a file picker and load it manually.
            4. Continue only after one of those paths succeeds.
        """
        candidates: list[Path] = []

        if self.default_mask is not None:
            configured_mask = Path(
                self.default_mask
            ).expanduser()

            if configured_mask.exists() and configured_mask.is_file():
                candidates.append(configured_mask.resolve())

        saved_mask = self._load_saved_mask_path()

        if (
            saved_mask is not None
            and saved_mask not in candidates
        ):
            candidates.append(saved_mask)

        for candidate in candidates:
            try:
                return self._open_mask_file(candidate)
            except Exception as error:
                print(
                    "Could not automatically load QXDM configuration "
                    f"{candidate}: {error}"
                )

        configuration_already_loaded = self._ask_yes_no(
            "QXDM Configuration",
            (
                "Is the required QXDM configuration already loaded "
                "in QXDM?\n\n"
                "Choose Yes to continue the test.\n"
                "Choose No to select and load a configuration file."
            ),
        )

        if configuration_already_loaded:
            print(
                "Using the configuration already loaded in QXDM."
            )
            return True

        selected_mask = self._prompt_for_mask()

        try:
            return self._open_mask_file(selected_mask)
        except Exception as error:
            raise RuntimeError(
                "The selected QXDM configuration could not be loaded. "
                "The test was not started."
            ) from error

    def _write_direct_debug(self, message: str) -> None:
        """Write direct-automation diagnostics without interrupting TestHub."""
        try:
            self.direct_debug_path.parent.mkdir(parents=True, exist_ok=True)
            with self.direct_debug_path.open("a", encoding="utf-8") as debug_file:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                debug_file.write(f"[{timestamp}] {message}\n")
        except OSError:
            pass

    @staticmethod
    def _call_first_available(target, method_names: list[str], argument_sets):
        """Call the first available automation method with a compatible signature."""
        errors: list[str] = []

        for method_name in method_names:
            try:
                method = getattr(target, method_name)
            except Exception as error:
                errors.append(f"{method_name}: unavailable ({error})")
                continue

            for arguments in argument_sets:
                try:
                    result = method(*arguments)
                    return method_name, result
                except Exception as error:
                    errors.append(
                        f"{method_name}{arguments!r}: {type(error).__name__}: {error}"
                    )

        raise RuntimeError("; ".join(errors))

    @staticmethod
    def _set_first_available_property(
        target,
        property_names: list[str],
        value,
        required: bool = True,
    ) -> Optional[str]:
        """Set the first writable COM property from a list of possible names."""
        errors: list[str] = []

        for property_name in property_names:
            try:
                setattr(target, property_name, value)
                return property_name
            except Exception as error:
                errors.append(
                    f"{property_name}: {type(error).__name__}: {error}"
                )

        if required:
            raise RuntimeError("; ".join(errors))

        return None

    def start_logging_direct(
        self,
        log_path: Path,
        mask_path: Optional[Path] = None,
        max_size_mb: Optional[int] = None,
    ) -> bool:
        """
        Try to start QXDM logging through an installed Windows COM interface.

        Qualcomm has shipped different automation interfaces across QXDM builds,
        so this adapter probes several common object and method names. Failure is
        non-fatal because start_logging() falls back to the existing UI workflow.

        Set QXDM_COM_PROGID in the environment when WNC knows the exact ProgID.
        """
        log_path = self.prepare_log_path(log_path)
        selected_size = (
            self.max_log_size_mb
            if max_size_mb is None
            else min(max(int(max_size_mb), 0), 1024)
        )

        if mask_path is not None:
            mask_path = Path(mask_path).expanduser().resolve()
            if not mask_path.exists() or not mask_path.is_file():
                raise FileNotFoundError(
                    f"The direct-automation mask was not found:\n{mask_path}"
                )

        try:
            import win32com.client  # type: ignore[import-untyped]
        except ImportError as error:
            raise RuntimeError(
                "Direct QXDM automation requires pywin32. "
                "Install it with: pip install pywin32"
            ) from error

        configured_progid = os.environ.get("QXDM_COM_PROGID", "").strip()
        progids = [
            configured_progid,
            "QXDM.Application",
            "QXDM4.Application",
            "QXDM.QXDMApplication",
            "Qualcomm.QXDM.Application",
        ]
        progids = list(dict.fromkeys(value for value in progids if value))

        dispatch_errors: list[str] = []
        application = None
        selected_progid = None

        for progid in progids:
            try:
                application = win32com.client.Dispatch(progid)
                selected_progid = progid
                break
            except Exception as error:
                dispatch_errors.append(
                    f"{progid}: {type(error).__name__}: {error}"
                )

        if application is None:
            raise RuntimeError(
                "No compatible QXDM COM application was found. Tried: "
                + " | ".join(dispatch_errors)
            )

        self.direct_qxdm = application
        self._write_direct_debug(f"Connected using ProgID: {selected_progid}")

        if mask_path is not None:
            mask_method, _ = self._call_first_available(
                application,
                [
                    "LoadConfiguration",
                    "LoadConfig",
                    "LoadLogMask",
                    "OpenConfiguration",
                    "OpenConfig",
                ],
                [(str(mask_path),)],
            )
            self._write_direct_debug(
                f"Loaded mask with {mask_method}: {mask_path}"
            )

        # Some automation builds expose StartLogging directly on the app.
        direct_start_errors: list[str] = []
        for method_name in ["StartLogging", "StartLog", "BeginLogging"]:
            try:
                method = getattr(application, method_name)
            except Exception as error:
                direct_start_errors.append(f"{method_name}: unavailable ({error})")
                continue

            for arguments in [
                (str(log_path), selected_size),
                (str(log_path),),
                (str(log_path.parent), log_path.name, selected_size),
                (str(log_path.parent), log_path.name),
            ]:
                try:
                    result = method(*arguments)
                    self.direct_logger = result if result is not None else application
                    self.direct_logging_active = True
                    self.direct_automation_error = None
                    self._write_direct_debug(
                        f"Started direct logging with {method_name}{arguments!r}"
                    )
                    print(
                        "QXDM direct automation started logging to: "
                        f"{log_path}"
                    )
                    return True
                except Exception as error:
                    direct_start_errors.append(
                        f"{method_name}{arguments!r}: "
                        f"{type(error).__name__}: {error}"
                    )

        # Other builds expose a logger/item-store object that must be configured.
        factory_name, logger = self._call_first_available(
            application,
            [
                "CreateItemStore",
                "CreateLogger",
                "CreateLog",
                "NewItemStore",
                "GetLogger",
            ],
            [(), (str(log_path),)],
        )

        if logger is None:
            raise RuntimeError(
                f"{factory_name} returned no logger object. Direct start errors: "
                + " | ".join(direct_start_errors)
            )

        path_property = self._set_first_available_property(
            logger,
            [
                "FileName",
                "Filename",
                "OutputFile",
                "OutputPath",
                "LogFileName",
                "LogPath",
            ],
            str(log_path),
        )
        size_property = self._set_first_available_property(
            logger,
            [
                "MaximumFileSize",
                "MaxFileSize",
                "MaximumSize",
                "MaxSizeMB",
                "FileSizeLimit",
            ],
            selected_size,
            required=False,
        )

        start_method, _ = self._call_first_available(
            logger,
            ["Start", "StartLogging", "Begin", "Open"],
            [(), (str(log_path),), (selected_size,)],
        )

        self.direct_logger = logger
        self.direct_logging_active = True
        self.direct_automation_error = None
        self._write_direct_debug(
            "Started logger object using "
            f"factory={factory_name}, path_property={path_property}, "
            f"size_property={size_property}, start_method={start_method}"
        )
        print(f"QXDM direct automation started logging to: {log_path}")
        return True

    def stop_logging_direct(self) -> bool:
        """Stop and flush a log started by start_logging_direct()."""
        if not self.direct_logging_active:
            return False

        targets = []
        if self.direct_logger is not None:
            targets.append(self.direct_logger)
        if self.direct_qxdm is not None and self.direct_qxdm not in targets:
            targets.append(self.direct_qxdm)

        stop_errors: list[str] = []
        stopped = False

        for target in targets:
            try:
                method_name, _ = self._call_first_available(
                    target,
                    ["Stop", "StopLogging", "End", "Close"],
                    [()],
                )
                self._write_direct_debug(
                    f"Stopped direct logger with {method_name}"
                )
                stopped = True
                break
            except Exception as error:
                stop_errors.append(str(error))

        if not stopped:
            raise RuntimeError(
                "Could not stop the direct QXDM logger: "
                + " | ".join(stop_errors)
            )

        for target in targets:
            try:
                self._call_first_available(
                    target,
                    ["Save", "Flush", "Commit"],
                    [(), (str(self.current_log_path),) if self.current_log_path else ()],
                )
                break
            except Exception:
                continue

        self.direct_logging_active = False
        self.direct_logger = None
        print("QXDM direct logging stopped.")
        return True

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
        log_path: Optional[Path] = None,
        transition_delay: float = 5.0,
        load_mask: bool = True,
        prompt_for_setup: bool = True,
    ) -> bool:
        """
        Run the complete QXDM startup sequence.

        By default, one setup dialog asks the user for:
            - the log mask/configuration,
            - the preferred save folder,
            - the log filename,
            - the maximum file size from 0 through 1024 MB.

        After the setup is confirmed, the controller creates the folder,
        loads the mask when requested, configures logging, and runs the
        existing mode commands.
        """
        should_load_mask = load_mask

        if prompt_for_setup:
            log_path, should_load_mask = self.prompt_for_logging_setup(
                suggested_log_path=log_path,
            )
        elif log_path is None:
            raise ValueError(
                "A log path is required when prompt_for_setup is False."
            )

        assert log_path is not None

        self.prepare_log_path(log_path)
        self.launch()

        direct_started = False

        if self.prefer_direct_automation:
            try:
                direct_mask = self.default_mask if should_load_mask else None
                direct_started = self.start_logging_direct(
                    log_path=log_path,
                    mask_path=direct_mask,
                    max_size_mb=self.max_log_size_mb,
                )
            except Exception as error:
                self.direct_automation_error = (
                    f"{type(error).__name__}: {error}"
                )
                self._write_direct_debug(
                    "Direct automation failed; falling back to pywinauto: "
                    f"{self.direct_automation_error}"
                )
                print(
                    "QXDM direct automation was unavailable. "
                    "Falling back to the existing QXDM UI workflow."
                )
                print(
                    f"Direct automation details: {self.direct_automation_error}"
                )
                print(f"Diagnostic file: {self.direct_debug_path}")

        if not direct_started:
            if should_load_mask:
                self.load_default_mask()

            self.configure_logging(log_path)

        self.mode_lpm()

        print(
            "Waiting "
            f"{transition_delay:.1f} seconds before mode online..."
        )
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

        if self.direct_logging_active:
            self.stop_logging_direct()
        else:
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