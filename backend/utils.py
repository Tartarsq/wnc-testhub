from datetime import datetime
from pathlib import Path


def get_timestamp() -> str:
    """Return a timestamp suitable for folder and file names."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def get_readable_time() -> str:
    """Return a human-readable date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_session_folder(results_folder: Path, device_name: str) -> Path:
    """
    Create a timestamped folder for a test session.

    Example:
    results/Titan3_2026-07-20_15-30-00
    """
    folder_name = f"{device_name}_{get_timestamp()}"
    session_folder = results_folder / folder_name
    session_folder.mkdir(parents=True, exist_ok=True)

    return session_folder


def prompt_with_default(message: str, default: str) -> str:
    """Prompt the user and return the default when nothing is entered."""
    value = input(f"{message} [{default}]: ").strip()

    if value:
        return value

    return default


def prompt_optional_float(message: str) -> float | None:
    """
    Prompt for a decimal number.

    The user may press Enter to leave the value blank.
    """
    while True:
        value = input(f"{message}: ").strip()

        if not value:
            return None

        try:
            return float(value)
        except ValueError:
            print("Please enter a valid number, such as -91 or 512.5.")


def prompt_yes_no(message: str, default: bool = True) -> bool:
    """Prompt the user for a yes or no answer."""
    default_text = "Y/n" if default else "y/N"
    value = input(f"{message} [{default_text}]: ").strip().lower()

    if not value:
        return default

    return value in {"y", "yes"}