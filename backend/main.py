from config import (
    DEFAULT_CARRIER,
    DEFAULT_MODE,
    DEFAULT_RESULT,
    DEFAULT_TECHNOLOGY,
    DEFAULT_TEST_TYPE,
    DEFAULT_TITAN_IP,
    RESULTS_FOLDER,
)
from controllers.qxdm_controller import QXDMController
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


def collect_test_data(
    titan: Titan3,
    connection_status: bool,
    qxdm_logging_started: bool,
    qxdm_logging_stopped: bool,
) -> dict:
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

    serving_band = input(
        "Serving band, such as n41 or B66: "
    ).strip()

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
        "connection_status": (
            "REACHABLE"
            if connection_status
            else "UNREACHABLE"
        ),
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
        "qxdm_logging_started": qxdm_logging_started,
        "qxdm_logging_stopped": qxdm_logging_stopped,
        "overall_result": overall_result,
        "notes": notes,
    }


def start_qxdm_logging(
    qxdm: QXDMController,
    logger,
) -> bool:
    """Prompt the user and start QXDM logging."""
    should_start = prompt_yes_no(
        "Start QXDM logging?",
        default=True,
    )

    if not should_start:
        logger.info(
            "The user skipped QXDM logging startup."
        )
        return False

    try:
        logger.info("Starting QXDM logging.")

        qxdm.start_logging()

        logger.info(
            "QXDM logging started successfully."
        )

        print("\nQXDM logging started successfully.")
        return True

    except Exception as error:
        logger.exception(
            "QXDM logging could not be started."
        )

        print(
            "\nQXDM logging could not be started."
        )
        print(f"Reason: {error}")

        continue_test = prompt_yes_no(
            "Continue the Titan 3 test without QXDM logging?",
            default=True,
        )

        if not continue_test:
            raise RuntimeError(
                "Test cancelled because QXDM logging "
                "could not be started."
            ) from error

        return False


def stop_qxdm_logging(
    qxdm: QXDMController,
    logger,
    logging_started: bool,
) -> bool:
    """Stop QXDM logging if it was previously started."""
    if not logging_started:
        logger.info(
            "QXDM logging was not started, so no stop "
            "command was required."
        )
        return False

    input(
        "\nPerform the Titan 3 validation test now.\n"
        "Press Enter when you are ready to stop QXDM logging..."
    )

    try:
        logger.info("Stopping QXDM logging.")

        qxdm.stop_logging()

        logger.info(
            "QXDM logging stopped successfully."
        )

        print("\nQXDM logging stopped successfully.")
        return True

    except Exception as error:
        logger.exception(
            "QXDM logging could not be stopped."
        )

        print(
            "\nQXDM logging could not be stopped automatically."
        )
        print(f"Reason: {error}")
        print(
            "Switch QXDM to ModeLPM manually before continuing."
        )

        input(
            "Press Enter after manually switching to ModeLPM..."
        )

        logger.warning(
            "The user was instructed to stop QXDM logging "
            "manually."
        )

        return False


def main() -> None:
    print("=" * 50)
    print("WNC TESTHUB - TITAN 3 TEST AUTOMATION")
    print("=" * 50)

    titan_ip = prompt_with_default(
        "Enter Titan 3 IP address",
        DEFAULT_TITAN_IP,
    )

    titan = Titan3(ip_address=titan_ip)
    qxdm = QXDMController()

    session_folder = create_session_folder(
        RESULTS_FOLDER,
        "Titan3",
    )

    create_session_folders(session_folder)

    logger = create_logger(
        session_folder / "logs"
    )

    logger.info("Titan 3 test session started.")
    logger.info(
        "Results folder: %s",
        session_folder,
    )
    logger.info(
        "Testing connection to %s.",
        titan.ip_address,
    )

    is_reachable = titan.ping()

    if is_reachable:
        logger.info(
            "Titan 3 responded successfully."
        )
        print("\nTitan 3 is reachable.")

    else:
        logger.warning(
            "Titan 3 did not respond to ping at %s.",
            titan.ip_address,
        )

        print(
            f"\nTitan 3 did not respond at "
            f"{titan.ip_address}."
        )

        continue_test = prompt_yes_no(
            "Continue the test anyway?",
            default=True,
        )

        if not continue_test:
            logger.info(
                "Test cancelled by the user."
            )
            print("\nTest cancelled.")
            return

    open_gui = prompt_yes_no(
        f"Open the Titan Web GUI at {titan.gui_url}?",
        default=True,
    )

    if open_gui:
        browser_started = titan.open_gui()

        if browser_started:
            logger.info(
                "Titan Web GUI opened."
            )
        else:
            logger.warning(
                "The browser could not be opened."
            )

    qxdm_logging_started = False
    qxdm_logging_stopped = False

    try:
        print("\n" + "=" * 50)
        print("QXDM LOGGING")
        print("=" * 50)

        print(
            "\nBefore starting, make sure:"
            "\n  1. Titan 3 is connected."
            "\n  2. QXDM can access the correct COM port."
            "\n  3. The correct DMC filter is loaded."
        )

        ready_for_qxdm = prompt_yes_no(
            "Is QXDM ready?",
            default=True,
        )

        if ready_for_qxdm:
            qxdm_logging_started = start_qxdm_logging(
                qxdm=qxdm,
                logger=logger,
            )
        else:
            logger.warning(
                "QXDM was not ready. Logging was skipped."
            )
            print("\nQXDM logging was skipped.")

        qxdm_logging_stopped = stop_qxdm_logging(
            qxdm=qxdm,
            logger=logger,
            logging_started=qxdm_logging_started,
        )

    except RuntimeError as error:
        logger.error("%s", error)
        print(f"\n{error}")
        return

    test_data = collect_test_data(
        titan=titan,
        connection_status=is_reachable,
        qxdm_logging_started=qxdm_logging_started,
        qxdm_logging_stopped=qxdm_logging_stopped,
    )

    logger.info("Generating test reports.")

    report_paths = generate_reports(
        session_folder=session_folder,
        test_data=test_data,
    )

    logger.info(
        "Test reports generated successfully."
    )
    logger.info(
        "Overall result: %s",
        test_data["overall_result"],
    )

    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)

    print(
        f"Result: {test_data['overall_result']}"
    )
    print(
        f"Titan connection: "
        f"{test_data['connection_status']}"
    )

    print(
        "QXDM logging started: "
        f"{'YES' if qxdm_logging_started else 'NO'}"
    )

    print(
        "QXDM logging stopped: "
        f"{'YES' if qxdm_logging_stopped else 'NO'}"
    )

    print(f"Results folder: {session_folder}")

    print("\nGenerated files:")

    for report_path in report_paths:
        print(f"  - reports/{report_path.name}")

    print("  - logs/test_session.log")


if __name__ == "__main__":
    main()