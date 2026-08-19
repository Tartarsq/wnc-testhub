"""
Reads live cellular radio metrics (RSRP, technology, firmware version,
etc.) from the Titan 3 Verizon GUI's Home page data endpoint.

Confirmed from a real captured request (2026-08-19): after logging in,
GET https://<titan-ip>/cgi/cgi_home.js (with the `sysauth` cookie) returns
a JavaScript-ish text body full of `addCfg("key", "<encrypted-blob>",
"<plain-value>")` and `addROD("key", value)` calls used to populate the
GUI's own form fields. The interesting ones for radio metrics:

    addCfg("rpsp_5g", "...", "-123");   -> RSRP while on 5G, dBm ("-" if none)
    addCfg("rpsp_4g", "...", "-");      -> RSRP while on 4G, dBm ("-" if none)
    addCfg("signal_type", "...", "5G network signal");
    addCfg("signal_level", "...", "1"); -> signal bars, not dBm

Plus a nested topology JSON blob (inside addROD("dump_toplogy_map_info",
{...})) that separately carries "fw_ver" (firmware) and "connect_type"
(e.g. "EN-DC" for 5G NSA dual-connectivity) - both grabbed with a plain
regex rather than fully parsing that JSON, since the rest of it is WiFi
mesh/topology data unrelated to cellular radio state.

RSSI, SINR, and Serving Band were not found on this page as of the last
check - they stay None here until a source for them is confirmed.

Login reuses the same Playwright-for-login-only approach as the syslog
download (see verizon_syslog_automation.py) - only the login step needs a
real browser, so the page's own JavaScript hashes the password correctly.
The actual data fetch is a plain `requests` GET using the resulting
session cookie, so a cached cookie can be reused across repeated polls
without relaunching a browser every time.
"""

from __future__ import annotations

import re
from typing import Any

import requests

from automation.verizon_syslog_automation import (
    SYSLOG_COOKIE_NAME,
    login_and_get_sysauth_cookie,
)



# The cellular signal fields (rpsp_5g/rpsp_4g/signal_type) live on
# cgi_home.js, but Mode (connect_type) and firmware version (fw_ver) turn
# out to live in the separate topology dump on cgi_basic.js instead - both
# get fetched and their response text combined before parsing.
RADIO_METRICS_PATHS = (
    "/cgi/cgi_home.js",
    "/cgi/cgi_basic.js",
)
REQUEST_TIMEOUT_SECONDS = 15

_ADD_CFG_PATTERN = re.compile(
    r'addCfg\(\s*"([^"]+)"\s*,\s*"[^"]*"\s*,\s*[\'"]([^\'"]*)[\'"]\s*\)'
)
_ADD_ROD_PATTERN = re.compile(
    r'addROD\(\s*"([^"]+)"\s*,\s*[\'"]([^\'"]*)[\'"]\s*\)'
)
_CONNECT_TYPE_PATTERN = re.compile(r'"connect_type"\s*:\s*"([^"]+)"')
_FW_VERSION_PATTERN = re.compile(r'"fw_ver"\s*:\s*"([^"]+)"')

# Human-readable labels for the Verizon GUI's short connection-type codes.
_MODE_LABELS = {
    "EN-DC": "5G NSA (EN-DC)",
    "SA": "5G SA",
    "LTE": "4G LTE",
}

EMPTY_RADIO_METRICS: dict[str, Any] = {
    "firmware_version": None,
    "carrier": None,
    "technology": None,
    "mode": None,
    "serving_band": None,
    "rsrp_dbm": None,
    "rssi_dbm": None,
    "sinr_db": None,
}


def fetch_radio_metrics(
    titan_ip: str,
    password: str,
) -> tuple[dict[str, Any], str]:
    """
    Log into the Titan 3 Verizon GUI and read live radio metrics.

    Returns (metrics, sysauth) so the caller can cache the session cookie
    and reuse fetch_radio_metrics_with_cookie() for subsequent polls
    instead of logging in again every time.
    """
    sysauth = login_and_get_sysauth_cookie(titan_ip, password)
    metrics = fetch_radio_metrics_with_cookie(titan_ip, sysauth)
    return metrics, sysauth


def _fetch_page_text(
    titan_ip: str,
    sysauth: str,
    path: str,
) -> str:
    url = f"https://{titan_ip}{path}"

    try:
        response = requests.get(
            url,
            cookies={SYSLOG_COOKIE_NAME: sysauth},
            headers={"Referer": f"https://{titan_ip}/"},
            timeout=REQUEST_TIMEOUT_SECONDS,
            verify=False,
        )
    except requests.RequestException as error:
        raise RuntimeError(
            f"Failed to reach {url} for radio metrics: {error}"
        ) from error

    if response.status_code in (401, 403):
        raise PermissionError(
            "The Verizon GUI session has expired. Connect again with "
            "the password."
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Reading radio metrics from {url} returned HTTP "
            f"{response.status_code}."
        )

    return response.text


def fetch_radio_metrics_with_cookie(
    titan_ip: str,
    sysauth: str,
) -> dict[str, Any]:
    """
    Read radio metrics using an already-authenticated sysauth cookie.

    Raises PermissionError if the session has expired (the caller should
    drop the cached cookie and prompt for the password again), or
    RuntimeError for any other request failure.
    """
    combined_text = "\n".join(
        _fetch_page_text(titan_ip, sysauth, path)
        for path in RADIO_METRICS_PATHS
    )

    return parse_radio_metrics(combined_text)


def _clean_dbm(raw: str | None) -> float | None:
    if not raw or raw.strip() in ("-", ""):
        return None

    try:
        return float(raw)
    except ValueError:
        return None


def parse_radio_metrics(page_text: str) -> dict[str, Any]:
    """
    Pull the radio-metric fields out of the cgi_home.js response text.
    """
    fields: dict[str, str] = {}

    for key, value in _ADD_CFG_PATTERN.findall(page_text):
        fields[key] = value

    for key, value in _ADD_ROD_PATTERN.findall(page_text):
        fields.setdefault(key, value)

    signal_type = fields.get("signal_type")
    rsrp_5g_value = _clean_dbm(fields.get("rpsp_5g"))
    rsrp_4g_value = _clean_dbm(fields.get("rpsp_4g"))

    technology = (
        signal_type.split(" ")[0].strip()
        if signal_type
        else None
    ) or None

    rsrp_dbm: float | None = None

    if rsrp_5g_value is not None:
        rsrp_dbm = rsrp_5g_value
        technology = technology or "5G"
    elif rsrp_4g_value is not None:
        rsrp_dbm = rsrp_4g_value
        technology = technology or "4G"

    connect_type_match = _CONNECT_TYPE_PATTERN.search(page_text)
    mode = (
        _MODE_LABELS.get(
            connect_type_match.group(1),
            connect_type_match.group(1),
        )
        if connect_type_match
        else None
    )

    firmware_match = _FW_VERSION_PATTERN.search(page_text)
    firmware_version = (
        firmware_match.group(1) if firmware_match else None
    )

    return {
        **EMPTY_RADIO_METRICS,
        "firmware_version": firmware_version,
        "technology": technology,
        "mode": mode,
        "rsrp_dbm": rsrp_dbm,
    }
