from __future__ import annotations

import socket
import time
from typing import Any

import speedtest


class ThroughputTester:
    """
    Run internet throughput tests using speedtest-cli.

    The Speedtest object and selected server are reused between runs
    to reduce setup time.
    """

    def __init__(
        self,
        timeout_seconds: int = 15,
        maximum_retries: int = 1,
        retry_delay_seconds: int = 2,
        refresh_server_every: int = 10,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.maximum_retries = maximum_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.refresh_server_every = refresh_server_every

        self.tester: speedtest.Speedtest | None = None
        self.completed_tests = 0

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """Convert a value to a rounded float when possible."""
        if value is None:
            return None

        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _get_interface_name() -> str | None:
        """
        Return the local hostname.

        speedtest-cli does not directly expose the Windows network
        interface name, so this provides a useful local identifier.
        """
        try:
            return socket.gethostname()
        except OSError:
            return None

    def _create_tester(self) -> speedtest.Speedtest:
        """Create and configure the Speedtest object."""
        print("Initializing Speedtest connection...")

        tester = speedtest.Speedtest(
            timeout=self.timeout_seconds,
            secure=True,
        )

        print("Selecting the best Speedtest server...")
        tester.get_best_server()

        return tester

    def _ensure_tester(self) -> speedtest.Speedtest:
        """
        Return the existing Speedtest object or create a new one.

        The server is periodically refreshed so long test sessions do
        not permanently rely on a server that may become degraded.
        """
        should_refresh = (
            self.tester is None
            or (
                self.refresh_server_every > 0
                and self.completed_tests > 0
                and self.completed_tests
                % self.refresh_server_every
                == 0
            )
        )

        if should_refresh:
            self.tester = self._create_tester()

        return self.tester

    def reset_connection(self) -> None:
        """Force a new Speedtest connection on the next test."""
        self.tester = None

    def _run_test_once(self) -> dict[str, Any]:
        """Run one download and upload test."""
        tester = self._ensure_tester()

        test_start = time.perf_counter()

        print("Running download test...")
        download_mbps = tester.download() / 1_000_000

        print("Running upload test...")
        upload_mbps = tester.upload() / 1_000_000

        elapsed_seconds = time.perf_counter() - test_start

        results = tester.results.dict()

        self.completed_tests += 1

        server = results.get("server") or {}
        client = results.get("client") or {}

        server_name = server.get("name")
        server_country = server.get("country")
        server_sponsor = server.get("sponsor")

        server_location_parts = [
            part
            for part in [
                server_name,
                server_country,
            ]
            if part
        ]

        server_location = ", ".join(
            server_location_parts
        )

        return {
            "download_mbps": round(
                download_mbps,
                2,
            ),
            "upload_mbps": round(
                upload_mbps,
                2,
            ),
            "ping_ms": self._to_float(
                results.get("ping")
            ),

            # speedtest-cli does not normally provide jitter.
            "ping_jitter_ms": None,

            # speedtest-cli often does not provide packet loss.
            "packet_loss_percent": self._to_float(
                results.get("packetLoss")
                or results.get("packet_loss")
            ),

            "isp": client.get("isp"),
            "external_ip": client.get("ip"),
            "interface_name": self._get_interface_name(),

            "server_name": (
                server_sponsor
                or server_name
            ),
            "server_location": server_location,

            # This is usually blank unless results.share()
            # is explicitly called.
            "result_url": results.get("share"),

            "test_duration_seconds": round(
                elapsed_seconds,
                2,
            ),
        }

    def run_full_test(self) -> dict[str, Any]:
        """
        Run a complete throughput test.

        If a test fails, reset the Speedtest connection and retry.
        """
        attempts = self.maximum_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                print(
                    f"Speedtest attempt "
                    f"{attempt}/{attempts}"
                )

                return self._run_test_once()

            except Exception as error:
                last_error = error

                print(
                    f"Speedtest attempt {attempt} failed: "
                    f"{error}"
                )

                # Discard the current connection and server.
                self.reset_connection()

                if attempt < attempts:
                    print(
                        f"Retrying in "
                        f"{self.retry_delay_seconds} seconds..."
                    )

                    time.sleep(
                        self.retry_delay_seconds
                    )

        raise RuntimeError(
            f"Speedtest failed after {attempts} "
            f"attempt(s): {last_error}"
        ) from last_error


if __name__ == "__main__":
    throughput_tester = ThroughputTester(
        timeout_seconds=15,
        maximum_retries=1,
        retry_delay_seconds=2,
        refresh_server_every=10,
    )

    test_results = throughput_tester.run_full_test()

    print("\nSpeedtest Results")
    print("=" * 40)

    for key, value in test_results.items():
        print(f"{key}: {value}")