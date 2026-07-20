import platform
import subprocess
import webbrowser
from dataclasses import dataclass

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

        return f"{self.protocol}://{self.ip_address}:{self.port}"

    def ping(self) -> bool:
        """Return True when the Titan responds to a ping."""
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