from __future__ import annotations

import csv
import os
import platform
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path


DEFAULT_DEVICE_IP = "192.168.1.1"
RESULTS_DIRECTORY = Path(__file__).resolve().parent.parent / "results"


def get_user_input(prompt: str, default: str = "") -> str:
    """Ask the user for a value and return the default if left blank."""
    if default:
        value = input(f"{prompt} [{default}]: ").strip()
        return value or default

    return input(f"{prompt}: ").strip()


def ping_device(ip_address: str) -> bool:
    """Return True if the device responds to a single ping."""
    count_flag = "-n" if platform.system() == "Windows" else "-c"

    try:
        result = subprocess.run(
            ["ping", count_flag, "1", ip_address],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return result.returncode == 0

    except subprocess.TimeoutExpired:
        return False

    except FileNotFoundError:
        print("ERROR: The ping command could not be found.")
        return False


def open_results_folder(folder: Path) -> None:
    """Open the saved results folder."""
    folder = folder.resolve()

    if platform.system() == "Windows":
        os.startfile(folder)  # type: ignore[attr-defined]

    elif platform.system() == "Darwin":
        subprocess.run(["open", str(folder)], check=False)

    else:
        subprocess.run(["xdg-open", str(folder)], check=False)


def save_results(result_folder: Path, results: dict[str, str]) -> None:
    """Save the test results as CSV and text files."""
    csv_path = result_folder / "test_result.csv"
    summary_path = result_folder / "test_summary.txt"

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=results.keys())
        writer.writeheader()
        writer.writerow(results)

    with summary_path.open("w", encoding="utf-8") as summary_file:
        summary_file.write("Titan 3 Test Summary\n")
        summary_file.write("=" * 40 + "\n\n")

        for field, value in results.items():
            readable_field = field.replace("_", " ").title()
            summary_file.write(f"{readable_field}: {value}\n")


def main() -> None:
    print("\n" + "=" * 55)
    print("Titan 3 Test Automation")
    print("=" * 55)

    device_ip = get_user_input(
        "Enter the Titan 3 IP address",
        DEFAULT_DEVICE_IP,
    )

    print(f"\nChecking connection to {device_ip}...")

    connected = ping_device(device_ip)

    if connected:
        print("SUCCESS: Titan 3 responded to ping.")

    else:
        print("WARNING: Titan 3 did not respond to ping.")

        continue_anyway = get_user_input(
            "Continue anyway? Enter y or n",
            "n",
        ).lower()

        if continue_anyway != "y":
            print("Test cancelled.")
            return

    gui_url = f"http://{device_ip}"

    print(f"\nOpening Titan 3 Web GUI at {gui_url}...")
    webbrowser.open(gui_url)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    result_folder = RESULTS_DIRECTORY / f"Titan3_{timestamp}"
    result_folder.mkdir(parents=True, exist_ok=True)

    print("\nUse the Titan 3 Web GUI and QXDM to obtain the values.")
    print("Press Enter to leave a field blank.\n")

    results = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "device": "Titan 3",
        "device_ip": device_ip,
        "connection_status": "Connected" if connected else "Not verified",
        "firmware": get_user_input("Firmware version"),
        "carrier": get_user_input("Carrier"),
        "technology": get_user_input(
            "Technology: NR, LTE, or UTRA",
            "NR",
        ),
        "mode": get_user_input(
            "Mode: NSA or SA",
            "NSA",
        ),
        "serving_band": get_user_input("Serving band"),
        "rsrp_dbm": get_user_input("RSRP in dBm"),
        "rssi_dbm": get_user_input("RSSI in dBm"),
        "sinr_db": get_user_input("SINR in dB"),
        "test_type": get_user_input(
            "Test type",
            "Wi-Fi throughput",
        ),
        "downlink_mbps": get_user_input(
            "Downlink throughput in Mbps"
        ),
        "uplink_mbps": get_user_input(
            "Uplink throughput in Mbps"
        ),
        "result": get_user_input(
            "Overall result: PASS or FAIL",
            "PASS",
        ),
        "notes": get_user_input("Notes"),
    }

    save_results(result_folder, results)

    print("\n" + "=" * 55)
    print("SUCCESS: Test session completed.")
    print(f"Results saved to: {result_folder.resolve()}")
    print("=" * 55)

    open_results_folder(result_folder)


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print("\n\nTest stopped by the user.")

    except Exception as error:
        print(f"\nERROR: {error}")