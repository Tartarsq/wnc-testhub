from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from automation.automated_runner import AutomatedTestRunner
from controllers.qxdm_controller import QXDMController
from controllers.syslog_controller import SyslogController
from titan3 import Titan3


ProgressCallback = Callable[[dict[str, Any]], None]


class TestWrapper:
    """
    Coordinate one WNC TestHub test session.

    Every session has one root folder containing:
        qxdm/
        throughput/
        syslog/
        metadata/

    QXDM has its own mode:
        manual
        automatic

    Throughput and syslog are independent collection options and are not
    controlled by the QXDM manual/automatic choice.
    """

    def __init__(
        self,
        qxdm: Optional[QXDMController] = None,
        syslog: Optional[SyslogController] = None,
    ) -> None:
        self.qxdm = qxdm or QXDMController()
        self.syslog = syslog or SyslogController()

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = re.sub(
            r'[^A-Za-z0-9._ -]+',
            '_',
            value,
        ).strip()

        cleaned = cleaned.replace(" ", "_")

        return cleaned or "WNC_Test"

    def create_workspace(
        self,
        save_root: Path,
        session_name: str,
        titan_ip: str,
        qxdm_mode: str,
    ) -> dict[str, Any]:
        save_root = Path(save_root).expanduser().resolve()
        save_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_name = self._safe_name(session_name)
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        session_folder = (
            save_root /
            f"{safe_name}_{timestamp}"
        ).resolve()

        qxdm_folder = session_folder / "qxdm"
        throughput_folder = session_folder / "throughput"
        syslog_folder = session_folder / "syslog"
        metadata_folder = session_folder / "metadata"

        for folder in (
            qxdm_folder,
            throughput_folder,
            syslog_folder,
            metadata_folder,
        ):
            folder.mkdir(
                parents=True,
                exist_ok=True,
            )

        metadata = {
            "session_name": session_name,
            "safe_name": safe_name,
            "titan_ip": titan_ip,
            "qxdm_mode": qxdm_mode,
            "created_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "status": "created",
            "session_folder": str(session_folder),
            "artifacts": {
                "qxdm": str(qxdm_folder),
                "throughput": str(throughput_folder),
                "syslog": str(syslog_folder),
            },
        }

        self.write_metadata(
            metadata_folder / "wrapper_session.json",
            metadata,
        )

        return metadata

    @staticmethod
    def write_metadata(
        metadata_path: Path,
        metadata: dict[str, Any],
    ) -> None:
        metadata_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        metadata_path.write_text(
            json.dumps(
                metadata,
                indent=2,
            ),
            encoding="utf-8",
        )

    def run(
        self,
        *,
        save_root: Path,
        session_name: str,
        titan_ip: str,
        qxdm_mode: str,
        number_of_runs: int,
        delay_between_runs: int,
        timeout_seconds: int,
        collect_qxdm: bool,
        collect_throughput: bool,
        collect_syslog: bool,
        qxdm_log_filename: str,
        qxdm_max_log_size_mb: int,
        load_mask: bool,
        continue_without_mask: bool,
        progress_callback: Optional[
            ProgressCallback
        ] = None,
    ) -> dict[str, Any]:
        normalized_qxdm_mode = (
            qxdm_mode.strip().lower()
        )

        if normalized_qxdm_mode not in {
            "manual",
            "automatic",
        }:
            raise ValueError(
                "QXDM mode must be either "
                "'manual' or 'automatic'."
            )

        session = self.create_workspace(
            save_root=save_root,
            session_name=session_name,
            titan_ip=titan_ip,
            qxdm_mode=normalized_qxdm_mode,
        )

        session_folder = Path(
            session["session_folder"]
        )
        qxdm_folder = Path(
            session["artifacts"]["qxdm"]
        )
        throughput_folder = Path(
            session["artifacts"]["throughput"]
        )
        syslog_folder = Path(
            session["artifacts"]["syslog"]
        )
        metadata_path = (
            session_folder /
            "metadata" /
            "wrapper_session.json"
        )

        session["status"] = "running"
        session["started_at"] = (
            datetime.now().isoformat(
                timespec="seconds"
            )
        )
        session["steps"] = []

        self.write_metadata(
            metadata_path,
            session,
        )

        def report(
            step: str,
            status: str,
            message: str,
            **extra: Any,
        ) -> None:
            item = {
                "step": step,
                "status": status,
                "message": message,
                "timestamp": (
                    datetime.now().isoformat(
                        timespec="seconds"
                    )
                ),
                **extra,
            }

            session["steps"].append(item)

            self.write_metadata(
                metadata_path,
                session,
            )

            if progress_callback is not None:
                progress_callback(item)

        syslog_started = False

        try:
            if collect_syslog:
                report(
                    "syslog",
                    "starting",
                    "Starting syslog collection.",
                )

                syslog_path = self.syslog.start(
                    syslog_folder,
                    base_name=self._safe_name(
                        session_name
                    ),
                )

                syslog_started = True

                session["syslog_path"] = str(
                    syslog_path.resolve()
                )

                report(
                    "syslog",
                    "running",
                    "Syslog collection is active.",
                    path=str(
                        syslog_path.resolve()
                    ),
                )

            if collect_qxdm:
                qxdm_name = (
                    Path(qxdm_log_filename)
                    .name
                    .strip()
                )

                if not qxdm_name:
                    qxdm_name = (
                        f"{self._safe_name(session_name)}.isf"
                    )

                if Path(qxdm_name).suffix == "":
                    qxdm_name += ".isf"

                qxdm_path = (
                    qxdm_folder /
                    qxdm_name
                ).resolve()

                self.qxdm.max_log_size_mb = min(
                    max(
                        int(qxdm_max_log_size_mb),
                        1,
                    ),
                    1024,
                )

                session["expected_qxdm_path"] = str(
                    qxdm_path
                )

                if normalized_qxdm_mode == "manual":
                    report(
                        "qxdm",
                        "manual_setup",
                        (
                            "Starting QXDM in manual mode. "
                            "TestHub will open the current "
                            "manual Item Store File setup "
                            "workflow before continuing."
                        ),
                        expected_path=str(
                            qxdm_path
                        ),
                    )

                    self.qxdm.start_logging(
                        log_path=qxdm_path,
                        load_mask=load_mask,
                        continue_without_mask=(
                            continue_without_mask
                        ),
                    )

                    report(
                        "qxdm",
                        "running",
                        (
                            "QXDM manual-mode capture "
                            "is active."
                        ),
                        expected_path=str(
                            qxdm_path
                        ),
                    )

                else:
                    report(
                        "qxdm",
                        "automatic_starting",
                        (
                            "Starting QXDM in automatic "
                            "mode using the controller's "
                            "automatic workflow."
                        ),
                        expected_path=str(
                            qxdm_path
                        ),
                    )

                    self.qxdm.start_logging(
                        log_path=qxdm_path,
                        load_mask=load_mask,
                        continue_without_mask=(
                            continue_without_mask
                        ),
                    )

                    report(
                        "qxdm",
                        "running",
                        (
                            "QXDM automatic-mode capture "
                            "is active."
                        ),
                        expected_path=str(
                            qxdm_path
                        ),
                    )

            if collect_throughput:
                report(
                    "throughput",
                    "starting",
                    "Starting throughput test runs.",
                )

                titan = Titan3(
                    ip_address=titan_ip
                )

                runner = AutomatedTestRunner(
                    titan=titan,
                    qxdm=None,
                    session_folder=(
                        throughput_folder
                    ),
                    number_of_runs=number_of_runs,
                    delay_between_runs=(
                        delay_between_runs
                    ),
                    timeout_seconds=(
                        timeout_seconds
                    ),
                    open_results_after_run=False,
                    progress_callback=None,
                )

                results = runner.run()

                session[
                    "throughput_results"
                ] = results

                session[
                    "throughput_report"
                ] = str(
                    runner.excel_path.resolve()
                )

                report(
                    "throughput",
                    "completed",
                    "Throughput testing completed.",
                    report_path=str(
                        runner.excel_path.resolve()
                    ),
                    completed_runs=len(results),
                )

            if collect_qxdm:
                report(
                    "qxdm",
                    "manual_stop_required",
                    (
                        "The selected QXDM capture is "
                        "still active. Stop/finalize it "
                        "using the currently validated "
                        "QXDM stop workflow, then use "
                        "Select Saved Log if TestHub "
                        "does not detect the final file."
                    ),
                )

            if syslog_started:
                syslog_path = self.syslog.stop()
                syslog_started = False

                report(
                    "syslog",
                    "completed",
                    "Syslog collection stopped.",
                    path=(
                        str(
                            syslog_path.resolve()
                        )
                        if syslog_path is not None
                        else None
                    ),
                )

            session["status"] = (
                "awaiting_qxdm_stop"
                if collect_qxdm
                else "completed"
            )

            session["finished_at"] = (
                datetime.now().isoformat(
                    timespec="seconds"
                )
            )

            self.write_metadata(
                metadata_path,
                session,
            )

            return session

        except Exception as error:
            if syslog_started:
                try:
                    self.syslog.stop()
                except Exception:
                    pass

            session["status"] = "failed"
            session["error"] = str(error)
            session["finished_at"] = (
                datetime.now().isoformat(
                    timespec="seconds"
                )
            )

            self.write_metadata(
                metadata_path,
                session,
            )

            raise