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

from automation.automated_runner import AutomatedTestRunner
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


def prompt_positive_integer(
    message: str,
    default: int,
) -> int:
    """
    Ask the user for a positive integer.

    Pressing Enter returns the supplied default.
    """

    while True:
        value = input(
            f"{message} [{default}]: "
        ).strip()

        if not value:
            return default

        try:
            number = int(value)

            if number <= 0:
                raise ValueError

            return number

        except ValueError:
            print(
                "Enter a positive whole number, "
                "such as 5 or 10."
            )


def collect_test_data(
    titan: Titan3,
    connection_status: bool,
    qxdm_logging_started: bool,
    qxdm_logging_stopped: bool,
    qxdm_log_path,
    automated_testing_used: bool,
    automated_run_count: int,
    automated_excel_path,
) -> dict:
    """
    Collect session-level Titan 3 test information.

    Throughput values are recorded automatically in the Excel
    workbook when automated testing is enabled.
    """

    print("\nEnter the Titan 3 session information.")
    print("Press Enter to accept any displayed default.\n")

    firmware = input(
        "Firmware version: "
    ).strip()

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

    rsrp = prompt_optional_float(
        "RSRP in dBm"
    )

    rssi = prompt_optional_float(
        "RSSI in dBm"
    )

    sinr = prompt_optional_float(
        "SINR in dB"
    )

    test_type = prompt_with_default(
        "Test type",
        DEFAULT_TEST_TYPE,
    )

    if automated_testing_used:
        print(
            "\nThroughput results were recorded automatically "
            "for each test run."
        )

        download_speed = None
        upload_speed = None

    else:
        download_speed = prompt_optional_float(
            "Downlink throughput in Mbps"
        )

        upload_speed = prompt_optional_float(
            "Uplink throughput in Mbps"
        )

    overall_result = prompt_with_default(
        "Overall session result",
        DEFAULT_RESULT,
    ).upper()

    notes = input(
        "Notes: "
    ).strip()

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
        "automated_testing_used": automated_testing_used,
        "automated_run_count": automated_run_count,
        "automated_excel_path": (
            str(automated_excel_path)
            if automated_excel_path is not None
            else ""
        ),
        "overall_result": overall_result,
        "notes": notes,
    }


def wait_for_usb_connection(
    titan: Titan3,
    logger,
) -> bool:
    """
    Wait for the user to connect the Titan 3 USB cable.

    After each confirmation, the program checks whether Titan
    responds at its configured IP address.
    """

    print("\n" + "=" * 50)
    print("TITAN 3 USB CONNECTION")
    print("=" * 50)

    while True:
        input(
            "\nConnect the Titan 3 USB cable.\n"
            "Press Enter after the USB cable is connected..."
        )

        print(
            f"\nChecking Titan 3 connection at "
            f"{titan.ip_address}..."
        )

        is_reachable = titan.ping()

        if is_reachable:
            logger.info(
                "Titan 3 was detected after USB connection."
            )

            print(
                "\nTitan 3 is connected and reachable."
            )

            return True

        logger.warning(
            "Titan 3 was not reachable after the user "
            "connected the USB cable."
        )

        print(
            "\nTitan 3 is not responding at "
            f"{titan.ip_address}."
        )

        retry_connection = prompt_yes_no(
            "Check the USB connection and try again?",
            default=True,
        )

        if retry_connection:
            continue

        continue_anyway = prompt_yes_no(
            "Continue even though Titan 3 is unreachable?",
            default=False,
        )

        if continue_anyway:
            logger.warning(
                "The user continued without a confirmed "
                "Titan 3 connection."
            )

            return False

        logger.info(
            "The test was cancelled because Titan 3 "
            "was not connected."
        )

        raise RuntimeError(
            "Test cancelled because Titan 3 was not connected."
        )


