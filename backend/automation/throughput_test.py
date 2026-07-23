import json
import subprocess
from pathlib import Path
from typing import Optional


class ThroughputTester:
    """Run automated iperf3 throughput tests."""

    def __init__(
        self,
        server_ip: str,
        iperf_executable: Path = Path("iperf3.exe"),
        duration_seconds: int = 10,
        port: int = 5201,
    ) -> None:
        self.server_ip = server_ip
        self.iperf_executable = Path(iperf_executable)
        self.duration_seconds = duration_seconds
        self.port = port

    def _run_iperf(
        self,
        reverse: bool = False,
    ) -> dict:
        command = [
            str(self.iperf_executable),
            "-c",
            self.server_ip,
            "-p",
            str(self.port),
            "-t",
            str(self.duration_seconds),
            "-J",
        ]

        # With iperf3, -R reverses the direction.
        if reverse:
            command.append("-R")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=self.duration_seconds + 30,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "iperf3 failed.\n"
                f"Command: {' '.join(command)}\n"
                f"Error: {result.stderr.strip()}"
            )

        try:
            return json.loads(result.stdout)

        except json.JSONDecodeError as error:
            raise RuntimeError(
                "iperf3 did not return valid JSON."
            ) from error

    @staticmethod
    def _extract_mbps(data: dict) -> Optional[float]:
        """
        Extract receiver throughput from iperf3 JSON.

        Different iperf3 modes may place the value in slightly
        different result fields.
        """
        end_data = data.get("end", {})

        stream = (
            end_data.get("sum_received")
            or end_data.get("sum")
            or end_data.get("sum_sent")
        )

        if not stream:
            return None

        bits_per_second = stream.get("bits_per_second")

        if bits_per_second is None:
            return None

        return round(bits_per_second / 1_000_000, 2)

    def run_download_test(self) -> Optional[float]:
        """
        Run traffic from the iperf server toward Titan.

        Depending on where this script runs, you may need to swap
        download and upload directions.
        """
        data = self._run_iperf(reverse=True)
        return self._extract_mbps(data)

    def run_upload_test(self) -> Optional[float]:
        """Run traffic from Titan toward the iperf server."""
        data = self._run_iperf(reverse=False)
        return self._extract_mbps(data)