from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional


class SyslogController:
    """
    Capture syslog output into the active TestHub wrapper session.

    The Titan 3 syslog command is environment-configured because the exact
    command depends on the WNC test environment. Set WNC_SYSLOG_COMMAND on the
    test computer once the team confirms the command that continuously emits
    the desired syslog stream.
    """

    def __init__(self, command: Optional[str] = None) -> None:
        self.command = (
            command
            if command is not None
            else os.getenv("WNC_SYSLOG_COMMAND", "").strip()
        )
        self.process: subprocess.Popen | None = None
        self.output_handle = None
        self.current_log_path: Path | None = None

    @property
    def configured(self) -> bool:
        return bool(self.command)

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, output_folder: Path, base_name: str = "syslog") -> Path:
        if self.running:
            raise RuntimeError("Syslog collection is already running.")

        if not self.configured:
            raise RuntimeError(
                "Syslog collection is not configured. "
                "Set WNC_SYSLOG_COMMAND to the Titan 3 syslog command."
            )

        output_folder = Path(output_folder).expanduser().resolve()
        output_folder.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_folder / f"{base_name}_{timestamp}.log"

        self.output_handle = output_path.open(
            "w",
            encoding="utf-8",
            errors="replace",
        )

        self.process = subprocess.Popen(
            self.command,
            shell=True,
            stdout=self.output_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

        self.current_log_path = output_path
        return output_path

    def stop(self, timeout_seconds: float = 5.0) -> Path | None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()

            try:
                self.process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)

        self.process = None

        if self.output_handle is not None:
            self.output_handle.flush()
            self.output_handle.close()
            self.output_handle = None

        return self.current_log_path

    def status(self) -> dict:
        return {
            "configured": self.configured,
            "running": self.running,
            "log_path": (
                str(self.current_log_path.resolve())
                if self.current_log_path is not None
                else None
            ),
        }