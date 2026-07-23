from __future__ import annotations

from typing import Any

import speedtest


class ThroughputTester:
    """Runs an internet throughput test using speedtest-cli."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None

        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None

    def run_full_test(self) -> dict[str, Any]:
        try:
            tester = speedtest.Speedtest()

            tester.get_best_server()

            download_mbps = (
                tester.download() / 1_000_000
            )

            upload_mbps = (
                tester.upload() / 1_000_000
            )

            results = tester.results.dict()

        except Exception as error:
            raise RuntimeError(
                f"Speedtest failed: {error}"
            ) from error

        server = results.get("server", {})
        client = results.get("client", {})

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
            "ping_jitter_ms": None,
            "packet_loss_percent": self._to_float(
                results.get("packetLoss")
            ),
            "isp": client.get("isp"),
            "external_ip": client.get("ip"),
            "interface_name": None,
            "server_name": (
                server_sponsor
                or server_name
            ),
            "server_location": server_location,
            "result_url": results.get("share"),
        }


if __name__ == "__main__":
    tester = ThroughputTester()

    results = tester.run_full_test()

    print("\nSpeedtest Results")
    print("=" * 40)

    for key, value in results.items():
        print(f"{key}: {value}")