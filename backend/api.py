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
            message="Throughput testing is running.",
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

        runner = AutomatedTestRunner(
            titan=titan,
            qxdm=None,
            session_folder=session_folder,
            number_of_runs=request.number_of_runs,
            delay_between_runs=request.delay_between_runs,
            timeout_seconds=request.timeout_seconds,
            open_results_after_run=False,
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