def start_qxdm_logging(
    qxdm: QXDMController,
    logger,
    session_folder,
):
    """
    Launch QXDM, load the configured DMC file, and prepare capture.

    The user currently confirms the capture start because this QXDM
    version does not expose the expected Start Logging menu path.
    """

    should_start = prompt_yes_no(
        "Start the QXDM setup?",
        default=True,
    )

    if not should_start:
        logger.info(
            "The user skipped the QXDM setup."
        )

        return False, None

    qxdm_log_path = (
        session_folder
        / "captures"
        / "qxdm"
        / QXDM_DEFAULT_LOG_FILENAME
    )

    qxdm_log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        print("\n" + "=" * 50)
        print("QXDM AUTOMATED SETUP")
        print("=" * 50)

        print(
            "\nThe application will:"
            "\n  1. Launch or focus QXDM."
            "\n  2. Open File > Load Configuration."
            "\n  3. Load the configured DMC file."
            "\n  4. Wait for configuration confirmation."
            "\n  5. Ask you to start the QXDM capture."
            "\n  6. Send ModeLPM."
            "\n  7. Send ModeOnline."
        )

        print(
            f"\nRequested QXDM capture path:\n"
            f"{qxdm_log_path}"
        )

        logger.info(
            "Launching QXDM."
        )

        qxdm.launch()

        logger.info(
            "QXDM launched or focused successfully."
        )

        print(
            "\nQXDM is open."
        )

        input(
            "\nVerify that QXDM can see the connected device.\n"
            "Press Enter to load the DMC configuration..."
        )

        logger.info(
            "Loading the configured QXDM DMC file."
        )

        mask_loaded = qxdm.load_default_mask()

        if mask_loaded:
            logger.info(
                "The QXDM DMC configuration was loaded."
            )

            print(
                "\nThe configured DMC file was loaded."
            )

        else:
            logger.warning(
                "No default QXDM DMC configuration was loaded."
            )

            print(
                "\nNo default DMC configuration was loaded."
            )

        configuration_ready = prompt_yes_no(
            "Did the QXDM configuration load correctly?",
            default=True,
        )

        if not configuration_ready:
            print(
                "\nLoad the correct DMC configuration "
                "manually in QXDM."
            )

            input(
                "Press Enter after the configuration "
                "has been loaded..."
            )

            logger.warning(
                "The QXDM configuration required "
                "manual confirmation."
            )

        print(
            "\nIn QXDM, start the capture and set its "
            "destination to:"
        )

        print(
            qxdm_log_path
        )

        input(
            "\nPress Enter after the QXDM capture "
            "has started..."
        )

        logger.info(
            "The user confirmed that QXDM capture started."
        )

        print(
            "\nPreparing the modem for testing..."
        )

        qxdm.mode_lpm()

        logger.info(
            "ModeLPM was sent successfully."
        )

        qxdm.mode_online()

        logger.info(
            "ModeOnline was sent successfully."
        )

        print(
            "\nQXDM capture is running."
        )

        print(
            "Titan 3 is in online mode."
        )

        print(
            f"Capture path: {qxdm_log_path}"
        )

        return True, qxdm_log_path

    except Exception as error:
        logger.exception(
            "The QXDM setup could not be completed."
        )

        print(
            "\nThe QXDM setup could not be completed."
        )

        print(
            f"Reason: {error}"
        )

        continue_test = prompt_yes_no(
            "Continue the Titan 3 test without QXDM capture?",
            default=True,
        )

        if not continue_test:
            raise RuntimeError(
                "Test cancelled because the QXDM "
                "setup could not be completed."
            ) from error

        return False, qxdm_log_path


