from pathlib import Path
import time

import ipaddress
import platform
import re
import socket
import subprocess

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



def _is_valid_ipv4(value: str) -> bool:
    """Return True when value is a usable IPv4 address."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False

    return (
        address.version == 4
        and not address.is_loopback
        and not address.is_multicast
        and not address.is_unspecified
    )


def _add_candidate(
    candidates: list[str],
    value: str | None,
) -> None:
    """Add a unique, valid IPv4 address to the candidate list."""
    if not value:
        return

    value = value.strip()

    if _is_valid_ipv4(value) and value not in candidates:
        candidates.append(value)


def discover_titan_ip_candidates() -> list[str]:
    """
    Build a list of likely Titan 3 addresses.

    The preferred Titan address is listed first. On Windows, this also
    reads ipconfig, adds detected default gateways, and derives the .1
    address for each active private IPv4 subnet.
    """
    candidates: list[str] = []

    _add_candidate(candidates, "192.168.100.1")
    _add_candidate(candidates, DEFAULT_TITAN_IP)

    for common_address in (
        "192.168.1.1",
        "192.168.0.1",
        "192.168.225.1",
        "192.168.137.1",
    ):
        _add_candidate(candidates, common_address)

    if platform.system().lower() == "windows":
        try:
            completed = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )

            ipconfig_output = completed.stdout or ""

            ipv4_matches = re.findall(
                r"IPv4 Address[^:]*:\s*([0-9.]+)",
                ipconfig_output,
                flags=re.IGNORECASE,
            )

            for local_ip in ipv4_matches:
                if not _is_valid_ipv4(local_ip):
                    continue

                try:
                    address = ipaddress.ip_address(local_ip)

                    if address.is_private:
                        octets = local_ip.split(".")
                        subnet_device_ip = ".".join(
                            octets[:3] + ["1"]
                        )
                        _add_candidate(
                            candidates,
                            subnet_device_ip,
                        )
                except ValueError:
                    continue

            gateway_matches = re.findall(
                r"Default Gateway[^:]*:\s*([0-9.]+)",
                ipconfig_output,
                flags=re.IGNORECASE,
            )

            for gateway in gateway_matches:
                _add_candidate(candidates, gateway)

        except (
            OSError,
            subprocess.SubprocessError,
        ):
            pass

    return candidates


def check_titan_candidate(
    ip_address: str,
    port: int = 80,
) -> tuple[bool, bool]:
    """
    Check whether an address responds to ping and whether its web port opens.

    Returns:
        tuple:
            ping reachable,
            TCP port reachable
    """
    operating_system = platform.system().lower()

    if operating_system == "windows":
        ping_command = [
            "ping",
            "-n",
            "1",
            "-w",
            "700",
            ip_address,
        ]
    else:
        ping_command = [
            "ping",
            "-c",
            "1",
            "-W",
            "1",
            ip_address,
        ]

    try:
        ping_result = subprocess.run(
            ping_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=2,
        )
        ping_reachable = ping_result.returncode == 0
    except (
        OSError,
        subprocess.SubprocessError,
    ):
        ping_reachable = False

    try:
        with socket.create_connection(
            (ip_address, port),
            timeout=0.8,
        ):
            port_reachable = True
    except OSError:
        port_reachable = False

    return ping_reachable, port_reachable


def select_titan_ip() -> str:
    """
    Show likely Titan 3 IP addresses and let the user choose one.

    Reachable addresses are placed first. The user may also enter a
    completely different address manually.
    """
    print("\n" + "=" * 50)
    print("TITAN 3 IP FINDER")
    print("=" * 50)
    print("\nChecking likely Titan 3 addresses...")

    candidate_results: list[tuple[str, bool, bool]] = []

    for candidate in discover_titan_ip_candidates():
        ping_reachable, port_reachable = check_titan_candidate(
            candidate,
            port=80,
        )

        candidate_results.append(
            (
                candidate,
                ping_reachable,
                port_reachable,
            )
        )

    candidate_results.sort(
        key=lambda item: (
            not item[2],
            not item[1],
            item[0] != "192.168.100.1",
        )
    )

    print()

    for index, (
        candidate,
        ping_reachable,
        port_reachable,
    ) in enumerate(candidate_results, start=1):
        if port_reachable:
            status = "WEB PORT REACHABLE"
        elif ping_reachable:
            status = "PING REACHABLE"
        else:
            status = "NO RESPONSE"

        preferred = (
            "  [preferred Titan address]"
            if candidate == "192.168.100.1"
            else ""
        )

        print(
            f"  {index}. {candidate:<15} "
            f"{status}{preferred}"
        )

    manual_option = len(candidate_results) + 1

    print(
        f"  {manual_option}. Enter another IP address"
    )

    default_index = 1

    for index, result in enumerate(
        candidate_results,
        start=1,
    ):
        if result[0] == "192.168.100.1":
            default_index = index
            break

    while True:
        selection = input(
            f"\nSelect the Titan 3 address "
            f"[{default_index}]: "
        ).strip()

        if not selection:
            selection = str(default_index)

        try:
            selected_index = int(selection)
        except ValueError:
            print("Enter one of the displayed option numbers.")
            continue

        if 1 <= selected_index <= len(candidate_results):
            selected_ip = candidate_results[
                selected_index - 1
            ][0]

            print(
                f"\nSelected Titan 3 IP: {selected_ip}"
            )

            return selected_ip

        if selected_index == manual_option:
            while True:
                manual_ip = input(
                    "Enter the Titan 3 IPv4 address: "
                ).strip()

                if _is_valid_ipv4(manual_ip):
                    print(
                        f"\nSelected Titan 3 IP: {manual_ip}"
                    )

                    return manual_ip

                print(
                    "Enter a valid IPv4 address, "
                    "such as 192.168.100.1."
                )

        print("Enter one of the displayed option numbers.")

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
    Launch QXDM and guide the user through the configurable logging setup.

    The workflow preserves automatic DMC loading while allowing the user
    to choose the log folder, filename, size, and modem mode transitions.
    """
    should_start = prompt_yes_no(
        "Start the QXDM logging setup?",
        default=True,
    )

    if not should_start:
        logger.info(
            "The user skipped the QXDM logging setup."
        )
        return False, None

    print("\n" + "=" * 50)
    print("QXDM LOGGING SETUP")
    print("=" * 50)

    try:
        logger.info("Launching QXDM.")
        qxdm.launch()

        print("\nQXDM is open.")

        open_settings = prompt_yes_no(
            "Open QXDM Options > Settings before configuring the log?",
            default=True,
        )

        if open_settings:
            try:
                qxdm.open_qxdm_settings()

                print(
                    "\nReview or change the QXDM logging settings."
                )
                print(
                    "Save or apply the settings, then close the "
                    "Settings window."
                )

                input(
                    "Press Enter after the QXDM Settings window is closed..."
                )

            except Exception as settings_error:
                logger.warning(
                    "QXDM Settings could not be opened automatically: %s",
                    settings_error,
                )

                print(
                    "\nThe QXDM Settings window could not be opened "
                    "automatically."
                )
                print(
                    "Open Options > Settings manually if you need to "
                    "change additional QXDM preferences."
                )

                input(
                    "Press Enter when you are ready to continue..."
                )

        default_log_folder = (
            session_folder
            / "captures"
            / "qxdm"
        )

        log_folder_text = prompt_with_default(
            "QXDM log folder",
            str(default_log_folder),
        )

        log_filename = prompt_with_default(
            "QXDM log filename",
            QXDM_DEFAULT_LOG_FILENAME,
        )

        if not log_filename.lower().endswith(".isf"):
            log_filename = f"{log_filename}.isf"

        maximum_log_size_mb = prompt_positive_integer(
            "Maximum QXDM log size in MB",
            default=qxdm.max_log_size_mb,
        )

        maximum_log_size_mb = min(
            maximum_log_size_mb,
            1024,
        )

        if maximum_log_size_mb != qxdm.max_log_size_mb:
            qxdm.max_log_size_mb = maximum_log_size_mb

        qxdm_log_path = (
            Path(log_folder_text).expanduser()
            / log_filename
        ).resolve()

        qxdm_log_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        print("\nQXDM capture configuration:")
        print(f"  Folder: {qxdm_log_path.parent}")
        print(f"  Filename: {qxdm_log_path.name}")
        print(
            f"  Maximum size: {qxdm.max_log_size_mb} MB"
        )

        logger.info(
            "QXDM log path: %s",
            qxdm_log_path,
        )
        logger.info(
            "QXDM maximum log size: %s MB",
            qxdm.max_log_size_mb,
        )

        print(
            "\nLoading the QXDM DMC configuration..."
        )

        qxdm.ensure_default_mask_loaded(
            retry_with_picker=True,
        )

        logger.info(
            "The QXDM DMC configuration was loaded."
        )

        print(
            "\nConfiguring and starting the QXDM capture..."
        )

        qxdm.configure_logging(
            qxdm_log_path
        )

        logger.info(
            "QXDM capture started."
        )

        use_airplane_mode = prompt_yes_no(
            "Do you want to send the Titan 3 to airplane mode "
            "before testing?",
            default=True,
        )

        if use_airplane_mode:
            print(
                "\nSending mode lpm..."
            )
            qxdm.mode_lpm()
            logger.info(
                "mode lpm was sent automatically."
            )

            print(
                "\nWaiting for the modem to enter low-power mode..."
            )
            time.sleep(2)

            print(
                "\nSending mode online..."
            )
            qxdm.mode_online()
            logger.info(
                "mode online was sent automatically."
            )

            print(
                "\nWaiting for the modem to return online..."
            )
            time.sleep(2)

            print(
                "\nAirplane-mode transition completed."
            )

        else:
            logger.info(
                "The user chose not to use the airplane-mode transition."
            )

            print(
                "\nAirplane-mode transition skipped. "
                "mode lpm and mode online were not sent."
            )

        print(
            "\nQXDM capture is running."
        )
        print(
            f"Capture path: {qxdm_log_path}"
        )

        return True, qxdm_log_path

    except Exception as error:
        logger.exception(
            "The QXDM logging setup could not be completed."
        )

        print(
            "\nThe QXDM logging setup could not be completed."
        )
        print(
            f"Reason: {error}"
        )

        print(
            "\nYou can complete these steps manually in QXDM:"
            "\n  1. Open File > Load Configuration."
            "\n  2. Select the DMC file."
            "\n  3. Set the log name, folder, and maximum size."
            "\n  4. Start the capture."
            "\n  5. Send mode lpm and mode online if required."
        )

        manual_setup = prompt_yes_no(
            "Did you complete the QXDM setup manually?",
            default=False,
        )

        if manual_setup:
            logger.warning(
                "The user completed QXDM setup manually."
            )

            manual_path = input(
                "Enter the QXDM log path, or press Enter "
                "to leave it blank: "
            ).strip()

            use_airplane_mode = prompt_yes_no(
                "Do you want to send the Titan 3 to airplane mode "
                "before testing?",
                default=True,
            )

            if use_airplane_mode:
                print(
                    "\nSending mode lpm..."
                )
                qxdm.mode_lpm()
                logger.info(
                    "mode lpm was sent automatically after manual QXDM setup."
                )

                print(
                    "\nWaiting for the modem to enter low-power mode..."
                )
                time.sleep(2)

                print(
                    "\nSending mode online..."
                )
                qxdm.mode_online()
                logger.info(
                    "mode online was sent automatically after manual QXDM setup."
                )

                print(
                    "\nWaiting for the modem to return online..."
                )
                time.sleep(2)

                print(
                    "\nAirplane-mode transition completed."
                )

            else:
                logger.info(
                    "The user skipped the airplane-mode transition "
                    "after manual QXDM setup."
                )

                print(
                    "\nAirplane-mode transition skipped. "
                    "mode lpm and mode online were not sent."
                )

            return (
                True,
                Path(manual_path).expanduser().resolve()
                if manual_path
                else None,
            )

        continue_test = prompt_yes_no(
            "Continue without QXDM capture?",
            default=True,
        )

        if not continue_test:
            raise RuntimeError(
                "Test cancelled because QXDM logging "
                "could not be started."
            ) from error

        return False, None


