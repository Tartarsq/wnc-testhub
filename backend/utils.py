from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def get_timestamp() -> str:
    """Return a timestamp suitable for folder and file names."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def get_readable_time() -> str:
    """Return a human-readable date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sanitize_folder_name(value: str) -> str:
    """Return a Windows-safe folder name."""
    cleaned = re.sub(
        r'[<>:"/\\|?*]+',
        "_",
        value.strip(),
    )

    cleaned = re.sub(
        r"\s+",
        "_",
        cleaned,
    )

    cleaned = cleaned.strip(" ._")

    return cleaned or "Untitled_Session"


def create_session_folder(
    results_folder: Path,
    device_name: str,
) -> Path:
    """
    Create a timestamped folder for a legacy test session.

    Example:
    results/Titan3_2026-07-20_15-30-00
    """
    folder_name = (
        f"{sanitize_folder_name(device_name)}_"
        f"{get_timestamp()}"
    )

    session_folder = (
        Path(results_folder).resolve()
        / folder_name
    )

    session_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    return session_folder


def create_named_session_folder(
    results_folder: Path,
    session_name: str,
    session_id: str,
) -> Path:
    """
    Create a persistent named TestHub session folder.

    Example:
    results/sessions/
    Session_2026-08-04_Throughput_Test_ab12cd34/
    """
    safe_name = sanitize_folder_name(session_name)
    short_id = session_id.replace("-", "")[:8]

    folder_name = (
        f"Session_{get_timestamp()}_"
        f"{safe_name}_{short_id}"
    )

    session_folder = (
        Path(results_folder).resolve()
        / "sessions"
        / folder_name
    )

    session_folder.mkdir(
        parents=True,
        exist_ok=False,
    )

    create_session_folders(session_folder)

    return session_folder


def create_session_folders(
    session_folder: Path,
) -> None:
    """
    Create the standard folder structure for a test session.

    Example:
    Session_2026-08-04_14-30-00/
    ├── captures/
    │   ├── qxdm/
    │   └── pcap/
    ├── reports/
    ├── metadata/
    └── logs/
    """
    session_folder = Path(
        session_folder
    ).resolve()

    folders = [
        session_folder / "captures" / "qxdm",
        session_folder / "captures" / "pcap",
        session_folder / "reports",
        session_folder / "metadata",
        session_folder / "logs",
    ]

    for folder in folders:
        folder.mkdir(
            parents=True,
            exist_ok=True,
        )


def create_session_record(
    results_folder: Path,
    session_name: str,
    titan_ip: str,
    notes: str = "",
) -> dict[str, Any]:
    """
    Create a persistent TestHub session and save session.json.
    """
    session_id = str(uuid4())

    session_folder = create_named_session_folder(
        results_folder=results_folder,
        session_name=session_name,
        session_id=session_id,
    )

    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

    session = {
        "session_id": session_id,
        "session_name": session_name.strip(),
        "titan_ip": titan_ip.strip(),
        "notes": notes.strip(),
        "status": "created",
        "created_at": created_at,
        "updated_at": created_at,
        "session_folder": str(
            session_folder.resolve()
        ),
        "throughput_jobs": [],
        "qxdm_logs": [],
        "reports": [],
    }

    write_session_record(
        session_folder=session_folder,
        session=session,
    )

    return session


def get_session_metadata_path(
    session_folder: Path,
) -> Path:
    """Return the session.json path for a session."""
    return (
        Path(session_folder).resolve()
        / "metadata"
        / "session.json"
    )


def write_session_record(
    session_folder: Path,
    session: dict[str, Any],
) -> Path:
    """Write session metadata to disk."""
    session_folder = Path(
        session_folder
    ).resolve()

    create_session_folders(
        session_folder
    )

    metadata_path = get_session_metadata_path(
        session_folder
    )

    session_to_write = dict(session)
    session_to_write["updated_at"] = (
        datetime.now().isoformat(
            timespec="seconds"
        )
    )

    metadata_path.write_text(
        json.dumps(
            session_to_write,
            indent=2,
        ),
        encoding="utf-8",
    )

    return metadata_path


def read_session_record(
    session_folder: Path,
) -> dict[str, Any]:
    """Read one session.json file."""
    metadata_path = get_session_metadata_path(
        session_folder
    )

    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Session metadata was not found: "
            f"{metadata_path}"
        )

    return json.loads(
        metadata_path.read_text(
            encoding="utf-8"
        )
    )


def list_session_records(
    results_folder: Path,
) -> list[dict[str, Any]]:
    """Return all persisted TestHub sessions."""
    sessions_root = (
        Path(results_folder).resolve()
        / "sessions"
    )

    if not sessions_root.exists():
        return []

    sessions: list[dict[str, Any]] = []

    for metadata_path in sessions_root.glob(
        "*/metadata/session.json"
    ):
        try:
            session = json.loads(
                metadata_path.read_text(
                    encoding="utf-8"
                )
            )

            sessions.append(session)

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
        ):
            continue

    sessions.sort(
        key=lambda session: session.get(
            "created_at",
            "",
        ),
        reverse=True,
    )

    return sessions


def find_session_record(
    results_folder: Path,
    session_id: str,
) -> dict[str, Any] | None:
    """Return one persisted session by ID."""
    for session in list_session_records(
        results_folder
    ):
        if session.get("session_id") == session_id:
            return session

    return None


def prompt_with_default(
    message: str,
    default: str,
) -> str:
    """Prompt the user and return the default when nothing is entered."""
    value = input(
        f"{message} [{default}]: "
    ).strip()

    if value:
        return value

    return default


def prompt_optional_float(
    message: str,
) -> float | None:
    """
    Prompt for a decimal number.

    The user may press Enter to leave the value blank.
    """
    while True:
        value = input(
            f"{message}: "
        ).strip()

        if not value:
            return None

        try:
            return float(value)
        except ValueError:
            print(
                "Please enter a valid number, "
                "such as -91 or 512.5."
            )


def prompt_yes_no(
    message: str,
    default: bool = True,
) -> bool:
    """Prompt the user for a yes or no answer."""
    default_text = (
        "Y/n"
        if default
        else "y/N"
    )

    value = input(
        f"{message} [{default_text}]: "
    ).strip().lower()

    if not value:
        return default

    return value in {
        "y",
        "yes",
    }