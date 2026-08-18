"""
Drives the Titan 3 "Verizon GUI" with a real, scriptable browser (Playwright)
to log in, navigate to Diagnostics & Monitoring > System Logging, and
download the syslog automatically instead of requiring a person to click
through it.

Menu path confirmed from real screenshots of the sidebar (2026-08-18):
Advanced tab > Diagnostics & Monitoring (collapsible section) >
System Logging > System Log tab (active by default) > Save button
(top right, next to Options/Refresh).

IMPORTANT - the login form and the exact Save button behavior are still
unconfirmed against the real device:
  - The login form is IP + password only (no username), per the team, but
    the submit button/behavior hasn't been verified.
  - Clicking Save is assumed to trigger a normal browser file download
    (that's what `_click_save_and_download` waits for) - not yet confirmed.

Everything here uses flexible, text/role-based Playwright locators so small
differences in markup don't break it, but treat this as still needing a
live test run. Each stage below raises a clearly labeled error naming
exactly which step failed, so a mismatch is easy to diagnose and fix in
one place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


ProgressCallback = Optional[Callable[[str, str], None]]

LOGIN_TIMEOUT_MS = 20_000
NAVIGATION_TIMEOUT_MS = 15_000
DOWNLOAD_TIMEOUT_MS = 30_000


@dataclass
class VerizonSyslogAutomationResult:
    saved_path: Path
    downloaded_filename: str


def _report(progress: ProgressCallback, step: str, message: str) -> None:
    if progress is not None:
        progress(step, message)


def automate_verizon_syslog_download(
    titan_ip: str,
    password: str,
    destination_folder: Path,
    headless: bool = False,
    progress: ProgressCallback = None,
) -> VerizonSyslogAutomationResult:
    """
    Log into the Titan 3 Verizon GUI and download the System Logging
    syslog directly into `destination_folder`.

    Runs headed (a visible browser window) by default so the engineer can
    watch it work and step in manually if a selector doesn't match the
    real page - this is a first pass against hardware we haven't seen yet.
    """
    try:
        from playwright.sync_api import (
            TimeoutError as PlaywrightTimeoutError,
            sync_playwright,
        )
    except ImportError as error:
        raise RuntimeError(
            "Playwright is not installed. Run 'pip install playwright "
            "&& playwright install chromium' in the backend virtual "
            "environment first."
        ) from error

    destination_folder = Path(destination_folder).expanduser().resolve()
    destination_folder.mkdir(parents=True, exist_ok=True)

    gui_url = f"https://{titan_ip}/#/login/"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)

        # The Titan 3 almost certainly serves a self-signed certificate on
        # its local management IP.
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            _report(
                progress,
                "launching",
                f"Opening the Verizon GUI at {gui_url}...",
            )

            try:
                page.goto(
                    gui_url,
                    timeout=NAVIGATION_TIMEOUT_MS,
                )
            except PlaywrightTimeoutError as error:
                raise RuntimeError(
                    f"Could not reach the Verizon GUI at {gui_url}. "
                    "Confirm the Titan IP is correct and the device is "
                    "reachable on the network."
                ) from error

            _report(
                progress,
                "logging_in",
                "Entering the Verizon GUI password...",
            )
            _login(page, password)

            _report(
                progress,
                "navigating",
                "Opening Diagnostics & Monitoring > System Logging...",
            )
            _click_diagnostic_monitoring(page)
            _click_system_logging(page)

            _report(
                progress,
                "saving",
                "Clicking Save and waiting for the syslog download...",
            )
            downloaded_path, downloaded_filename = _click_save_and_download(
                page,
                destination_folder,
            )

            _report(
                progress,
                "completed",
                f"Saved {downloaded_filename} to {destination_folder}.",
            )

            return VerizonSyslogAutomationResult(
                saved_path=downloaded_path,
                downloaded_filename=downloaded_filename,
            )

        finally:
            context.close()
            browser.close()


def _login(page, password: str) -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    try:
        password_field = page.locator('input[type="password"]').first
        password_field.wait_for(timeout=LOGIN_TIMEOUT_MS)
        password_field.fill(password)
    except PlaywrightTimeoutError as error:
        raise RuntimeError(
            "Could not find a password field on the Verizon GUI login "
            "page. The login form selector needs updating in "
            "backend/automation/verizon_syslog_automation.py (_login)."
        ) from error

    # Try a visible login/submit button first; fall back to pressing
    # Enter in the password field, which works for most login forms.
    submit_button = page.get_by_role(
        "button",
        name=re.compile(r"log ?in|sign ?in|submit", re.IGNORECASE),
    )

    try:
        if submit_button.count() > 0:
            submit_button.first.click()
        else:
            password_field.press("Enter")
    except PlaywrightTimeoutError as error:
        raise RuntimeError(
            "Found the password field but could not submit the login "
            "form. Update _login() with the real submit button."
        ) from error

    try:
        page.wait_for_url(
            re.compile(r"^(?!.*#/login/).*$"),
            timeout=LOGIN_TIMEOUT_MS,
        )
    except PlaywrightTimeoutError as error:
        raise RuntimeError(
            "Submitted the login form but the Verizon GUI never left the "
            "login page. Check whether the password was correct, or "
            "whether login uses a different flow than expected."
        ) from error


def _click_diagnostic_monitoring(page) -> None:
    # Confirmed from a real screenshot of the sidebar: the section is
    # labeled "Diagnostics & Monitoring" (plural "Diagnostics", with the
    # "&"), not "Diagnostic Monitoring". It's a collapsible section header
    # in the left sidebar - clicking it expands the submenu that contains
    # "System Logging".
    _click_menu_text(
        page,
        "Diagnostics & Monitoring",
        step_name="_click_diagnostic_monitoring",
    )


def _click_system_logging(page) -> None:
    _click_menu_text(
        page,
        "System Logging",
        step_name="_click_system_logging",
    )


def _click_menu_text(page, label: str, step_name: str) -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    locator = page.get_by_text(label, exact=False).first

    try:
        locator.wait_for(timeout=NAVIGATION_TIMEOUT_MS)
        locator.click()
    except PlaywrightTimeoutError as error:
        raise RuntimeError(
            f"Could not find or click '{label}' in the Verizon GUI. "
            f"Update {step_name}() in "
            "backend/automation/verizon_syslog_automation.py with the "
            "real menu selector once the actual page structure is known."
        ) from error


def _click_save_and_download(
    page,
    destination_folder: Path,
) -> tuple[Path, str]:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    save_button = page.get_by_role(
        "button",
        name=re.compile(r"save", re.IGNORECASE),
    ).first

    try:
        save_button.wait_for(timeout=NAVIGATION_TIMEOUT_MS)
    except PlaywrightTimeoutError as error:
        raise RuntimeError(
            "Could not find a Save button on the System Logging page. "
            "Update _click_save_and_download() with the real selector."
        ) from error

    try:
        with page.expect_download(
            timeout=DOWNLOAD_TIMEOUT_MS
        ) as download_info:
            save_button.click()

        download = download_info.value

    except PlaywrightTimeoutError as error:
        raise RuntimeError(
            "Clicked Save but no file download started within "
            f"{DOWNLOAD_TIMEOUT_MS // 1000} seconds. The Verizon GUI may "
            "require an extra confirmation step before it downloads."
        ) from error

    suggested_name = download.suggested_filename or "messages_SYS.log"
    saved_path = destination_folder / suggested_name

    counter = 1
    while saved_path.exists():
        stem = Path(suggested_name).stem
        suffix = Path(suggested_name).suffix
        saved_path = destination_folder / f"{stem}({counter}){suffix}"
        counter += 1

    download.save_as(str(saved_path))

    return saved_path, saved_path.name
