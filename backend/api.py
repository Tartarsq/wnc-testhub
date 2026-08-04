from __future__ import annotations

from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from automation.automated_runner import AutomatedTestRunner
from config import DEFAULT_TITAN_IP, RESULTS_FOLDER
from titan3 import Titan3
from utils import create_session_folder, create_session_folders


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