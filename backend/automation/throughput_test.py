from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from config import (
    find_speedtest_executable,
    verify_speedtest_executable,
)


DEFAULT_SERVER_ID = "62092"
DEFAULT_SERVER_NAME = "Optimum Online - Parsippany, NJ"


class ThroughputTester:
    """
    Run throughput tests using the official Ookla Speedtest CLI.

    The executable is detected automatically through config.py.

    The public class interface is kept similar to the previous
    speedtest-cli implementation so existing project code does not
    require major changes.
    """

    def __init__(
        self,
        timeout_seconds: int = 15,
        maximum_retries: int = 1,
        retry_delay_seconds: int = 2,
        refresh_server_every: int = 10,
        server_id: str | int | None = DEFAULT_SERVER_ID,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.maximum_retries = maximum_retries
        self.retry_delay_seconds = retry_delay_seconds

        # Kept for compatibility with existing code.
        # The official CLI starts a new process for every test, so it
        # does not reuse a persistent Speedtest connection.
        self.refresh_server_every = refresh_server_every

        # Use the configured server consistently for comparable results.
        # Pass server_id=None to use Ookla automatic server selection only.
        self.server_id = (
            str(server_id)
            if server_id is not None
            else None
        )

        self.completed_tests = 0

        # Automatically locate the official Ookla CLI.
        self.speedtest_path: Path = (
            find_speedtest_executable()
        )

        # Make sure the detected executable is the official
        # Ookla CLI and not the Python speedtest-cli package.
        self.speedtest_version = (
            verify_speedtest_executable(
                self.speedtest_path
            )
        )

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

    def _build_command(
        self,
        server_id: str | None = None,
    ) -> list[str]:
        """
        Create the command used to run the official Ookla CLI.
        """
        command = [
            str(self.speedtest_path),
            "--accept-license",
            "--accept-gdpr",
            "--format=json",
        ]

        if server_id:
            command.extend(
                [
                    "--server-id",
                    server_id,
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
        print(
            f"Using Speedtest CLI: {self.speedtest_path}"
        )

        # A full download/upload test normally needs much longer than
        # the network timeout value supplied to the constructor.
        process_timeout_seconds = max(
            180,
            self.timeout_seconds,
        )

        def run_command(
            server_id: str | None,
        ) -> subprocess.CompletedProcess[str]:
            command = self._build_command(
                server_id
            )

            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=process_timeout_seconds,
                encoding="utf-8",
                errors="replace",
            )

        if self.server_id:
            print(
                f"Using preferred Speedtest server: "
                f"{DEFAULT_SERVER_NAME} "
                f"(ID {self.server_id})"
            )

            completed_process = run_command(
                self.server_id
            )

            if completed_process.returncode == 0:
                return self._extract_json(
                    completed_process.stdout.strip()
                )

            preferred_error = (
                completed_process.stderr.strip()
                or completed_process.stdout.strip()
                or "No error details were returned."
            )

            print(
                "Preferred server was unavailable. "
                "Falling back to Ookla automatic server selection..."
            )
            print(
                f"Preferred server error: {preferred_error}"
            )

        else:
            print(
                "Using Ookla automatic server selection..."
            )

        completed_process = run_command(
            None
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

    def run_full_test(
        self,
    ) -> dict[str, Any]:
        """
        Run a complete throughput test.

        If a test fails, retry according to maximum_retries.
        """
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
        timeout_seconds=15,
        maximum_retries=1,
        retry_delay_seconds=2,
        refresh_server_every=10,
    )

    print("\nSpeedtest Installation")
    print("=" * 40)
    print(
        f"Executable: "
        f"{throughput_tester.speedtest_path}"
    )
    print(
        f"Version: "
        f"{throughput_tester.speedtest_version}"
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