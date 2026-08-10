from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openpyxl import load_workbook

from automation.automated_runner import AutomatedTestRunner
from config import (
    DEFAULT_TITAN_IP,
    QXDM_DEFAULT_LOG_FILENAME,
    QXDM_DEFAULT_MASK,
    QXDM_EXECUTABLE,
    QXDM_MAX_LOG_SIZE_MB,
    RESULTS_FOLDER,
)
from controllers.qxdm_controller import QXDMController
from titan3 import Titan3
from utils import (
    create_session_folder,
    create_session_folders,
    create_session_record,
    find_session_record,
    list_session_records,
)


app = FastAPI(
    title="WNC TestHub API",
    version="1.0.0",
)

# Allow the Vite React frontend to call this backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# Throughput models and state
# ==========================================================

class ThroughputRequest(BaseModel):
    titan_ip: str = Field(
        default=DEFAULT_TITAN_IP,
        min_length=7,
        max_length=45,
    )
    number_of_runs: int = Field(
        default=5,
        ge=1,
        le=15,
    )
    delay_between_runs: int = Field(
        default=10,
        ge=0,
        le=3600,
    )
    timeout_seconds: int = Field(
        default=180,
        ge=1,
        le=1800,
    )


class ThroughputJob(BaseModel):
    job_id: str
    status: str
    message: str
    titan_ip: str
    number_of_runs: int
    completed_runs: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    session_folder: str | None = None
    excel_path: str | None = None


class SessionCreateRequest(BaseModel):
    session_name: str = Field(
        min_length=1,
        max_length=120,
    )
    titan_ip: str = Field(
        default=DEFAULT_TITAN_IP,
        min_length=7,
        max_length=45,
    )
    notes: str = Field(
        default="",
        max_length=2000,
    )


class TestSession(BaseModel):
    session_id: str
    session_name: str
    titan_ip: str
    notes: str = ""
    status: str
    created_at: str
    updated_at: str
    session_folder: str
    throughput_jobs: list[dict[str, Any]] = Field(
        default_factory=list
    )
    qxdm_logs: list[dict[str, Any]] = Field(
        default_factory=list
    )
    reports: list[dict[str, Any]] = Field(
        default_factory=list
    )


class AnalyticsSummary(BaseModel):
    total_runs: int = 0
    average_download_mbps: float | None = None
    minimum_download_mbps: float | None = None
    maximum_download_mbps: float | None = None
    average_upload_mbps: float | None = None
    minimum_upload_mbps: float | None = None
    maximum_upload_mbps: float | None = None
    average_ping_ms: float | None = None
    average_jitter_ms: float | None = None


class AnalyticsResponse(BaseModel):
    summary: AnalyticsSummary
    history: list[dict[str, Any]] = Field(default_factory=list)


jobs: dict[str, dict[str, Any]] = {}
jobs_lock = Lock()


def update_job(
    job_id: str,
    **changes: Any,
) -> None:
    with jobs_lock:
        current_job = jobs.get(job_id)

        if current_job is None:
            return

        current_job.update(changes)


def run_throughput_job(
    job_id: str,
    request: ThroughputRequest,
) -> None:
    try:
        update_job(
            job_id,
            status="running",
            message=(
                f"Running throughput test 1 of "
                f"{request.number_of_runs}."
            ),
            completed_runs=0,
            results=[],
            error=None,
        )

        titan = Titan3(
            ip_address=request.titan_ip,
        )

        session_folder = create_session_folder(
            RESULTS_FOLDER,
            "Titan3_API",
        )

        create_session_folders(
            session_folder
        )

        def report_progress(
            completed_runs: int,
            total_runs: int,
            partial_results: list[dict[str, Any]],
        ) -> None:
            if completed_runs >= total_runs:
                progress_message = (
                    "All throughput test runs are complete."
                )
            else:
                next_run = completed_runs + 1
                progress_message = (
                    f"Completed {completed_runs} of {total_runs} runs. "
                    f"Preparing run {next_run}."
                )

            update_job(
                job_id,
                status="running",
                message=progress_message,
                completed_runs=completed_runs,
                results=partial_results,
            )

        runner = AutomatedTestRunner(
            titan=titan,
            qxdm=None,
            session_folder=session_folder,
            number_of_runs=request.number_of_runs,
            delay_between_runs=request.delay_between_runs,
            timeout_seconds=request.timeout_seconds,
            open_results_after_run=False,
            progress_callback=report_progress,
        )

        results = runner.run()

        update_job(
            job_id,
            status="completed",
            message="Throughput testing completed successfully.",
            completed_runs=len(results),
            results=results,
            session_folder=str(session_folder.resolve()),
            excel_path=str(runner.excel_path.resolve()),
        )

    except Exception as error:
        update_job(
            job_id,
            status="failed",
            message="Throughput testing failed.",
            error=str(error),
        )


