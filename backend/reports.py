import csv
import json
from pathlib import Path
from typing import Any


def save_csv_report(session_folder: Path, test_data: dict[str, Any]) -> Path:
    """Save the test results as a one-row CSV file."""
    report_path = session_folder / "test_result.csv"

    with report_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=test_data.keys())
        writer.writeheader()
        writer.writerow(test_data)

    return report_path


def save_text_report(session_folder: Path, test_data: dict[str, Any]) -> Path:
    """Save a readable text summary."""
    report_path = session_folder / "test_summary.txt"

    with report_path.open("w", encoding="utf-8") as text_file:
        text_file.write("WNC TESTHUB - TITAN 3 TEST SUMMARY\n")
        text_file.write("=" * 45 + "\n\n")

        for key, value in test_data.items():
            readable_key = key.replace("_", " ").title()
            displayed_value = value if value not in {None, ""} else "Not provided"

            text_file.write(f"{readable_key}: {displayed_value}\n")

    return report_path


def save_json_report(session_folder: Path, test_data: dict[str, Any]) -> Path:
    """Save structured test data for future dashboard use."""
    report_path = session_folder / "test_result.json"

    with report_path.open("w", encoding="utf-8") as json_file:
        json.dump(test_data, json_file, indent=4)

    return report_path


def generate_reports(
    session_folder: Path,
    test_data: dict[str, Any],
) -> list[Path]:
    """Generate all currently supported report formats."""
    return [
        save_csv_report(session_folder, test_data),
        save_text_report(session_folder, test_data),
        save_json_report(session_folder, test_data),
    ]