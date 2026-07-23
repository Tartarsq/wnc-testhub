import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .excel_report import ExcelResultWriter
from .throughput_test import ThroughputTester


class AutomatedTestRunner:
    """Run repeated Titan throughput tests and save each result."""

    def __init__(
        self,
        titan,
        qxdm,
        session_folder: Path,
        number_of_runs: int = 5,
        delay_between_runs: int = 10,
        speedtest_executable: str = "speedtest.exe",
        timeout_seconds: int = 180,
    ) -> None:
        """Initialize the automated test runner."""
        self.titan = titan
        self.qxdm = qxdm
        self.session_folder = Path(session_folder)
        self.number_of_runs = number_of_runs
        self.delay_between_runs = delay_between_runs

        self.throughput = ThroughputTester(
            speedtest_executable=speedtest_executable,
            timeout_seconds=timeout_seconds,
        )

        self.excel_path = (
            self.session_folder
            / "reports"
            / "Titan3_Automated_Results.xlsx"
        )

        self.excel = ExcelResultWriter(
            self.excel_path
        )

    def get_radio_metrics(self) -> dict[str, Any]:
        """
        Retrieve radio metrics from Titan.

        RF values remain blank until Titan3.get_radio_metrics()
        is connected to the real Titan API or status source.
        """
        empty_metrics = {
            "firmware_version": None,
            "carrier": None,
            "technology": None,
            "mode": None,
            "serving_band": None,
            "rsrp_dbm": None,
            "rssi_dbm": None,
            "sinr_db": None,
        }

        if not hasattr(self.titan, "get_radio_metrics"):
            return {
                **empty_metrics,
                "metrics_error": (
                    "Titan radio metric collection is not configured."
                ),
            }

        try:
            metrics = self.titan.get_radio_metrics()

            if not isinstance(metrics, dict):
                raise TypeError(
                    "Titan get_radio_metrics() must return a dictionary."
                )

            return {
                **empty_metrics,
                **metrics,
                "metrics_error": None,
            }

        except Exception as error:
            return {
                **empty_metrics,
                "metrics_error": str(error),
            }

    @staticmethod
    def determine_result(
        download_mbps: float | None,
        upload_mbps: float | None,
        packet_loss_percent: float | None = None,
    ) -> str:
        """
        Determine pass or fail using temporary thresholds.

        Replace these values with the team's official requirements.
        """
        minimum_download_mbps = 100.0
        minimum_upload_mbps = 20.0
        maximum_packet_loss_percent = 2.0

        if download_mbps is None or upload_mbps is None:
            return "ERROR"

        throughput_passed = (
            download_mbps >= minimum_download_mbps
            and upload_mbps >= minimum_upload_mbps
        )

        packet_loss_passed = (
            packet_loss_percent is None
            or packet_loss_percent <= maximum_packet_loss_percent
        )

        if throughput_passed and packet_loss_passed:
            return "PASS"

        return "FAIL"

    def create_run_folder(
        self,
        run_number: int,
    ) -> Path:
        """Create and return the folder for one test run."""
        run_folder = (
            self.session_folder
            / "captures"
            / "qxdm"
            / f"run_{run_number:03d}"
        )

        run_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        return run_folder

    def run_single_test(
        self,
        run_number: int,
    ) -> dict[str, Any]:
        """Run one throughput test and return the collected data."""
        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        titan_reachable = self.titan.ping()

        connection_status = (
            "REACHABLE"
            if titan_reachable
            else "UNREACHABLE"
        )

        run_folder = self.create_run_folder(
            run_number
        )

        speedtest_results: dict[str, Any] = {}
        radio_metrics: dict[str, Any] = {}

        overall_result = "ERROR"
        notes = ""

        try:
            if not titan_reachable:
                raise RuntimeError(
                    "Titan 3 is not reachable."
                )

            print("\nSending ModeOnline...")
            self.qxdm.mode_online()

            print("Running automated Speedtest CLI test...")

            speedtest_results = (
                self.throughput.run_full_test()
            )

            download_mbps = speedtest_results.get(
                "download_mbps"
            )

            upload_mbps = speedtest_results.get(
                "upload_mbps"
            )

            ping_ms = speedtest_results.get(
                "ping_ms"
            )

            jitter_ms = speedtest_results.get(
                "ping_jitter_ms"
            )

            packet_loss = speedtest_results.get(
                "packet_loss_percent"
            )

            print(f"Download: {download_mbps} Mbps")
            print(f"Upload: {upload_mbps} Mbps")
            print(f"Ping: {ping_ms} ms")
            print(f"Jitter: {jitter_ms} ms")
            print(f"Packet loss: {packet_loss}%")

            print("Collecting Titan radio metrics...")

            radio_metrics = self.get_radio_metrics()

            overall_result = self.determine_result(
                download_mbps=download_mbps,
                upload_mbps=upload_mbps,
                packet_loss_percent=packet_loss,
            )

        except Exception as error:
            notes = str(error)

            print(
                f"\nRun {run_number} failed: {error}"
            )

            if not radio_metrics:
                radio_metrics = self.get_radio_metrics()

        finally:
            try:
                print("Sending ModeLPM...")
                self.qxdm.mode_lpm()

            except Exception as error:
                lpm_error = (
                    f"ModeLPM error: {error}"
                )

                if notes:
                    notes = (
                        f"{notes}; {lpm_error}"
                    )
                else:
                    notes = lpm_error

                print(lpm_error)

        return {
            "timestamp": timestamp,
            "run_number": run_number,
            "titan_ip": self.titan.ip_address,
            "connection_status": connection_status,
            "download_mbps": speedtest_results.get(
                "download_mbps"
            ),
            "upload_mbps": speedtest_results.get(
                "upload_mbps"
            ),
            "ping_ms": speedtest_results.get(
                "ping_ms"
            ),
            "ping_jitter_ms": speedtest_results.get(
                "ping_jitter_ms"
            ),
            "packet_loss_percent": speedtest_results.get(
                "packet_loss_percent"
            ),
            "isp": speedtest_results.get(
                "isp"
            ),
            "external_ip": speedtest_results.get(
                "external_ip"
            ),
            "interface_name": speedtest_results.get(
                "interface_name"
            ),
            "server_name": speedtest_results.get(
                "server_name"
            ),
            "server_location": speedtest_results.get(
                "server_location"
            ),
            "result_url": speedtest_results.get(
                "result_url"
            ),
            **radio_metrics,
            "overall_result": overall_result,
            "run_folder": str(run_folder),
            "notes": notes,
        }

    def run(self) -> list[dict[str, Any]]:
        """
        Run every requested test and append each result to Excel.

        Returns:
            A list containing all run results.
        """
        all_results: list[dict[str, Any]] = []

        print(
            f"\nStarting {self.number_of_runs} "
            "automated test runs."
        )

        for run_number in range(
            1,
            self.number_of_runs + 1,
        ):
            print("\n" + "=" * 50)

            print(
                f"AUTOMATED RUN "
                f"{run_number}/{self.number_of_runs}"
            )

            print("=" * 50)

            result = self.run_single_test(
                run_number=run_number
            )

            all_results.append(result)

            self.excel.append_result(result)

            print(
                f"\nRun {run_number} result: "
                f"{result['overall_result']}"
            )

            print(
                f"Run {run_number} saved to Excel."
            )

            if run_number < self.number_of_runs:
                print(
                    f"\nWaiting "
                    f"{self.delay_between_runs} seconds "
                    "before the next run..."
                )

                time.sleep(
                    self.delay_between_runs
                )

        print(
            "\nAll automated test runs are complete."
        )

        print("Excel workbook:")
        print(self.excel_path)

        return all_results