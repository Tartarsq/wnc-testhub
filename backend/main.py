from config import (
    DEFAULT_CARRIER,
    DEFAULT_MODE,
    DEFAULT_RESULT,
    DEFAULT_TECHNOLOGY,
    DEFAULT_TEST_TYPE,
    DEFAULT_TITAN_IP,
    RESULTS_FOLDER,
)
from logger import create_logger
from reports import generate_reports
from titan3 import Titan3
from utils import (
    create_session_folder,
    create_session_folders,
    get_readable_time,
    prompt_optional_float,
    prompt_with_default,
    prompt_yes_no,
)


def collect_test_data(titan: Titan3, connection_status: bool) -> dict:
    """Collect Titan 3 test information from the user."""
    print("\nEnter the Titan 3 test information.")
    print("Press Enter to accept any displayed default.\n")

    firmware = input("Firmware version: ").strip()

    carrier = prompt_with_default(
        "Carrier",
        DEFAULT_CARRIER,
    )

    technology = prompt_with_default(
        "Technology",
        DEFAULT_TECHNOLOGY,
    )

    mode = prompt_with_default(
        "Mode",
        DEFAULT_MODE,
    )

    serving_band = input("Serving band, such as n41 or B66: ").strip()

    rsrp = prompt_optional_float("RSRP in dBm")
    rssi = prompt_optional_float("RSSI in dBm")
    sinr = prompt_optional_float("SINR in dB")

    test_type = prompt_with_default(
        "Test type",
        DEFAULT_TEST_TYPE,
    )

    download_speed = prompt_optional_float(
        "Downlink throughput in Mbps"
    )

    upload_speed = prompt_optional_float(
        "Uplink throughput in Mbps"
    )

    overall_result = prompt_with_default(
        "Overall result",
        DEFAULT_RESULT,
    ).upper()

    notes = input("Notes: ").strip()

    return {
        "timestamp": get_readable_time(),
        "device": "Titan 3",
        "ip_address": titan.ip_address,
        "gui_url": titan.gui_url,
        "connection_status": "REACHABLE" if connection_status else "UNREACHABLE",
        "firmware_version": firmware,
        "carrier": carrier,
        "technology": technology,
        "mode": mode,
        "serving_band": serving_band,
        "rsrp_dbm": rsrp,
        "rssi_dbm": rssi,
        "sinr_db": sinr,
        "test_type": test_type,
        "downlink_mbps": download_speed,
        "uplink_mbps": upload_speed,
        "overall_result": overall_result,
        "notes": notes,
    }


def main() -> None:
    print("=" * 50)
    print("WNC TESTHUB - TITAN 3 TEST AUTOMATION")
    print("=" * 50)

    titan_ip = prompt_with_default(
        "Enter Titan 3 IP address",
        DEFAULT_TITAN_IP,
    )

    titan = Titan3(ip_address=titan_ip)

    session_folder = create_session_folder(
        RESULTS_FOLDER,
        "Titan3",
    )

    create_session_folders(session_folder)

    logger = create_logger(session_folder)

    logger.info("Titan 3 test session started.")
    logger.info("Results folder: %s", session_folder)
    logger.info("Testing connection to %s.", titan.ip_address)

    is_reachable = titan.ping()

    if is_reachable:
        logger.info("Titan 3 responded successfully.")
    else:
        logger.warning(
            "Titan 3 did not respond to ping at %s.",
            titan.ip_address,
        )

        continue_test = prompt_yes_no(
            "Continue the test anyway?",
            default=True,
        )

        if not continue_test:
            logger.info("Test cancelled by the user.")
            print("\nTest cancelled.")
            return

    open_gui = prompt_yes_no(
        f"Open the Titan Web GUI at {titan.gui_url}?",
        default=True,
    )

    if open_gui:
        browser_started = titan.open_gui()

        if browser_started:
            logger.info("Titan Web GUI opened.")
        else:
            logger.warning("The browser could not be opened.")

    test_data = collect_test_data(
        titan=titan,
        connection_status=is_reachable,
    )

    logger.info("Generating test reports.")

    report_paths = generate_reports(
        session_folder=session_folder,
        test_data=test_data,
    )

    logger.info("Test reports generated successfully.")
    logger.info("Overall result: %s", test_data["overall_result"])

    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)
    print(f"Result: {test_data['overall_result']}")
    print(f"Results folder: {session_folder}")

    print("\nGenerated files:")
    for report_path in report_paths:
        print(f"  - {report_path.name}")

    print("  - test_session.log")


if __name__ == "__main__":
    main()