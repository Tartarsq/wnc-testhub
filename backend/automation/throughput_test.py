import json
import subprocess
from pathlib import Path
from typing import Any


class ThroughputTester:
    """Runs Ookla Speedtest CLI and returns normalized results."""

    def __init__(
        self,
        speedtest_executable: str | Path = "speedtest.exe",
        timeout_seconds: int = 180,
    ) -> None:
        self.speedtest_executable = Path(speedtest_executable)
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _to_mbps(bytes_per_second: Any) -> float | None:
        if bytes_per_second is None:
            return None

        try:
            return round(float(bytes_per_second) * 8 / 1_000_000, 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None

        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None

    def run_full_test(self) -> dict[str, Any]:
        command = [
            str(self.speedtest_executable),
            "--accept-license",
            "--accept-gdpr",
            "--format=json",
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )

        except FileNotFoundError:
            raise FileNotFoundError(
                "speedtest.exe was not found."
            )

        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "Speedtest timed out."
            )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(
                "Speedtest did not return valid JSON."
            )

        download = data.get("download", {})
        upload = data.get("upload", {})
        ping = data.get("ping", {})
        interface = data.get("interface", {})
        server = data.get("server", {})
        result_data = data.get("result", {})

        return {
            "download_mbps": self._to_mbps(
                download.get("bandwidth")
            ),
            "upload_mbps": self._to_mbps(
                upload.get("bandwidth")
            ),
            "ping_ms": self._to_float(
                ping.get("latency")
            ),
            "ping_jitter_ms": self._to_float(
                ping.get("jitter")
            ),
            "packet_loss_percent": self._to_float(
                data.get("packetLoss")
            ),
            "isp": data.get("isp"),
            "external_ip": interface.get(
                "externalIp"
            ),
            "interface_name": interface.get(
                "name"
            ),
            "server_name": server.get(
                "name"
            ),
            "server_location": (
                f"{server.get('location', '')}, "
                f"{server.get('country', '')}"
            ),
            "result_url": result_data.get(
                "url"
            ),
        }


if __name__ == "__main__":
    tester = ThroughputTester()

    results = tester.run_full_test()

    print(results)