# ==========================================================
# QXDM models and state
# ==========================================================

class QXDMStartRequest(BaseModel):
    log_filename: str = Field(
        default=QXDM_DEFAULT_LOG_FILENAME,
        min_length=1,
        max_length=180,
    )
    output_folder: str | None = Field(
        default=None,
        max_length=500,
    )
    max_log_size_mb: int = Field(
        default=QXDM_MAX_LOG_SIZE_MB,
        ge=1,
        le=1024,
    )
    load_mask: bool = True
    continue_without_mask: bool = True
    session_id: str | None = Field(
        default=None,
        max_length=64,
    )


class QXDMStatus(BaseModel):
    status: str
    message: str
    workflow_step: str = "idle"
    manual_settings_required: bool = False
    installed: bool
    process_running: bool
    logging_active: bool
    executable_path: str
    mask_path: str | None = None
    expected_log_path: str | None = None
    current_log_path: str | None = None
    current_log_size_bytes: int = 0
    current_log_size_mb: float = 0.0
    current_log_filename: str | None = None
    current_log_modified_at: str | None = None
    max_log_size_mb: int
    started_at: str | None = None
    stopped_at: str | None = None
    session_id: str | None = None
    session_name: str | None = None
    error: str | None = None


qxdm_controller = QXDMController()
qxdm_lock = Lock()

qxdm_state: dict[str, Any] = {
    "status": "idle",
    "message": "QXDM logging is idle.",
    "workflow_step": "idle",
    "manual_settings_required": False,
    "logging_active": False,
    "expected_log_path": None,
    "current_log_path": None,
    "started_at": None,
    "stopped_at": None,
    "session_id": None,
    "session_name": None,
    "error": None,
}


def update_qxdm_state(
    **changes: Any,
) -> None:
    with qxdm_lock:
        qxdm_state.update(changes)


def find_current_qxdm_log() -> Path | None:
    configured_path = qxdm_controller.current_log_path

    if configured_path is None:
        return None

    configured_path = Path(configured_path)

    if configured_path.exists() and configured_path.is_file():
        return configured_path

    try:
        candidates = [
            candidate
            for candidate in configured_path.parent.glob(
                f"{configured_path.stem}*"
            )
            if candidate.is_file()
        ]
    except OSError:
        return None

    if not candidates:
        return None

    try:
        return max(
            candidates,
            key=lambda candidate: candidate.stat().st_mtime,
        )
    except OSError:
        return None


def build_qxdm_status() -> QXDMStatus:
    with qxdm_lock:
        state_snapshot = dict(qxdm_state)

    current_log = find_current_qxdm_log()
    current_size_bytes = 0

    if current_log is not None:
        try:
            current_size_bytes = current_log.stat().st_size
        except OSError:
            current_size_bytes = 0

    configured_mask = qxdm_controller.resolve_default_mask()

    return QXDMStatus(
        status=state_snapshot["status"],
        message=state_snapshot["message"],
        workflow_step=state_snapshot.get("workflow_step", "idle"),
        manual_settings_required=state_snapshot.get(
            "manual_settings_required",
            False,
        ),
        installed=qxdm_controller.executable_exists(),
        process_running=qxdm_controller.is_running(),
        logging_active=state_snapshot["logging_active"],
        executable_path=str(QXDM_EXECUTABLE),
        mask_path=(
            str(configured_mask)
            if configured_mask is not None
            else None
        ),
        expected_log_path=state_snapshot.get(
            "expected_log_path"
        ),
        current_log_path=(
            str(current_log.resolve())
            if current_log is not None
            else None
        ),
        current_log_size_bytes=current_size_bytes,
        current_log_size_mb=round(
            current_size_bytes / (1024 * 1024),
            2,
        ),
        current_log_filename=(
            current_log.name
            if current_log is not None
            else None
        ),
        current_log_modified_at=(
            datetime.fromtimestamp(
                current_log.stat().st_mtime
            ).isoformat(timespec="seconds")
            if current_log is not None
            else None
        ),
        max_log_size_mb=qxdm_controller.max_log_size_mb,
        started_at=state_snapshot["started_at"],
        stopped_at=state_snapshot["stopped_at"],
        session_id=state_snapshot.get("session_id"),
        session_name=state_snapshot.get("session_name"),
        error=state_snapshot["error"],
    )



