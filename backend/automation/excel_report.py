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
    "Result",
    "QXDM Log",
    "Notes",
]


class ExcelResultWriter:
    """Append automated test results to an Excel workbook."""

    def __init__(self, workbook_path: Path) -> None:
        self.workbook_path = Path(workbook_path)
        self.workbook_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _create_workbook(self) -> None:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Test Results"

        worksheet.append(HEADERS)

        for cell in worksheet[1]:
            cell.font = Font(bold=True)

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = (
            f"A1:Q{worksheet.max_row}"
        )

        workbook.save(self.workbook_path)

    def append_result(self, result: dict[str, Any]) -> None:
        if not self.workbook_path.exists():
            self._create_workbook()

        workbook = load_workbook(self.workbook_path)
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
                result.get("overall_result"),
                result.get("qxdm_log_path"),
                result.get("notes"),
            ]
        )

        worksheet.auto_filter.ref = (
            f"A1:Q{worksheet.max_row}"
        )

        workbook.save(self.workbook_path)