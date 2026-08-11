from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil
from pywinauto import Desktop


class PCATController:
    """
    Phase 1 PCAT controller for WNC TestHub.

    Current responsibilities:
        1. Resolve the PCAT executable for the current testing computer.
        2. Save/reuse a machine-specific executable path.
        3. Detect whether PCAT is already running.
        4. Launch PCAT when needed.
        5. Find and focus the PCAT window.
        6. Report status back to FastAPI/TestHub.

    CrashDump UI automation is intentionally NOT guessed here.
    Once the real PCAT CrashDump screens/buttons are confirmed, those
    operations can be added on top of this controller without changing
    the executable-launch architecture.
    """

    SETTINGS_FILE = (
        Path.home()
        / ".wnc_testhub"
        / "tool_settings.json"
    )

    SETTINGS_KEY = "pcat_executable"

    ENVIRONMENT_KEY = "WNC_PCAT_EXECUTABLE"

    # Keep these broad because different PCAT versions/installations can use
    # slightly different executable names.
    PROCESS_NAME_HINTS = (
        "pcat",
        "packet",
    )

    WINDOW_TITLE_PATTERN = r"(?i).*PCAT.*"

    # These are only fallback guesses. A saved machine-specific path always
    # takes priority.
    COMMON_PATHS = (
        Path(r"C:\Program Files\Qualcomm\PCAT\PCAT.exe"),
        Path(r"C:\Program Files (x86)\Qualcomm\PCAT\PCAT.exe"),
        Path(r"C:\Qualcomm\PCAT\PCAT.exe"),
        Path(r"C:\PCAT\PCAT.exe"),
    )

    def __init__(
        self,
        executable: str | Path | None = None,
    ) -> None:
        self.process: subprocess.Popen | None = None

        self.executable = self.resolve_executable(
            explicit_path=executable
        )

    # ==========================================================
    # Settings
    # ==========================================================

    def _load_settings(self) -> dict[str, Any]:
        if not self.SETTINGS_FILE.exists():
            return {}

        try:
            data = json.loads(
                self.SETTINGS_FILE.read_text(
                    encoding="utf-8"
                )
            )

            return (
                data
                if isinstance(data, dict)
                else {}
            )

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
        ):
            return {}

    def _save_settings(
        self,
        settings: dict[str, Any],
    ) -> None:
        self.SETTINGS_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.SETTINGS_FILE.write_text(
            json.dumps(
                settings,
                indent=2,
            ),
            encoding="utf-8",
        )

    def save_executable_path(
        self,
        executable: str | Path,
    ) -> Path:
        """
        Save this computer's PCAT executable location.

        The setting is stored outside the Git repository so each testing
        computer can use a different PCAT location without editing code.
        """
        path = Path(
            executable
        ).expanduser()

        if not path.exists():
            raise FileNotFoundError(
                f"PCAT executable was not found:\n{path}"
            )

        if not path.is_file():
            raise ValueError(
                f"PCAT executable path is not a file:\n{path}"
            )

        settings = self._load_settings()
        settings[self.SETTINGS_KEY] = str(
            path.resolve()
        )

        self._save_settings(
            settings
        )

        self.executable = path.resolve()

        return self.executable

    # ==========================================================
    # Executable discovery
    # ==========================================================

    def resolve_executable(
        self,
        explicit_path: str | Path | None = None,
    ) -> Path | None:
        """
        Resolve PCAT in this order:

            1. Explicit constructor path.
            2. WNC_PCAT_EXECUTABLE environment variable.
            3. ~/.wnc_testhub/tool_settings.json.
            4. Common Windows install paths.

        Returns None when PCAT has not been configured/found yet.
        """

        candidates: list[Path] = []

        if explicit_path:
            candidates.append(
                Path(explicit_path).expanduser()
            )

        environment_path = os.getenv(
            self.ENVIRONMENT_KEY,
            "",
        ).strip()

        if environment_path:
            candidates.append(
                Path(environment_path).expanduser()
            )

        settings = self._load_settings()

        configured_path = str(
            settings.get(
                self.SETTINGS_KEY,
                "",
            )
        ).strip()

        if configured_path:
            candidates.append(
                Path(configured_path).expanduser()
            )

        candidates.extend(
            self.COMMON_PATHS
        )

        for candidate in candidates:
            try:
                if (
                    candidate.exists()
                    and candidate.is_file()
                ):
                    return candidate.resolve()

            except OSError:
                continue

        return None

    @property
    def configured(self) -> bool:
        return (
            self.executable is not None
            and self.executable.exists()
            and self.executable.is_file()
        )

    # ==========================================================
    # Running-process detection
    # ==========================================================

    def find_running_process(self) -> psutil.Process | None:
        """
        Find a running PCAT-like process.

        Prefer exact executable matching when a PCAT executable is configured.
        Otherwise use conservative PCAT process-name hints.
        """

        configured_executable = (
            str(self.executable).lower()
            if self.executable is not None
            else None
        )

        for process in psutil.process_iter(
            [
                "pid",
                "name",
                "exe",
            ]
        ):
            try:
                process_executable = (
                    process.info.get("exe")
                    or ""
                ).lower()

                process_name = (
                    process.info.get("name")
                    or ""
                ).lower()

                if (
                    configured_executable
                    and process_executable
                    == configured_executable
                ):
                    return process

                if any(
                    hint in process_name
                    for hint in self.PROCESS_NAME_HINTS
                ):
                    return process

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
                OSError,
            ):
                continue

        return None

    @property
    def running(self) -> bool:
        return (
            self.find_running_process()
            is not None
        )

    # ==========================================================
    # Window handling
    # ==========================================================

    def get_window(
        self,
        timeout_seconds: float = 20.0,
    ):
        """
        Locate PCAT's main desktop window.
        """

        desktop = Desktop(
            backend="uia"
        )

        window = desktop.window(
            title_re=self.WINDOW_TITLE_PATTERN
        )

        window.wait(
            "visible enabled ready",
            timeout=timeout_seconds,
        )

        return window

    def focus(
        self,
        timeout_seconds: float = 20.0,
    ):
        """
        Bring PCAT to the foreground.
        """

        window = self.get_window(
            timeout_seconds=timeout_seconds
        )

        try:
            if window.is_minimized():
                window.restore()
        except Exception:
            pass

        window.set_focus()

        return window

    # ==========================================================
    # Launch
    # ==========================================================

    def launch(
        self,
        wait_seconds: float = 5.0,
    ) -> dict[str, Any]:
        """
        Launch PCAT, or focus the existing PCAT instance if already running.
        """

        if self.running:
            try:
                window = self.focus()
                title = (
                    window.window_text()
                    or "PCAT"
                )
            except Exception:
                title = "PCAT"

            return {
                "success": True,
                "already_running": True,
                "running": True,
                "window_title": title,
                "executable_path": (
                    str(self.executable)
                    if self.executable
                    else None
                ),
                "message": (
                    "PCAT is already running and was brought to the front."
                ),
            }

        if not self.configured:
            raise FileNotFoundError(
                "PCAT has not been configured on this testing computer.\n\n"
                "Set the PCAT executable path once in TestHub, or set the "
                "WNC_PCAT_EXECUTABLE environment variable."
            )

        self.process = subprocess.Popen(
            [str(self.executable)],
            cwd=str(
                self.executable.parent
            ),
        )

        time.sleep(
            max(wait_seconds, 0)
        )

        running_process = (
            self.find_running_process()
        )

        if running_process is None:
            raise RuntimeError(
                "PCAT was launched but TestHub could not confirm that "
                "the application is running."
            )

        window_title = None

        try:
            window = self.focus()
            window_title = (
                window.window_text()
                or "PCAT"
            )
        except Exception:
            # Do not fail the entire launch just because the window title
            # differs from the expected pattern. We can tune the UI locator
            # after inspecting the actual PCAT screen.
            pass

        return {
            "success": True,
            "already_running": False,
            "running": True,
            "window_title": window_title,
            "executable_path": str(
                self.executable
            ),
            "message": (
                "PCAT launched successfully. "
                "CrashDump navigation can now begin."
            ),
        }

    # ==========================================================
    # Status
    # ==========================================================

    def status(self) -> dict[str, Any]:
        process = (
            self.find_running_process()
        )

        return {
            "configured": self.configured,
            "running": (
                process is not None
            ),
            "pid": (
                process.pid
                if process is not None
                else None
            ),
            "executable_path": (
                str(self.executable)
                if self.executable
                else None
            ),
            "settings_file": str(
                self.SETTINGS_FILE
            ),
        }


if __name__ == "__main__":
    controller = PCATController()

    print(
        "PCAT status before launch:"
    )
    print(
        controller.status()
    )

    result = controller.launch()

    print(
        "\nLaunch result:"
    )
    print(
        result
    )