def resolve_qxdm_session(
    session_id: str | None,
) -> dict[str, Any] | None:
    if not session_id:
        return None

    session = find_session_record(
        results_folder=RESULTS_FOLDER,
        session_id=session_id,
    )

    if session is None:
        raise ValueError(
            "The selected test session was not found."
        )

    return session


def save_qxdm_log_to_session(
    session_id: str | None,
    log_path: Path | None,
    started_at: str | None,
    stopped_at: str | None,
) -> None:
    if not session_id or log_path is None:
        return

    session = find_session_record(
        results_folder=RESULTS_FOLDER,
        session_id=session_id,
    )

    if session is None:
        return

    qxdm_logs = list(
        session.get("qxdm_logs", [])
    )

    resolved_path = str(
        Path(log_path).resolve()
    )

    if not any(
        item.get("log_path") == resolved_path
        for item in qxdm_logs
    ):
        qxdm_logs.append(
            {
                "log_path": resolved_path,
                "filename": Path(resolved_path).name,
                "started_at": started_at,
                "stopped_at": stopped_at,
                "size_bytes": (
                    Path(resolved_path).stat().st_size
                    if Path(resolved_path).exists()
                    else 0
                ),
            }
        )

    session["qxdm_logs"] = qxdm_logs
    session["status"] = "completed"
    session["updated_at"] = datetime.now().isoformat(
        timespec="seconds"
    )

    session_folder = Path(
        session["session_folder"]
    ).resolve()

    metadata_path = (
        session_folder
        / "metadata"
        / "session.json"
    )

    metadata_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    import json

    metadata_path.write_text(
        json.dumps(
            session,
            indent=2,
        ),
        encoding="utf-8",
    )


def run_qxdm_start(
    request: QXDMStartRequest,
) -> None:
    try:
        session = resolve_qxdm_session(
            request.session_id
        )

        # The QXDM log location is user-controlled. If a folder is entered
        # in TestHub, always honor it even when a test session is selected.
        # The session still receives the log metadata after capture stops.
        output_folder = (
            Path(request.output_folder).expanduser()
            if request.output_folder
            else RESULTS_FOLDER / "qxdm_logs"
        )

        output_folder = output_folder.resolve()
        output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_filename = Path(
            request.log_filename
        ).name.strip()

        if not safe_filename:
            raise ValueError(
                "A QXDM log filename is required."
            )

        if Path(safe_filename).suffix == "":
            safe_filename = f"{safe_filename}.isf"

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        filename_path = Path(safe_filename)
        timestamped_filename = (
            f"{filename_path.stem}_{timestamp}"
            f"{filename_path.suffix}"
        )

        suggested_log_path = (
            output_folder / timestamped_filename
        ).resolve()

        qxdm_controller.max_log_size_mb = min(
            max(int(request.max_log_size_mb), 1),
            1024,
        )

        session_name = (
            session.get("session_name")
            if session is not None
            else None
        )

        update_qxdm_state(
            status="starting",
            workflow_step="launching",
            message="Launching QXDM and waiting for the diagnostic USB connection.",
            manual_settings_required=False,
            logging_active=False,
            expected_log_path=str(suggested_log_path),
            current_log_path=None,
            started_at=None,
            stopped_at=None,
            session_id=request.session_id,
            session_name=session_name,
            error=None,
        )

        # The controller loads the DMC, opens QXDM Settings, and displays
        # its Continue confirmation window while the user chooses the
        # actual Item Store File save settings.
        update_qxdm_state(
            workflow_step="manual_save_settings",
            message=(
                "QXDM is preparing the capture. After the short delay, "
                "Settings will remain open while you manually enter or "
                "confirm the QXDM save location. TestHub will wait until "
                "you close Settings and click Continue."
            ),
            manual_settings_required=True,
        )

        qxdm_controller.start_logging(
            log_path=suggested_log_path,
            load_mask=request.load_mask,
            continue_without_mask=request.continue_without_mask,
        )

        detected_log = find_current_qxdm_log()
        actual_log_path = (
            str(detected_log.resolve())
            if detected_log is not None
            else None
        )

        update_qxdm_state(
            status="logging",
            workflow_step="capture_active",
            message="QXDM capture is active.",
            manual_settings_required=False,
            logging_active=True,
            current_log_path=actual_log_path,
            started_at=datetime.now().isoformat(
                timespec="seconds"
            ),
            stopped_at=None,
            session_id=request.session_id,
            session_name=session_name,
            error=None,
        )

    except Exception as error:
        update_qxdm_state(
            status="failed",
            workflow_step="failed",
            message="QXDM logging failed to start.",
            manual_settings_required=False,
            logging_active=False,
            error=str(error),
        )


