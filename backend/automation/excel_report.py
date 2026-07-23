from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font


HEADERS = [
    "Timestamp",
    "Run",
    "Titan IP",
    "Connection",
    "Firmware",
    "Carrier",
    "Technology",
    "Mode",
    "Band",
    "RSRP dBm",
    "RSSI dBm",
    "SINR dB",
    "Download Mbps",
    "Upload Mbps",
    "Ping ms",
    "Jitter ms",
    "Packet Loss %",
    "ISP",
    "External IP",
    "Interface",
    "Server Name",
    "Server Location",
    "Result URL",
    "Overall Result",
    "Run Folder",
    "Notes",
]


class ExcelResultWriter:
    """Append automated test results to an Excel workbook."""

    def __init__(
        self,
        workbook_path: Path,
    ) -> None:
        self.workbook_path = Path(workbook_path)

        self.workbook_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _create_workbook(self) -> None:
        """Create the workbook and header row."""
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Test Results"

        worksheet.append(HEADERS)

        for cell in worksheet[1]:
            cell.font = Font(bold=True)

        worksheet.freeze_panes = "A2"

        worksheet.auto_filter.ref = (
            f"A1:Z{worksheet.max_row}"
        )

        workbook.save(self.workbook_path)

    def _adjust_column_widths(
        self,
        worksheet,
    ) -> None:
        """Resize columns so values are easier to read."""
        for column_cells in worksheet.columns:
            column_letter = (
                column_cells[0].column_letter
            )

            maximum_length = max(
                (
                    len(str(cell.value))
                    for cell in column_cells
                    if cell.value is not None
                ),
                default=0,
            )

            worksheet.column_dimensions[
                column_letter
            ].width = min(
                maximum_length + 2,
                45,
            )

    def append_result(
        self,
        result: dict[str, Any],
    ) -> None:
        """Append one automated test result to the workbook."""
        if not self.workbook_path.exists():
            self._create_workbook()

        workbook = load_workbook(
            self.workbook_path
        )

        worksheet = workbook["Test Results"]

        worksheet.append(
            [
                result.get(
                    "timestamp",
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                ),
                result.get("run_number"),
                result.get("titan_ip"),
                result.get("connection_status"),
                result.get("firmware_version"),
                result.get("carrier"),
                result.get("technology"),
                result.get("mode"),
                result.get("serving_band"),
                result.get("rsrp_dbm"),
                result.get("rssi_dbm"),
                result.get("sinr_db"),
                result.get("download_mbps"),
                result.get("upload_mbps"),
                result.get("ping_ms"),
                result.get("ping_jitter_ms"),
                result.get(
                    "packet_loss_percent"
                ),
                result.get("isp"),
                result.get("external_ip"),
                result.get("interface_name"),
                result.get("server_name"),
                result.get("server_location"),
                result.get("result_url"),
                result.get("overall_result"),
                result.get("run_folder"),
                result.get("notes"),
            ]
        )

        worksheet.auto_filter.ref = (
            f"A1:Z{worksheet.max_row}"
        )

        self._adjust_column_widths(
            worksheet
        )

        workbook.save(
            self.workbook_path
        )