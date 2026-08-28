"""
Logs into the Titan 3 "Verizon GUI" and downloads the System Logging
syslog automatically, instead of requiring a person to click through it.

Confirmed from real captured network requests (2026-08-18): the GUI is
built on LuCI (OpenWrt's web UI) under a custom skin - the login form
posts to /login.cgi with fields luci_username, luci_password, luci_token,
luci_view, and luci_keep_login, and success is marked by a `sysauth`
session cookie. The syslog itself is served as a plain file at
/log/messages_SYS.log once that cookie is present.

IMPORTANT: luci_username/luci_password in the captured request are
128-character hex strings (SHA-512 digests), not plaintext, and
luci_token looks like a one-time nonce issued per page load. That means
the login form's own JavaScript is hashing the credentials together with
a fresh token before submitting - replicating that exact algorithm with
plain HTTP requests would be guesswork and easy to get subtly wrong.

So this only uses Playwright for the login step, where the real page's
own JavaScript does the hashing correctly - then it reads the resulting
`sysauth` cookie straight out of the browser and closes it, and fetches
the syslog with one plain `requests` GET using that cookie. This avoids
depending on any UI structure (menus, tabs, buttons) beyond the login
form itself, which is what kept breaking as the click-through path was
built out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests


ProgressCallback = Optional[Callable[[str, str], None]]

LOGIN_TIMEOUT_MS = 20_000
NAVIGATION_TIMEOUT_MS = 15_000
DOWNLOAD_TIMEOUT_SECONDS = 30

SYSLOG_COOKIE_NAME = "sysauth"
SYSLOG_PATH = "/log/messages_SYS.log"


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

    Runs headed (a visible browser window) by default for the login step,
    so the engineer can watch it work and step in manually if the login
    form ever changes.
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

        # The Titan 3 serves a self-signed certificate on its local
        # management IP.
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

            sysauth = _get_sysauth_cookie(context, titan_ip)

        finally:
            context.close()
            browser.close()

    _report(
        progress,
        "downloading",
        f"Downloading {SYSLOG_PATH} with the authenticated session...",
    )
    saved_path, downloaded_filename = _download_syslog(
        titan_ip=titan_ip,
        sysauth=sysauth,
        destination_folder=destination_folder,
    )

    _report(
        progress,
        "completed",
        f"Saved {downloaded_filename} to {destination_folder}.",
    )

    return VerizonSyslogAutomationResult(
        saved_path=saved_path,
        downloaded_filename=downloaded_filename,
    )


def login_and_get_sysauth_cookie(
    titan_ip: str,
    password: str,
    headless: bool = True,
) -> str:
    """
    Log into the Titan 3 Verizon GUI with a real browser (so the page's
    own JavaScript hashes the password correctly, same reasoning as
    automate_verizon_syslog_download above) and return the resulting
    `sysauth` session cookie value.

    Shared by anything that needs an authenticated session against the
    Verizon GUI without also wanting the syslog-specific download step -
    e.g. reading the live radio metrics page.
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

    gui_url = f"https://{titan_ip}/#/login/"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
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

            _login(page, password)

            return _get_sysauth_cookie(context, titan_ip)

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


def _get_sysauth_cookie(context, titan_ip: str) -> str:
    for cookie in context.cookies():
        if cookie.get("name") == SYSLOG_COOKIE_NAME:
            return cookie["value"]

    raise RuntimeError(
        f"Logged in, but no '{SYSLOG_COOKIE_NAME}' session cookie was "
        f"found for {titan_ip}. The Verizon GUI may use a different "
        "cookie name now - check DevTools > Application > Cookies after "
        "logging in manually and update SYSLOG_COOKIE_NAME."
    )


def _download_syslog(
    titan_ip: str,
    sysauth: str,
    destination_folder: Path,
) -> tuple[Path, str]:
    url = f"https://{titan_ip}{SYSLOG_PATH}"

    try:
        response = requests.get(
            url,
            cookies={SYSLOG_COOKIE_NAME: sysauth},
            headers={"Referer": f"https://{titan_ip}/"},
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
            verify=False,
        )
    except requests.RequestException as error:
        raise RuntimeError(
            f"Failed to reach {url} for the syslog download: {error}"
        ) from error

    if response.status_code != 200:
        raise RuntimeError(
            f"Downloading the syslog from {url} returned HTTP "
            f"{response.status_code} instead of 200. The session cookie "
            "may have expired, or the log path may have changed."
        )

    suggested_name = Path(SYSLOG_PATH).name
    saved_path = destination_folder / suggested_name

    counter = 1
    while saved_path.exists():
        stem = Path(suggested_name).stem
        suffix = Path(suggested_name).suffix
        saved_path = destination_folder / f"{stem}({counter}){suffix}"
        counter += 1

    saved_path.write_bytes(response.content)

    return saved_path, saved_path.name