def run_qxdm_stop() -> None:
    try:
        with qxdm_lock:
            state_snapshot = dict(qxdm_state)

        update_qxdm_state(
            status="stopping",
            workflow_step="stopping",
            message="Stopping and finalizing the QXDM log while leaving the modem online.",
            manual_settings_required=False,
            error=None,
        )

        qxdm_controller.stop_logging(
            load_saved_log=True,
        )

        completed_log = find_current_qxdm_log()
        stopped_at = datetime.now().isoformat(
            timespec="seconds"
        )

        save_qxdm_log_to_session(
            session_id=state_snapshot.get("session_id"),
            log_path=completed_log,
            started_at=state_snapshot.get("started_at"),
            stopped_at=stopped_at,
        )

        update_qxdm_state(
            status="completed",
            workflow_step="completed",
            message=(
                "QXDM logging stopped. The modem remains online."
            ),
            manual_settings_required=False,
            logging_active=False,
            current_log_path=(
                str(completed_log.resolve())
                if completed_log is not None
                else None
            ),
            stopped_at=stopped_at,
            error=None,
        )

    except Exception as error:
        update_qxdm_state(
            status="failed",
            workflow_step="failed",
            message="QXDM logging failed to stop cleanly.",
            manual_settings_required=False,
            logging_active=False,
            error=str(error),
        )


# ==========================================================
# Analytics helpers
# ==========================================================

ANALYTICS_FIELDS = [
    "timestamp", "run_number", "titan_ip", "connection_status",
    "download_mbps", "upload_mbps", "ping_ms", "ping_jitter_ms",
    "packet_loss_percent", "test_duration_seconds", "isp",
    "external_ip", "interface_name", "server_name", "server_location",
    "result_url", "firmware_version", "carrier", "technology", "mode",
    "serving_band", "rsrp_dbm", "rssi_dbm", "sinr_db",
    "metrics_error", "notes",
]

def _to_float(value: Any) -> float | None:
    if value is None or value == "": return None
    try: return float(value)
    except (TypeError, ValueError): return None

def load_analytics_history() -> list[dict[str, Any]]:
    history=[]
    if not RESULTS_FOLDER.exists(): return history
    for workbook_path in RESULTS_FOLDER.rglob("*.xlsx"):
        try: wb=load_workbook(workbook_path,read_only=True,data_only=True)
        except Exception: continue
        try:
            if "Throughput Results" not in wb.sheetnames: continue
            for row in wb["Throughput Results"].iter_rows(min_row=2,values_only=True):
                if not any(v is not None for v in row): continue
                rec={f:(row[i] if i < len(row) else None) for i,f in enumerate(ANALYTICS_FIELDS)}
                ts=rec.get("timestamp")
                if isinstance(ts,datetime): rec["timestamp"]=ts.isoformat(timespec="seconds")
                elif ts is not None: rec["timestamp"]=str(ts)
                rec["workbook_path"]=str(workbook_path.resolve())
                rec["session_folder"]=str(workbook_path.parent.parent.resolve())
                history.append(rec)
        finally: wb.close()
    history.sort(key=lambda x:str(x.get("timestamp") or ""),reverse=True)
    return history

