from config import (
    DEFAULT_CARRIER,
    DEFAULT_MODE,
    DEFAULT_RESULT,
    DEFAULT_TECHNOLOGY,
    DEFAULT_TEST_TYPE,
    DEFAULT_TITAN_IP,
    QXDM_DEFAULT_LOG_FILENAME,
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
    qxdm_log_path,
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
        "qxdm_log_path": (
            str(qxdm_log_path)
            if qxdm_log_path is not None
            else ""
        ),
        "overall_result": overall_result,
        "notes": notes,
    }


def start_qxdm_logging(
    qxdm: QXDMController,
    logger,
    session_folder,
):
    """
    Prepare the QXDM log path and start the automated logging workflow.

    Returns:
        tuple[bool, Path | None]:
            Whether logging started and the configured log path.
    """
    should_start = prompt_yes_no(
        "Start QXDM logging?",
        default=True,
    )

    if not should_start:
        logger.info(
            "The user skipped QXDM logging startup."
        )
        return False, None

    qxdm_log_path = (
        session_folder
        / "captures"
        / "qxdm"
        / QXDM_DEFAULT_LOG_FILENAME
    )

    try:
        logger.info("Preparing QXDM logging.")
        logger.info(
            "Requested QXDM log path: %s",
            qxdm_log_path,
        )

        print("\nPreparing QXDM logging...")
        print(f"Log destination: {qxdm_log_path}")

        qxdm.start_logging(
            log_path=qxdm_log_path,
            load_mask=True,
        )

        logger.info(
            "QXDM logging started successfully."
        )

        print("\nQXDM logging started successfully.")
        print(f"Log file: {qxdm_log_path}")

        return True, qxdm_log_path

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

        return False, qxdm_log_path


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
            "Switch QXDM to ModeLPM and stop the "
            "capture manually before continuing."
        )

        input(
            "Press Enter after manually stopping QXDM logging..."
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
    qxdm_log_path = None

    try:
        print("\n" + "=" * 50)
        print("QXDM LOGGING")
        print("=" * 50)

        print(
            "\nThe application will attempt to:"
            "\n  1. Create the QXDM log destination."
            "\n  2. Launch QXDM."
            "\n  3. Load the configured default log mask."
            "\n  4. Set the log file location."
            "\n  5. Limit the log size to 1024 MB."
            "\n  6. Start capture."
            "\n  7. Send ModeLPM."
            "\n  8. Send ModeOnline."
        )

        ready_for_qxdm = prompt_yes_no(
            "Is Titan 3 connected and ready for QXDM?",
            default=True,
        )

        if ready_for_qxdm:
            (
                qxdm_logging_started,
                qxdm_log_path,
            ) = start_qxdm_logging(
                qxdm=qxdm,
                logger=logger,
                session_folder=session_folder,
            )

        else:
            logger.warning(
                "Titan 3 was not ready for QXDM. "
                "Logging was skipped."
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
        qxdm_log_path=qxdm_log_path,
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

    if qxdm_log_path is not None:
        print(f"QXDM log path: {qxdm_log_path}")

    print(f"Results folder: {session_folder}")

    print("\nGenerated files:")

    for report_path in report_paths:
        print(f"  - reports/{report_path.name}")

    print("  - logs/test_session.log")


if __name__ == "__main__":
    main()