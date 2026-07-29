import ipaddress
import platform
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    Launch QXDM, load the DMC once, verify it, let the user configure
    log-saving settings, then send mode lpm and mode online before
    automated throughput testing.
    """

    should_start = prompt_yes_no(
        "Start the QXDM setup?",
        default=True,
    )

    if not should_start:
        logger.info("The user skipped the QXDM setup.")
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

        qxdm.launch()
        logger.info("QXDM launched or focused successfully.")

        input(
            "\nVerify that QXDM can see the connected device.\n"
            "Press Enter to load the DMC configuration..."
        )

        try:
            resolved_mask = qxdm.resolve_default_mask()

            if resolved_mask is None:
                qxdm.prompt_for_default_mask()

            qxdm.load_default_mask()

            logger.info(
                "The QXDM DMC load command was submitted."
            )

            print(
                "\nThe configured DMC file was submitted to QXDM."
            )

        except Exception as error:
            logger.warning(
                "Automatic QXDM DMC loading could not be confirmed: %s",
                error,
            )

            print(
                "\nAutomatic DMC loading could not be confirmed."
            )
            print(f"Reason: {error}")

        configuration_ready = prompt_yes_no(
            "Did the QXDM configuration load correctly?",
            default=True,
        )

        if not configuration_ready:
            print(
                "\nLoad the correct DMC configuration manually in QXDM."
            )

            input(
                "Press Enter after the configuration has been loaded..."
            )

            logger.warning(
                "The QXDM configuration required manual loading."
            )

        print("\n" + "=" * 50)
        print("QXDM LOG SETTINGS")
        print("=" * 50)

        try:
            qxdm.open_qxdm_settings()

            logger.info(
                "The QXDM Settings window was opened automatically."
            )

            print(
                "\nThe QXDM Settings window is open."
            )

        except Exception as error:
            logger.warning(
                "Could not open QXDM Settings automatically: %s",
                error,
            )

            print(
                "\nThe QXDM Settings window could not be opened "
                "automatically."
            )

            print(
                "Open Options > Settings manually."
            )

        print(
            "\nConfigure:"
            "\n  - Base File Name"
            "\n  - Log File Directory"
            "\n  - Maximum Log File Size"
            "\n  - Maximum Log File Duration"
            "\n  - Automatic file-saving options"
        )

        print(
            f"\nSuggested session log directory:\n"
            f"{qxdm_log_path.parent}"
        )

        input(
            "\nClick OK in QXDM after configuring the settings, "
            "then press Enter here..."
        )

        log_settings_ready = prompt_yes_no(
            "Are the QXDM log settings configured correctly?",
            default=True,
        )

        if not log_settings_ready:
            print(
                "\nReturn to Options > Settings and correct "
                "the QXDM log settings."
            )

            input(
                "Press Enter after the settings are ready..."
            )

        logger.info(
            "The user confirmed that the QXDM log settings are ready."
        )

        perform_airplane_mode = prompt_yes_no(
            "Perform Airplane Mode before throughput testing?",
            default=True,
        )

        if perform_airplane_mode:
            print(
                "\nPreparing the modem for throughput testing..."
            )

            qxdm.mode_lpm()
            logger.info("ModeLPM was sent successfully.")
            time.sleep(2)

            qxdm.mode_online()
            logger.info("ModeOnline was sent successfully.")
            time.sleep(2)

            print(
                "\nTitan 3 is back in online mode."
            )

        else:
            logger.info(
                "The user skipped Airplane Mode."
            )

            print(
                "\nSkipping Airplane Mode."
            )

        print(
            "Proceeding directly to automated throughput testing."
        )

        return False, qxdm_log_path

    except Exception as error:
        logger.exception(
            "The QXDM setup could not be completed."
        )

        print(
            "\nThe QXDM setup could not be completed."
        )
        print(f"Reason: {error}")

        continue_test = prompt_yes_no(
            "Continue the Titan 3 test without QXDM setup?",
            default=True,
        )

        if not continue_test:
            raise RuntimeError(
                "Test cancelled because the QXDM setup "
                "could not be completed."
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

    print(
        "\nAutomated test configuration:"
    )

    print(
        f"  Runs: {number_of_runs}"
    )

    print(
        f"  Delay: {delay_between_runs} seconds"
    )

    print(
        f"  Speedtest timeout: {speedtest_timeout} seconds"
    )

    print(
        f"  Speedtest executable: {speedtest_executable}"
    )

    print(
        f"  Excel output: {excel_path}"
    )

    input(
        "\nMake sure the official Ookla Speedtest CLI is installed.\n"
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
            "Continue the session and generate the remaining reports?",
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



def get_local_ipv4_address() -> str | None:
    """
    Return the IPv4 address used by the active network interface.

    No data is sent. The UDP socket is only used so Windows selects
    the interface it would use for an outbound connection.
    """
    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )

    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]

    except OSError:
        return None

    finally:
        sock.close()


def ping_ip_address(
    ip_address: str,
    timeout_ms: int = 250,
) -> bool:
    """Return True when the address responds to one ping."""
    if platform.system().lower() == "windows":
        command = [
            "ping",
            "-n",
            "1",
            "-w",
            str(timeout_ms),
            ip_address,
        ]

        creation_flags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )

    else:
        timeout_seconds = max(
            1,
            round(timeout_ms / 1000),
        )

        command = [
            "ping",
            "-c",
            "1",
            "-W",
            str(timeout_seconds),
            ip_address,
        ]

        creation_flags = 0

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=max(2, timeout_ms / 1000 + 1),
            creationflags=creation_flags,
            check=False,
        )

        return result.returncode == 0

    except (
        OSError,
        subprocess.TimeoutExpired,
    ):
        return False


def has_titan_web_port(
    ip_address: str,
    timeout_seconds: float = 0.25,
) -> bool:
    """
    Check for a web interface commonly used by the Titan dashboard.

    This does not prove that the host is a Titan 3, so the user is
    still asked to confirm the selected address.
    """
    for port in (80, 443):
        try:
            with socket.create_connection(
                (ip_address, port),
                timeout=timeout_seconds,
            ):
                return True

        except OSError:
            continue

    return False


def check_titan_candidate(
    ip_address: str,
) -> tuple[str, bool, bool]:
    """Check whether an address responds to ping or exposes a web port."""
    web_port_open = has_titan_web_port(ip_address)
    ping_replied = ping_ip_address(ip_address)

    return ip_address, ping_replied, web_port_open


def build_discovery_networks(
    default_ip: str,
) -> list[ipaddress.IPv4Network]:
    """
    Build a short list of /24 networks that may contain the Titan 3.

    The Titan USB network 192.168.100.0/24 is always checked. The
    current PC network and the configured default IP network are also
    included when available.
    """
    networks: list[ipaddress.IPv4Network] = []

    def add_network(ip_value: str | None) -> None:
        if not ip_value:
            return

        try:
            network = ipaddress.ip_network(
                f"{ip_value}/24",
                strict=False,
            )

        except ValueError:
            return

        if network not in networks:
            networks.append(network)

    add_network("192.168.100.1")
    add_network(default_ip)
    add_network(get_local_ipv4_address())

    return networks


def discover_titan_candidates(
    default_ip: str,
) -> list[str]:
    """
    Search likely local /24 networks for reachable Titan candidates.

    Addresses with a web interface are placed first because the Titan
    dashboard normally uses HTTP or HTTPS.
    """
    networks = build_discovery_networks(default_ip)

    addresses: list[str] = []

    for network in networks:
        for host in network.hosts():
            host_text = str(host)

            if host_text not in addresses:
                addresses.append(host_text)

    # Test the known/default addresses first so the common case is fast.
    priority_addresses = [
        "192.168.100.1",
        default_ip,
    ]

    ordered_addresses: list[str] = []

    for address in priority_addresses + addresses:
        if address and address not in ordered_addresses:
            ordered_addresses.append(address)

    candidates: list[tuple[str, bool, bool]] = []

    with ThreadPoolExecutor(max_workers=48) as executor:
        futures = {
            executor.submit(
                check_titan_candidate,
                address,
            ): address
            for address in ordered_addresses
        }

        for future in as_completed(futures):
            try:
                ip_address, ping_replied, web_port_open = (
                    future.result()
                )

            except Exception:
                continue

            if ping_replied or web_port_open:
                candidates.append(
                    (
                        ip_address,
                        ping_replied,
                        web_port_open,
                    )
                )

    def sort_key(
        item: tuple[str, bool, bool],
    ) -> tuple[int, int, int]:
        ip_address, ping_replied, web_port_open = item

        preferred = (
            0
            if ip_address in {
                "192.168.100.1",
                default_ip,
            }
            else 1
        )

        return (
            0 if web_port_open else 1,
            preferred,
            int(ipaddress.ip_address(ip_address)),
        )

    candidates.sort(key=sort_key)

    return [
        ip_address
        for ip_address, _, _ in candidates
    ]


def select_titan_ip_address(
    default_ip: str,
) -> str:
    """
    Automatically look for the Titan 3 and allow manual fallback.

    Because another device may also answer on the network, the user
    confirms the detected address before the test proceeds.
    """
    print("\nSearching for the Titan 3 IP address...")

    candidates = discover_titan_candidates(
        default_ip
    )

    if not candidates:
        print(
            "\nNo reachable Titan 3 candidate was found automatically."
        )

        return prompt_with_default(
            "Enter Titan 3 IP address",
            default_ip,
        )

    print("\nReachable device candidates:")

    for index, ip_address in enumerate(
        candidates,
        start=1,
    ):
        marker = (
            " (usual Titan 3 address)"
            if ip_address == "192.168.100.1"
            else ""
        )

        print(
            f"  [{index}] {ip_address}{marker}"
        )

    print(
        "  [M] Enter an IP address manually"
    )

    while True:
        choice = input(
            "\nSelect the Titan 3 address "
            f"[default: 1]: "
        ).strip()

        if not choice:
            selected_ip = candidates[0]

        elif choice.lower() == "m":
            return prompt_with_default(
                "Enter Titan 3 IP address",
                default_ip,
            )

        else:
            try:
                selected_index = int(choice) - 1
                selected_ip = candidates[selected_index]

            except (
                ValueError,
                IndexError,
            ):
                print(
                    "Choose one of the displayed numbers or enter M."
                )
                continue

        confirmed = prompt_yes_no(
            f"Use {selected_ip} for the Titan 3?",
            default=True,
        )

        if confirmed:
            return selected_ip


def main() -> None:
    print("=" * 50)
    print("WNC TESTHUB - TITAN 3 TEST AUTOMATION")
    print("=" * 50)

    titan_ip = select_titan_ip_address(
        DEFAULT_TITAN_IP,
    )

    print(
        f"\nUsing Titan 3 IP address: {titan_ip}"
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