def build_analytics_summary(history: list[dict[str, Any]]) -> AnalyticsSummary:
    def vals(k): return [v for x in history if (v:=_to_float(x.get(k))) is not None]
    d,u,p,j=vals("download_mbps"),vals("upload_mbps"),vals("ping_ms"),vals("ping_jitter_ms")
    avg=lambda x: round(sum(x)/len(x),2) if x else None
    return AnalyticsSummary(total_runs=len(history),average_download_mbps=avg(d),minimum_download_mbps=round(min(d),2) if d else None,maximum_download_mbps=round(max(d),2) if d else None,average_upload_mbps=avg(u),minimum_upload_mbps=round(min(u),2) if u else None,maximum_upload_mbps=round(max(u),2) if u else None,average_ping_ms=avg(p),average_jitter_ms=avg(j))


# ==========================================================
# General and device endpoints
# ==========================================================

@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {
        "status": "online",
        "service": "WNC TestHub API",
    }


@app.get("/api/device/status")
def get_device_status(
    titan_ip: str = DEFAULT_TITAN_IP,
) -> dict[str, Any]:
    titan = Titan3(
        ip_address=titan_ip,
    )

    reachable = titan.ping()

    device_status: dict[str, Any] = {
        "ip_address": titan.ip_address,
        "gui_url": titan.gui_url,
        "reachable": reachable,
        "status": (
            "connected"
            if reachable
            else "disconnected"
        ),
        "firmware_version": None,
        "carrier": None,
        "technology": None,
        "mode": None,
        "serving_band": None,
        "rsrp_dbm": None,
        "rssi_dbm": None,
        "sinr_db": None,
        "metrics_error": None,
    }

    if not reachable:
        device_status["metrics_error"] = (
            "Titan is not reachable."
        )

        return device_status

    try:
        metrics = titan.get_radio_metrics()

        if not isinstance(metrics, dict):
            raise TypeError(
                "Titan radio metrics must be returned as a dictionary."
            )

        device_status.update(metrics)

    except Exception as error:
        device_status["metrics_error"] = str(error)

    return device_status




# ==========================================================
# Analytics endpoints
# ==========================================================

@app.get("/api/analytics/history", response_model=list[dict[str, Any]])
def get_analytics_history() -> list[dict[str, Any]]:
    return load_analytics_history()

@app.get("/api/analytics/summary", response_model=AnalyticsSummary)
def get_analytics_summary() -> AnalyticsSummary:
    return build_analytics_summary(load_analytics_history())

@app.get("/api/analytics", response_model=AnalyticsResponse)
def get_analytics() -> AnalyticsResponse:
    history=load_analytics_history()
    return AnalyticsResponse(summary=build_analytics_summary(history),history=history)


# ==========================================================
# Session endpoints
# ==========================================================

@app.post(
    "/api/sessions",
    response_model=TestSession,
    status_code=status.HTTP_201_CREATED,
)
def create_test_session(
    request: SessionCreateRequest,
) -> TestSession:
    session = create_session_record(
        results_folder=RESULTS_FOLDER,
        session_name=request.session_name,
        titan_ip=request.titan_ip,
        notes=request.notes,
    )

    return TestSession(**session)


@app.get(
    "/api/sessions",
    response_model=list[TestSession],
)
def get_test_sessions() -> list[TestSession]:
    sessions = list_session_records(
        RESULTS_FOLDER
    )

    return [
        TestSession(**session)
        for session in sessions
    ]


@app.get(
    "/api/sessions/{session_id}",
    response_model=TestSession,
)
def get_test_session(
    session_id: str,
) -> TestSession:
    session = find_session_record(
        results_folder=RESULTS_FOLDER,
        session_id=session_id,
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test session was not found.",
        )

    return TestSession(**session)


# ==========================================================
# Throughput endpoints
# ==========================================================

@app.post(
    "/api/throughput/start",
    response_model=ThroughputJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_throughput_test(
    request: ThroughputRequest,
    background_tasks: BackgroundTasks,
) -> ThroughputJob:
    job_id = str(uuid4())

    job = {
        "job_id": job_id,
        "status": "queued",
        "message": "Throughput testing has been queued.",
        "titan_ip": request.titan_ip,
        "number_of_runs": request.number_of_runs,
        "completed_runs": 0,
        "results": [],
        "error": None,
        "session_folder": None,
        "excel_path": None,
    }

    with jobs_lock:
        jobs[job_id] = job

    background_tasks.add_task(
        run_throughput_job,
        job_id,
        request,
    )

    return ThroughputJob(**job)


@app.get(
    "/api/throughput/status/{job_id}",
    response_model=ThroughputJob,
)
def get_throughput_status(
    job_id: str,
) -> ThroughputJob:
    with jobs_lock:
        job = jobs.get(job_id)

        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Throughput job was not found.",
            )

        return ThroughputJob(**job)


