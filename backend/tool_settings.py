from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class ToolSettings:
    """
    Store machine-specific tool paths outside the Git repository.

    Default settings file:
        C:\\Users\\<user>\\.wnc_testhub\\tool_settings.json
    """

    def __init__(
        self,
        settings_path: Optional[Path] = None,
    ) -> None:
        self.settings_path = (
            Path(settings_path).expanduser().resolve()
            if settings_path is not None
            else (
                Path.home()
                / ".wnc_testhub"
                / "tool_settings.json"
            ).resolve()
        )

    def load(self) -> dict[str, str]:
        if not self.settings_path.exists():
            return {}

        try:
            data = json.loads(
                self.settings_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
        ):
            return {}

        if not isinstance(data, dict):
            return {}

        return {
            str(key): str(value)
            for key, value in data.items()
            if value is not None
        }

    def save(
        self,
        settings: dict[str, str],
    ) -> None:
        self.settings_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.settings_path.write_text(
            json.dumps(
                settings,
                indent=2,
            ),
            encoding="utf-8",
        )

    def get_path(
        self,
        key: str,
    ) -> Optional[Path]:
        value = self.load().get(key)

        if not value:
            return None

        return Path(value).expanduser()

    def get_valid_path(
        self,
        key: str,
    ) -> Optional[Path]:
        path = self.get_path(key)

        if path is None:
            return None

        try:
            resolved = path.resolve()
        except OSError:
            return None

        if not resolved.exists() or not resolved.is_file():
            return None

        return resolved

    def set_path(
        self,
        key: str,
        path: Path,
    ) -> Path:
        resolved = (
            Path(path)
            .expanduser()
            .resolve()
        )

        if not resolved.exists():
            raise FileNotFoundError(
                f"Tool path was not found:\n{resolved}"
            )

        if not resolved.is_file():
            raise ValueError(
                f"Tool path is not a file:\n{resolved}"
            )

        settings = self.load()
        settings[key] = str(resolved)

        self.save(settings)

        return resolved

    def remove(
        self,
        key: str,
    ) -> None:
        settings = self.load()

        if key in settings:
            settings.pop(key)
            self.save(settings)