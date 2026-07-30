import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .excel_report import ExcelResultWriter
from .throughput_test import ThroughputTester


class AutomatedTestRunner:
    """
    Run repeated Titan throughput tests and save each result.

    QXDM logging is intentionally separate from throughput testing.
    Use start_qxdm_logging() and stop_qxdm_logging() when a QXDM
    capture is needed.
    """

    def __init__(
        self,
        titan,
        qxdm,
        session_folder: Path,
        number_of_runs: int = 5,
        delay_between_runs: int = 10,
        timeout_seconds: int = 180,
    ) -> None:
        """Initialize the automated test runner."""
        self.titan = titan
        self.qxdm = qxdm
        self.session_folder = Path(session_folder)
        self.number_of_runs = max(int(number_of_runs), 1)
        self.delay_between_runs = max(int(delay_between_runs), 0)
        self.timeout_seconds = max(int(timeout_seconds), 1)

        self.throughput = ThroughputTester(
            timeout_seconds=self.timeout_seconds
        )

        self.excel_path = (
            self.session_folder
            / "reports"
            / "Titan3_Automated_Results.xlsx"
        )

        self.excel = ExcelResultWriter(self.excel_path)

        self.active_qxdm_log_path: Optional[Path] = None

    # ------------------------------------------------------------------
    # QXDM WORKFLOW
    # ------------------------------------------------------------------

    def create_qxdm_log_path(self) -> Path:
        """Create a timestamped QXDM log path for this session."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        log_folder = (
            self.session_folder
            / "captures"
            / "qxdm"
        )

        log_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        return log_folder / f"Titan3_QXDM_{timestamp}.isf"

    def start_qxdm_logging(
        self,
        log_path: Path | None = None,
        load_mask: bool = True,
    ) -> Path:
        """
        Start an independent QXDM logging session.

        This method does not run a throughput test.
        """
        if self.qxdm is None:
            raise RuntimeError(
                "A QXDM controller was not provided."
            )

        if log_path is None:
            log_path = self.create_qxdm_log_path()
        else:
            log_path = Path(log_path).resolve()
            log_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        print("\nStarting QXDM logging...")
        print(f"QXDM log path: {log_path}")

        self.qxdm.start_logging(
            log_path=log_path,
            load_mask=load_mask,
        )

        self.active_qxdm_log_path = log_path

        print("QXDM logging started.")
        return log_path

    def stop_qxdm_logging(
        self,
        load_saved_log: bool = True,
    ) -> Path | None:
        """
        Stop QXDM logging and finalize the active log.

        The updated QXDMController.stop_logging() is expected to:
            1. Send mode lpm.
            2. Stop the QXDM capture.
            3. Wait for the log file to finish saving.
            4. Optionally load the saved log back into QXDM.
        """
        if self.qxdm is None:
            raise RuntimeError(
                "A QXDM controller was not provided."
            )

        if self.active_qxdm_log_path is None:
            print("No active QXDM log is registered.")

        print("\nStopping QXDM logging...")

        self.qxdm.stop_logging(
            load_saved_log=load_saved_log
        )

        completed_log_path = self.active_qxdm_log_path
        self.active_qxdm_log_path = None

        if completed_log_path is not None:
            print(
                f"QXDM log finalized: "
                f"{completed_log_path.resolve()}"
            )

        return completed_log_path

    # ------------------------------------------------------------------
    # TITAN DATA COLLECTION
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # THROUGHPUT WORKFLOW
    # ------------------------------------------------------------------

    def run_single_test(
        self,
        run_number: int,
    ) -> dict[str, Any]:
        """
        Run one throughput test.

        This method does not start, stop, or send commands to QXDM.
        """
        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        titan_reachable = self.titan.ping()

        connection_status = (
            "REACHABLE"
            if titan_reachable
            else "UNREACHABLE"
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

            print(
                "\nRunning official Ookla CLI throughput test..."
            )

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

            test_duration = speedtest_results.get(
                "test_duration_seconds"
            )

            print(f"Download: {download_mbps} Mbps")
            print(f"Upload: {upload_mbps} Mbps")
            print(f"Ping: {ping_ms} ms")
            print(f"Jitter: {jitter_ms} ms")
            server_name = speedtest_results.get(
                "server_name"
            )
            server_location = speedtest_results.get(
                "server_location"
            )

            print(f"Packet loss: {packet_loss}%")
            print(f"Test duration: {test_duration} seconds")
            print(f"Server: {server_name or 'Unknown'}")
            print(
                f"Server location: "
                f"{server_location or 'Unknown'}"
            )

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
            "test_duration_seconds": speedtest_results.get(
                "test_duration_seconds"
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
            "run_folder": None,
            "notes": notes,
        }

    def run(self) -> list[dict[str, Any]]:
        """
        Run every requested throughput test and append each result to Excel.

        QXDM is not started, stopped, or controlled by this method.
        """
        all_results: list[dict[str, Any]] = []

        print(
            f"\nStarting {self.number_of_runs} "
            "independent throughput test runs."
        )

        for run_number in range(
            1,
            self.number_of_runs + 1,
        ):
            print("\n" + "=" * 50)

            print(
                f"THROUGHPUT RUN "
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
            "\nAll throughput test runs are complete."
        )

        self.open_results()

        return all_results

    def open_results(self) -> None:
        """Open the reports folder and Excel workbook on Windows."""
        resolved_excel_path = self.excel_path.resolve()

        print(
            f"Excel workbook: {resolved_excel_path}"
        )

        try:
            if not resolved_excel_path.exists():
                raise FileNotFoundError(
                    f"Excel workbook was not found: "
                    f"{resolved_excel_path}"
                )

            os.startfile(
                resolved_excel_path.parent
            )

            os.startfile(
                resolved_excel_path
            )

            print(
                "Opened the reports folder and automated "
                "Excel workbook."
            )

        except Exception as error:
            print(
                f"Could not open the results automatically: "
                f"{error}"
            )