@app.get(
    "/api/throughput/results/{job_id}",
    response_model=ThroughputJob,
)
def get_throughput_results(
    job_id: str,
) -> ThroughputJob:
    with jobs_lock:
        job = jobs.get(job_id)

        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Throughput job was not found.",
            )

        if job["status"] not in {"completed", "failed"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Throughput testing is still running.",
            )

        return ThroughputJob(**job)


# ==========================================================
# QXDM endpoints
# ==========================================================

@app.get(
    "/api/qxdm/status",
    response_model=QXDMStatus,
)
def get_qxdm_status() -> QXDMStatus:
    return build_qxdm_status()


@app.post(
    "/api/qxdm/start",
    response_model=QXDMStatus,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_qxdm_logging(
    request: QXDMStartRequest,
    background_tasks: BackgroundTasks,
) -> QXDMStatus:
    with qxdm_lock:
        if qxdm_state["status"] in {
            "starting",
            "logging",
            "stopping",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "QXDM is already starting, logging, "
                    "or stopping."
                ),
            )

    if not qxdm_controller.executable_exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "QXDM executable was not found at "
                f"{QXDM_EXECUTABLE}."
            ),
        )

    update_qxdm_state(
        status="starting",
        workflow_step="queued",
        message="QXDM logging start has been queued.",
        manual_settings_required=False,
        logging_active=False,
        error=None,
    )

    background_tasks.add_task(
        run_qxdm_start,
        request,
    )

    return build_qxdm_status()


@app.post(
    "/api/qxdm/saved-log/select",
    response_model=QXDMStatus,
)
def select_saved_qxdm_log() -> QXDMStatus:
    """
    Let the user identify the actual QXDM log saved on this Windows machine.

    This does not change the existing QXDM start/stop workflow. It is a
    fallback for captures whose final filename or folder was changed manually
    inside QXDM Settings.
    """
    try:
        selected_log = qxdm_controller.prompt_for_saved_log()

        if selected_log is None:
            return build_qxdm_status()

        with qxdm_lock:
            state_snapshot = dict(qxdm_state)

        stopped_at = (
            state_snapshot.get("stopped_at")
            or datetime.now().isoformat(timespec="seconds")
        )

        update_qxdm_state(
            current_log_path=str(selected_log.resolve()),
            stopped_at=stopped_at,
            message="Saved QXDM log selected successfully.",
            error=None,
        )

        save_qxdm_log_to_session(
            session_id=state_snapshot.get("session_id"),
            log_path=selected_log,
            started_at=state_snapshot.get("started_at"),
            stopped_at=stopped_at,
        )

        return build_qxdm_status()

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error


@app.post(
    "/api/qxdm/saved-log/open-folder",
    response_model=QXDMStatus,
)
def open_saved_qxdm_log_folder() -> QXDMStatus:
    """
    Open File Explorer with the currently tracked saved QXDM log selected.
    """
    current_log = find_current_qxdm_log()

    if current_log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No saved QXDM log is currently tracked. "
                "Select the saved log first."
            ),
        )

    try:
        qxdm_controller.open_saved_log_folder(
            current_log
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error

    return build_qxdm_status()


@app.post(
    "/api/qxdm/stop",
    response_model=QXDMStatus,
    status_code=status.HTTP_202_ACCEPTED,
)
def stop_qxdm_logging(
    background_tasks: BackgroundTasks,
) -> QXDMStatus:
    with qxdm_lock:
        if not qxdm_state["logging_active"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="QXDM logging is not currently active.",
            )

        if qxdm_state["status"] == "stopping":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="QXDM logging is already stopping.",
            )

    update_qxdm_state(
        status="stopping",
        workflow_step="stopping",
        message="QXDM logging stop has been queued.",
        manual_settings_required=False,
        error=None,
    )

    background_tasks.add_task(
        run_qxdm_stop,
    )

    return build_qxdm_status()