def run_automated_tests(
    titan: Titan3,
    qxdm: QXDMController,
    logger,
    session_folder,
) -> tuple[bool, int, object]:
    """
    Configure and run repeated automated Speedtest CLI tests.

    Returns:
        tuple:
            automated testing used,
            number of requested runs,
            Excel workbook path
    """

    print("\n" + "=" * 50)
    print("AUTOMATED THROUGHPUT TESTING")
    print("=" * 50)

    should_run = prompt_yes_no(
        "Run automated throughput tests?",
        default=True,
    )

    if not should_run:
        logger.info(
            "The user skipped automated throughput testing."
        )

        return False, 0, None

    number_of_runs = prompt_positive_integer(
        "Number of automated test runs",
        default=5,
    )

    delay_between_runs = prompt_positive_integer(
        "Delay between runs in seconds",
        default=10,
    )

    speedtest_timeout = prompt_positive_integer(
        "Speedtest timeout in seconds",
        default=180,
    )

    speedtest_executable = prompt_with_default(
        "Speedtest executable path",
        "speedtest.exe",
    )

    excel_path = (
        session_folder
        / "reports"
        / "Titan3_Automated_Results.xlsx"
    )

    print("\nAutomated test configuration:")
    print(f"  Runs: {number_of_runs}")
    print(f"  Delay: {delay_between_runs} seconds")
    print(
        f"  Speedtest timeout: "
        f"{speedtest_timeout} seconds"
    )
    print(
        f"  Speedtest executable: "
        f"{speedtest_executable}"
    )
    print(f"  Excel output: {excel_path}")

    input(
        "\nMake sure the official Ookla Speedtest CLI "
        "is installed.\n"
        "Press Enter to begin the automated tests..."
    )

    logger.info(
        "Starting automated throughput testing."
    )

    logger.info(
        "Requested runs: %s",
        number_of_runs,
    )

    logger.info(
        "Speedtest executable: %s",
        speedtest_executable,
    )

    try:
        runner = AutomatedTestRunner(
            titan=titan,
            qxdm=qxdm,
            session_folder=session_folder,
            number_of_runs=number_of_runs,
            delay_between_runs=delay_between_runs,
            speedtest_executable=speedtest_executable,
            timeout_seconds=speedtest_timeout,
        )

        runner.run()

        logger.info(
            "Automated throughput testing completed."
        )

        print(
            "\nAutomated throughput testing completed."
        )

        print(
            f"Excel results: {excel_path}"
        )

        return True, number_of_runs, excel_path

    except Exception as error:
        logger.exception(
            "Automated throughput testing failed."
        )

        print(
            "\nAutomated throughput testing failed."
        )

        print(
            f"Reason: {error}"
        )

        continue_session = prompt_yes_no(
            "Continue the session and generate the "
            "remaining reports?",
            default=True,
        )

        if not continue_session:
            raise RuntimeError(
                "Test session cancelled because automated "
                "throughput testing failed."
            ) from error

        return True, number_of_runs, excel_path