def run_automated_tests(
    titan: Titan3,
    qxdm: QXDMController,
    logger,
    session_folder,
) -> tuple[bool, int, object]:
    """
    Configure and run repeated official Ookla Speedtest CLI tests.

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

    excel_path = (
        session_folder
        / "reports"
        / "Titan3_Automated_Results.xlsx"
    )

    print("\nAutomated test configuration:")
    print(f"  Runs: {number_of_runs}")
    print(f"  Delay: {delay_between_runs} seconds")
    print("  Throughput method: Python speedtest-cli library")
    print(f"  Excel output: {excel_path}")

    input(
        "\nMake sure the Python speedtest-cli package is installed.\n"
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
        "Throughput method: Official Ookla Speedtest CLI."
    )

    try:
        runner = AutomatedTestRunner(
            titan=titan,
            qxdm=qxdm,
            session_folder=session_folder,
            number_of_runs=number_of_runs,
            delay_between_runs=delay_between_runs,
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
    Automatically stop QXDM capture, wait for the log to finish saving,
    and reopen the completed log in QXDM.
    """
    if not logging_started:
        logger.info(
            "QXDM capture was not started, so no stop procedure was required."
        )
        return False

    input(
        "\nPress Enter when all validation testing is complete "
        "and you are ready to stop QXDM..."
    )

    try:
        logger.info(
            "Stopping and finalizing the QXDM capture."
        )

        qxdm.stop_logging(
            load_saved_log=True,
        )

        logger.info(
            "QXDM capture stopped, saved, and reopened successfully."
        )

        print(
            "\nQXDM capture stopped successfully."
        )
        print(
            "The completed log was saved and loaded back into QXDM."
        )

        return True

    except Exception as error:
        logger.exception(
            "The automated QXDM stop procedure failed."
        )

        print(
            "\nThe QXDM capture could not be stopped automatically."
        )
        print(
            f"Reason: {error}"
        )

        print(
            "\nStop and save the capture manually in QXDM."
        )

        input(
            "Press Enter after manually stopping and saving the capture..."
        )

        return prompt_yes_no(
            "Was the QXDM capture stopped successfully?",
            default=True,
        )


def main() -> None:
    print("=" * 50)
    print("WNC TESTHUB - TITAN 3 TEST AUTOMATION")
    print("=" * 50)

    titan_ip = select_titan_ip()

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