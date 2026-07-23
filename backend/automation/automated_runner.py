import time
from datetime import datetime
from pathlib import Path

from .excel_report import ExcelResultWriter
from .throughput_test import ThroughputTester


class AutomatedTestRunner:
    """Run repeated Titan throughput tests and record each result."""

    def __init__(
        self,
        titan,
        qxdm,
        session_folder: Path,
        iperf_server_ip: str,
        number_of_runs: int = 5,
        delay_between_runs: int = 10,
    ) -> None:
        self.titan = titan
        self.qxdm = qxdm
        self.session_folder = Path(session_folder)
        self.number_of_runs = number_of_runs
        self.delay_between_runs = delay_between_runs

        self.throughput = ThroughputTester(
            server_ip=iperf_server_ip,
            iperf_executable=Path("iperf3.exe"),
            duration_seconds=10,
        )

        self.excel = ExcelResultWriter(
            self.session_folder
            / "reports"
            / "Titan3_Automated_Results.xlsx"
        )

    def get_radio_metrics(self) -> dict:
        """
        Replace this once the Titan metric source is known.

        Possible sources:
        - Titan REST API
        - JSON status endpoint
        - SSH command
        - Diagnostic export
        - Web interface
        """
        return {
            "firmware_version": None,
            "carrier": None,
            "technology": None,
            "mode": None,
            "serving_band": None,
            "rsrp_dbm": None,
            "rssi_dbm": None,
            "sinr_db": None,
        }

    def determine_result(
        self,
        download_mbps: float | None,
        upload_mbps: float | None,
    ) -> str:
        """
        Example pass/fail rule.

        Replace these values with the team's official requirements.
        """
        minimum_download = 100
        minimum_upload = 20

        if download_mbps is None or upload_mbps is None:
            return "ERROR"

        if (
            download_mbps >= minimum_download
            and upload_mbps >= minimum_upload
        ):
            return "PASS"

        return "FAIL"

    def run(self) -> None:
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

            timestamp = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            connection_status = (
                "REACHABLE"
                if self.titan.ping()
                else "UNREACHABLE"
            )

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

            qxdm_log_path = (
                run_folder
                / f"run_{run_number:03d}.isf"
            )

            download_mbps = None
            upload_mbps = None
            notes = ""

            try:
                if connection_status != "REACHABLE":
                    raise RuntimeError(
                        "Titan is not reachable."
                    )

                print("Sending ModeOnline...")
                self.qxdm.mode_online()

                print("Running download test...")
                download_mbps = (
                    self.throughput.run_download_test()
                )

                print(
                    f"Download: {download_mbps} Mbps"
                )

                print("Running upload test...")
                upload_mbps = (
                    self.throughput.run_upload_test()
                )

                print(
                    f"Upload: {upload_mbps} Mbps"
                )

                radio_metrics = self.get_radio_metrics()

                overall_result = self.determine_result(
                    download_mbps=download_mbps,
                    upload_mbps=upload_mbps,
                )

            except Exception as error:
                radio_metrics = self.get_radio_metrics()
                overall_result = "ERROR"
                notes = str(error)

                print(f"Run failed: {error}")

            finally:
                try:
                    self.qxdm.mode_lpm()
                except Exception as error:
                    notes += (
                        f" ModeLPM error: {error}"
                    )

            result = {
                "timestamp": timestamp,
                "run_number": run_number,
                "titan_ip": self.titan.ip_address,
                "connection_status": connection_status,
                "download_mbps": download_mbps,
                "upload_mbps": upload_mbps,
                "overall_result": overall_result,
                "qxdm_log_path": str(qxdm_log_path),
                "notes": notes,
                **radio_metrics,
            }

            self.excel.append_result(result)

            print(
                f"Run {run_number} saved to Excel."
            )

            if run_number < self.number_of_runs:
                print(
                    f"Waiting {self.delay_between_runs} "
                    "seconds before the next run..."
                )

                time.sleep(self.delay_between_runs)

        print("\nAll automated test runs are complete.")