def stop_qxdm_logging(
    qxdm: QXDMController,
    logger,
    logging_started: bool,
) -> bool:
    """
    Place the modem into low-power mode and allow the user
    to stop and save the QXDM capture.
    """

    if not logging_started:
        logger.info(
            "QXDM capture was not started, so no stop "
            "procedure was required."
        )

        return False

    input(
        "\nPress Enter when all validation testing is complete "
        "and you are ready to stop QXDM..."
    )

    try:
        logger.info(
            "Preparing to stop the QXDM capture."
        )

        print(
            "\nSending ModeLPM before stopping capture..."
        )

        qxdm.mode_lpm()

        logger.info(
            "ModeLPM was sent before capture stop."
        )

        print(
            "\nStop and save the QXDM capture "
            "using the QXDM toolbar."
        )

        input(
            "Press Enter after the QXDM capture "
            "has been stopped and saved..."
        )

        capture_stopped = prompt_yes_no(
            "Was the QXDM capture stopped successfully?",
            default=True,
        )

        if capture_stopped:
            logger.info(
                "The user confirmed that the QXDM "
                "capture stopped successfully."
            )

            print(
                "\nQXDM capture stopped successfully."
            )

            return True

        logger.warning(
            "The user could not confirm that the "
            "QXDM capture stopped."
        )

        print(
            "\nQXDM capture stop was not confirmed."
        )

        return False

    except Exception as error:
        logger.exception(
            "The QXDM stop procedure failed."
        )

        print(
            "\nThe QXDM stop procedure could not "
            "be completed automatically."
        )

        print(
            f"Reason: {error}"
        )

        print(
            "\nSwitch QXDM to ModeLPM and stop the "
            "capture manually."
        )

        input(
            "Press Enter after manually stopping "
            "and saving the capture..."
        )

        logger.warning(
            "The user was instructed to stop the "
            "QXDM capture manually."
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

    titan = Titan3(
        ip_address=titan_ip
    )

    qxdm = QXDMController()

    session_folder = create_session_folder(
        RESULTS_FOLDER,
        "Titan3",
    )

    create_session_folders(
        session_folder
    )

    logger = create_logger(
        session_folder / "logs"
    )

    logger.info(
        "Titan 3 test session started."
    )

    logger.info(
        "Results folder: %s",
        session_folder,
    )

    try:
        is_reachable = wait_for_usb_connection(
            titan=titan,
            logger=logger,
        )

    except RuntimeError as error:
        logger.error(
            "%s",
            error,
        )

        print(
            f"\n{error}"
        )

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

    automated_testing_used = False
    automated_run_count = 0
    automated_excel_path = None

    try:
        print("\n" + "=" * 50)
        print("QXDM CAPTURE")
        print("=" * 50)

        (
            qxdm_logging_started,
            qxdm_log_path,
        ) = start_qxdm_logging(
            qxdm=qxdm,
            logger=logger,
            session_folder=session_folder,
        )

        (
            automated_testing_used,
            automated_run_count,
            automated_excel_path,
        ) = run_automated_tests(
            titan=titan,
            qxdm=qxdm,
            logger=logger,
            session_folder=session_folder,
        )

        qxdm_logging_stopped = stop_qxdm_logging(
            qxdm=qxdm,
            logger=logger,
            logging_started=qxdm_logging_started,
        )

    except RuntimeError as error:
        logger.error(
            "%s",
            error,
        )

        print(
            f"\n{error}"
        )

        return

    test_data = collect_test_data(
        titan=titan,
        connection_status=is_reachable,
        qxdm_logging_started=qxdm_logging_started,
        qxdm_logging_stopped=qxdm_logging_stopped,
        qxdm_log_path=qxdm_log_path,
        automated_testing_used=automated_testing_used,
        automated_run_count=automated_run_count,
        automated_excel_path=automated_excel_path,
    )

    logger.info(
        "Generating test reports."
    )

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
        f"Result: "
        f"{test_data['overall_result']}"
    )

    print(
        f"Titan connection: "
        f"{test_data['connection_status']}"
    )

    print(
        "QXDM capture started: "
        f"{'YES' if qxdm_logging_started else 'NO'}"
    )

    print(
        "QXDM capture stopped: "
        f"{'YES' if qxdm_logging_stopped else 'NO'}"
    )

    print(
        "Automated testing used: "
        f"{'YES' if automated_testing_used else 'NO'}"
    )

    if automated_testing_used:
        print(
            f"Automated runs requested: "
            f"{automated_run_count}"
        )

    if qxdm_log_path is not None:
        print(
            f"QXDM capture path: "
            f"{qxdm_log_path}"
        )

    if automated_excel_path is not None:
        print(
            f"Automated Excel results: "
            f"{automated_excel_path}"
        )

    print(
        f"Results folder: "
        f"{session_folder}"
    )

    print(
        "\nGenerated files:"
    )

    for report_path in report_paths:
        print(
            f"  - reports/{report_path.name}"
        )

    if automated_excel_path is not None:
        print(
            "  - reports/"
            f"{automated_excel_path.name}"
        )

    print(
        "  - logs/test_session.log"
    )


if __name__ == "__main__":
    main()