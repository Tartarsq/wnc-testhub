from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from config import (
    find_speedtest_executable,
    verify_speedtest_executable,
)
from tool_settings import ToolSettings


class ThroughputTester:
    """
    Run throughput testing in either GUI or CLI mode.

    GUI mode:
        Launch the installed Speedtest desktop application so the engineer
        can accept the best server or choose a specific server manually.
        GUI results can then be normalized into the same result dictionary
        used by the rest of TestHub.

    CLI mode:
        Keep the existing official Ookla Speedtest CLI workflow unchanged.

    Keeping both modes means existing analytics/reporting code can continue
    consuming the same throughput result fields.
    """

    def __init__(
        self,
        timeout_seconds: int = 15,
        maximum_retries: int = 1,
        retry_delay_seconds: int = 2,
        refresh_server_every: int = 10,
        server_id: str | int | None = None,
        mode: str = "cli",
        gui_executable: Optional[Path] = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.maximum_retries = maximum_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.refresh_server_every = refresh_server_every

        normalized_mode = str(mode).strip().lower()

        if normalized_mode not in {
            "gui",
            "cli",
        }:
            raise ValueError(
                "Throughput mode must be either 'gui' or 'cli'."
            )

        self.mode = normalized_mode

        self.server_id = (
            str(server_id)
            if server_id is not None
            else None
        )

        self.completed_tests = 0
        self.tool_settings = ToolSettings()

        # Keep CLI discovery exactly as before. It is resolved lazily so GUI
        # mode does not require the CLI to be installed.
        self.speedtest_path: Optional[Path] = None
        self.speedtest_version: Optional[str] = None

        if self.mode == "cli":
            self._ensure_cli_ready()

        saved_gui = self.tool_settings.get_valid_path(
            "speedtest_gui_executable"
        )

        if saved_gui is not None:
            self.gui_executable: Optional[Path] = saved_gui
        elif gui_executable is not None:
            self.gui_executable = (
                Path(gui_executable)
                .expanduser()
            )
        else:
            self.gui_executable = None

        self.gui_process: Optional[subprocess.Popen] = None

    def _ensure_cli_ready(self) -> Path:
        """Locate and verify the official Ookla CLI only when it is needed."""
        if (
            self.speedtest_path is not None
            and Path(self.speedtest_path).exists()
        ):
            return Path(self.speedtest_path)

        self.speedtest_path = (
            find_speedtest_executable()
        )

        self.speedtest_version = (
            verify_speedtest_executable(
                self.speedtest_path
            )
        )

        return self.speedtest_path

    def get_gui_executable(self) -> Optional[Path]:
        """
        Return the saved Speedtest GUI executable when it still exists.
        """
        saved_gui = self.tool_settings.get_valid_path(
            "speedtest_gui_executable"
        )

        if saved_gui is not None:
            self.gui_executable = saved_gui
            return saved_gui

        if self.gui_executable is None:
            return None

        candidate = (
            Path(self.gui_executable)
            .expanduser()
        )

        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

        return None

    def set_gui_executable(
        self,
        executable_path: Path,
        persist: bool = True,
    ) -> Path:
        """
        Configure the Speedtest GUI executable for this testing computer.
        """
        executable_path = (
            Path(executable_path)
            .expanduser()
            .resolve()
        )

        if not executable_path.exists():
            raise FileNotFoundError(
                "The selected Speedtest GUI executable was not found:\n"
                f"{executable_path}"
            )

        if not executable_path.is_file():
            raise ValueError(
                "The selected Speedtest GUI path is not a file:\n"
                f"{executable_path}"
            )

        self.gui_executable = executable_path

        if persist:
            self.tool_settings.set_path(
                "speedtest_gui_executable",
                executable_path,
            )

        return executable_path

    def prompt_for_gui_executable(
        self,
    ) -> Optional[Path]:
        """
        Let the engineer browse for the Speedtest desktop executable.
        The selected path is remembered for future TestHub runs.
        """
        try:
            from tkinter import Tk
            from tkinter.filedialog import askopenfilename
        except ImportError as error:
            raise RuntimeError(
                "Tkinter is required to browse for the Speedtest GUI."
            ) from error

        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        try:
            selected_file = askopenfilename(
                parent=root,
                title="Select Speedtest Desktop Executable",
                filetypes=[
                    ("Executable files", "*.exe"),
                    ("All files", "*.*"),
                ],
            )
        finally:
            root.destroy()

        if not selected_file:
            return None

        return self.set_gui_executable(
            Path(selected_file),
            persist=True,
        )

    def launch_gui(self) -> Path:
        """
        Launch Speedtest's desktop GUI.

        TestHub deliberately does not automate the server-selection controls.
        The engineer can use Speedtest's suggested/best server or choose a
        specific server before pressing GO.
        """
        executable = self.get_gui_executable()

        if executable is None:
            executable = self.prompt_for_gui_executable()

        if executable is None:
            raise RuntimeError(
                "Speedtest GUI is not configured on this computer."
            )

        self.gui_process = subprocess.Popen(
            [str(executable)],
            cwd=str(executable.parent),
        )

        print(
            "Speedtest GUI opened. "
            "Choose the desired server in Speedtest and run the test."
        )

        return executable

    def normalize_gui_result(
        self,
        *,
        download_mbps: float,
        upload_mbps: float,
        ping_ms: float,
        server_name: str,
        server_location: str = "",
        server_id: str | int | None = None,
        ping_jitter_ms: float | None = None,
        packet_loss_percent: float | None = None,
        isp: str | None = None,
        result_url: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Convert a manually completed GUI test into the same field structure
        used by CLI throughput results.

        This preserves the existing Analytics/Excel pipeline.
        """
        self.completed_tests += 1

        return {
            "download_mbps": self._to_float(
                download_mbps
            ),
            "upload_mbps": self._to_float(
                upload_mbps
            ),
            "ping_ms": self._to_float(
                ping_ms
            ),
            "ping_jitter_ms": self._to_float(
                ping_jitter_ms
            ),
            "packet_loss_percent": self._to_float(
                packet_loss_percent
            ),
            "isp": isp,
            "external_ip": None,
            "interface_name": self._get_interface_name(),
            "server_name": (
                server_name.strip()
                if server_name
                else None
            ),
            "server_location": (
                server_location.strip()
                if server_location
                else None
            ),
            "server_id": (
                str(server_id)
                if server_id is not None
                else None
            ),
            "server_host": None,
            "result_url": result_url,
            "test_duration_seconds": None,
            "raw_speedtest_result": {
                "source": "speedtest_gui",
                "notes": notes,
            },
        }


    @staticmethod
    def _to_float(
        value: Any,
    ) -> float | None:
        """Convert a value to a rounded float when possible."""
        if value is None:
            return None

        try:
            return round(
                float(value),
                2,
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _get_interface_name() -> str | None:
        """
        Return the local hostname when the CLI does not provide
        a network-interface name.
        """
        try:
            return socket.gethostname()
        except OSError:
            return None

    @staticmethod
    def _extract_json(
        output: str,
    ) -> dict[str, Any]:
        """
        Parse JSON returned by the Ookla CLI.

        Normally the CLI returns only JSON when --format=json is used.
        The fallback handles cases where another informational line is
        printed before the JSON object.
        """
        cleaned_output = output.strip()

        if not cleaned_output:
            raise RuntimeError(
                "Ookla Speedtest returned no output."
            )

        try:
            parsed_output = json.loads(
                cleaned_output
            )
        except json.JSONDecodeError:
            json_start = cleaned_output.find("{")

            if json_start == -1:
                raise RuntimeError(
                    "Ookla Speedtest did not return valid JSON.\n"
                    f"Output:\n{cleaned_output}"
                )

            try:
                parsed_output = json.loads(
                    cleaned_output[json_start:]
                )
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    "Ookla Speedtest returned invalid JSON.\n"
                    f"Output:\n{cleaned_output}"
                ) from error

        if not isinstance(parsed_output, dict):
            raise RuntimeError(
                "Ookla Speedtest returned an unexpected "
                "JSON structure."
            )

        return parsed_output

    def _build_command(self) -> list[str]:
        """
        Create the command used to run the official Ookla CLI.
        """
        speedtest_path = self._ensure_cli_ready()

        command = [
            str(speedtest_path),
            "--accept-license",
            "--accept-gdpr",
            "--format=json",
        ]

        if self.server_id:
            command.extend(
                [
                    "--server-id",
                    self.server_id,
                ]
            )

        return command

    def reset_connection(self) -> None:
        """
        Compatibility method.

        The official CLI creates a new process and connection for every
        throughput test, so there is no persistent connection to reset.
        """
        return None

    def _run_speedtest_command(
        self,
    ) -> dict[str, Any]:
        """Run the official Ookla CLI and return its JSON output."""
        command = self._build_command()

        print(
            f"Using Speedtest CLI: {self.speedtest_path}"
        )

        if self.server_id:
            print(
                f"Using Speedtest server ID: "
                f"{self.server_id}"
            )
        else:
            print(
                "Using the automatically selected "
                "Speedtest server..."
            )

        # A full download/upload test normally needs much longer than
        # the network timeout value supplied to the constructor.
        process_timeout_seconds = max(
            180,
            self.timeout_seconds,
        )

        completed_process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=process_timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )

        standard_output = (
            completed_process.stdout.strip()
        )

        standard_error = (
            completed_process.stderr.strip()
        )

        if completed_process.returncode != 0:
            error_output = (
                standard_error
                or standard_output
                or "No error details were returned."
            )

            raise RuntimeError(
                "Ookla Speedtest failed.\n"
                f"Exit code: "
                f"{completed_process.returncode}\n"
                f"Details:\n{error_output}"
            )

        return self._extract_json(
            standard_output
        )

    def _run_test_once(
        self,
    ) -> dict[str, Any]:
        """Run one complete download and upload test."""
        test_start = time.perf_counter()

        print("Running Ookla throughput test...")

        raw_results = (
            self._run_speedtest_command()
        )

        elapsed_seconds = (
            time.perf_counter()
            - test_start
        )

        self.completed_tests += 1

        download = (
            raw_results.get("download")
            or {}
        )

        upload = (
            raw_results.get("upload")
            or {}
        )

        ping = (
            raw_results.get("ping")
            or {}
        )

        server = (
            raw_results.get("server")
            or {}
        )

        interface = (
            raw_results.get("interface")
            or {}
        )

        result_information = (
            raw_results.get("result")
            or {}
        )

        # The official Ookla CLI reports bandwidth in bytes per second.
        # Multiply by 8 to convert bytes to bits, then divide by
        # 1,000,000 to convert to Mbps.
        download_bandwidth = self._to_float(
            download.get("bandwidth")
        )

        upload_bandwidth = self._to_float(
            upload.get("bandwidth")
        )

        download_mbps = (
            round(
                download_bandwidth
                * 8
                / 1_000_000,
                2,
            )
            if download_bandwidth is not None
            else None
        )

        upload_mbps = (
            round(
                upload_bandwidth
                * 8
                / 1_000_000,
                2,
            )
            if upload_bandwidth is not None
            else None
        )

        server_name = (
            server.get("name")
            or server.get("host")
        )

        server_location = (
            server.get("location")
            or server.get("country")
        )

        interface_name = (
            interface.get("name")
            or self._get_interface_name()
        )

        return {
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,

            "ping_ms": self._to_float(
                ping.get("latency")
            ),

            "ping_jitter_ms": self._to_float(
                ping.get("jitter")
            ),

            "packet_loss_percent": self._to_float(
                raw_results.get("packetLoss")
                or raw_results.get(
                    "packet_loss"
                )
            ),

            "isp": raw_results.get("isp"),

            "external_ip": (
                interface.get("externalIp")
                or interface.get("external_ip")
            ),

            "interface_name": interface_name,

            "server_name": server_name,
            "server_location": server_location,

            "server_id": (
                server.get("id")
            ),

            "server_host": (
                server.get("host")
            ),

            "result_url": (
                result_information.get("url")
                or raw_results.get("share")
            ),

            "test_duration_seconds": round(
                elapsed_seconds,
                2,
            ),

            # Keep the full response available so that we can save
            # a separate JSON log for every throughput test later.
            "raw_speedtest_result": raw_results,
        }

    def run(
        self,
    ) -> dict[str, Any] | Path:
        """
        Start the configured throughput workflow.

        GUI mode returns the executable path after launching the desktop app.
        CLI mode returns the structured throughput result.
        """
        if self.mode == "gui":
            return self.launch_gui()

        return self.run_full_test()

    def run_full_test(
        self,
    ) -> dict[str, Any]:
        """
        Run one complete CLI throughput test.

        If a test fails, retry according to maximum_retries.
        """
        self._ensure_cli_ready()
        attempts = (
            self.maximum_retries
            + 1
        )

        last_error: Exception | None = None

        for attempt in range(
            1,
            attempts + 1,
        ):
            try:
                print(
                    f"Speedtest attempt "
                    f"{attempt}/{attempts}"
                )

                return self._run_test_once()

            except subprocess.TimeoutExpired as error:
                last_error = error

                print(
                    "Speedtest attempt "
                    f"{attempt} timed out."
                )

            except Exception as error:
                last_error = error

                print(
                    f"Speedtest attempt "
                    f"{attempt} failed: "
                    f"{error}"
                )

            if attempt < attempts:
                print(
                    f"Retrying in "
                    f"{self.retry_delay_seconds} "
                    "seconds..."
                )

                time.sleep(
                    self.retry_delay_seconds
                )

        raise RuntimeError(
            f"Speedtest failed after "
            f"{attempts} attempt(s): "
            f"{last_error}"
        ) from last_error



if __name__ == "__main__":
    throughput_tester = ThroughputTester(
        mode="cli",
        timeout_seconds=15,
        maximum_retries=1,
        retry_delay_seconds=2,
        refresh_server_every=10,
    )

    test_results = (
        throughput_tester.run_full_test()
    )

    print("\nSpeedtest Results")
    print("=" * 40)

    for key, value in test_results.items():
        if key == "raw_speedtest_result":
            continue

        print(f"{key}: {value}")