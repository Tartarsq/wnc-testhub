import platform
import subprocess
import webbrowser
from dataclasses import dataclass
from typing import Any

import requests

from config import (
    DEFAULT_TITAN_PORT,
    DEFAULT_TITAN_PROTOCOL,
    PING_TIMEOUT_SECONDS,
)


@dataclass
class Titan3:
    ip_address: str
    protocol: str = DEFAULT_TITAN_PROTOCOL
    port: int = DEFAULT_TITAN_PORT
    request_timeout_seconds: int = 10

    @property
    def gui_url(self) -> str:
        """Return the Titan 3 Web GUI URL."""
        standard_port = (
            self.protocol == "http" and self.port == 80
        ) or (
            self.protocol == "https" and self.port == 443
        )

        if standard_port:
            return f"{self.protocol}://{self.ip_address}"

        return (
            f"{self.protocol}://"
            f"{self.ip_address}:{self.port}"
        )

    def ping(self) -> bool:
        """Return True when Titan responds to a ping."""
        operating_system = platform.system().lower()

        if operating_system == "windows":
            command = [
                "ping",
                "-n",
                "1",
                "-w",
                str(PING_TIMEOUT_SECONDS * 1000),
                self.ip_address,
            ]
        else:
            command = [
                "ping",
                "-c",
                "1",
                "-W",
                str(PING_TIMEOUT_SECONDS),
                self.ip_address,
            ]

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

            return result.returncode == 0

        except OSError:
            return False

    def open_gui(self) -> bool:
        """Open the Titan Web GUI in the default browser."""
        return webbrowser.open(self.gui_url)

    def request_json(
        self,
        endpoint: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send an HTTP request to Titan and return JSON data.

        The endpoint should begin with a slash, for example:
        /api/status
        """
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        url = f"{self.gui_url}{endpoint}"

        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                json=payload,
                timeout=self.request_timeout_seconds,
                verify=False,
            )

            response.raise_for_status()

        except requests.RequestException as error:
            raise RuntimeError(
                f"Titan API request failed for {url}: {error}"
            ) from error

        try:
            return response.json()

        except ValueError as error:
            raise RuntimeError(
                f"Titan returned non-JSON data from {url}."
            ) from error

    def get_radio_metrics(self) -> dict[str, Any]:
        """
        Retrieve Titan RF and device metrics.

        Replace '/api/status' and the field names below with
        Titan's real endpoint and JSON structure.
        """
        data = self.request_json("/api/status")

        return {
            "firmware_version": data.get("firmware_version"),
            "carrier": data.get("carrier"),
            "technology": data.get("technology"),
            "mode": data.get("mode"),
            "serving_band": data.get("serving_band"),
            "rsrp_dbm": data.get("rsrp"),
            "rssi_dbm": data.get("rssi"),
            "sinr_db": data.get("sinr"),
        }