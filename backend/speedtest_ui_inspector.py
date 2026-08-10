from __future__ import annotations

import sys
from pathlib import Path

from pywinauto import Desktop


OUTPUT_FILE = Path(__file__).with_name(
    "speedtest_ui_controls.txt"
)


def find_speedtest_window():
    """
    Find the visible Speedtest desktop window using Windows UI Automation.
    """
    desktop = Desktop(
        backend="uia"
    )

    candidates = []

    for window in desktop.windows():
        try:
            title = (
                window.window_text()
                or ""
            ).strip()

            if "speedtest" in title.lower():
                candidates.append(
                    window
                )
        except Exception:
            continue

    if not candidates:
        raise RuntimeError(
            "No Speedtest window was found. "
            "Open Speedtest and leave the completed result screen visible."
        )

    # Prefer the first visible enabled Speedtest window.
    for window in candidates:
        try:
            if (
                window.is_visible()
                and window.is_enabled()
            ):
                return window
        except Exception:
            continue

    return candidates[0]


def collect_controls(
    window,
) -> list[str]:
    """
    Walk through the Speedtest UIA control tree and capture text,
    automation IDs, control types, and rectangles.

    This tells us whether download/upload/ping/server values are exposed
    as real Windows UI controls or only painted graphically.
    """
    lines: list[str] = []

    try:
        title = window.window_text()
    except Exception:
        title = "<unknown>"

    lines.append(
        f"WINDOW: {title}"
    )
    lines.append(
        "=" * 100
    )

    try:
        descendants = (
            window.descendants()
        )
    except Exception as error:
        raise RuntimeError(
            "Could not inspect Speedtest UI controls: "
            f"{error}"
        ) from error

    for index, control in enumerate(
        descendants,
        start=1,
    ):
        try:
            info = (
                control.element_info
            )

            name = (
                info.name
                or ""
            )
            control_type = (
                info.control_type
                or ""
            )
            automation_id = (
                info.automation_id
                or ""
            )
            class_name = (
                info.class_name
                or ""
            )

            try:
                rectangle = (
                    control.rectangle()
                )
                rect_text = (
                    f"({rectangle.left},"
                    f"{rectangle.top},"
                    f"{rectangle.right},"
                    f"{rectangle.bottom})"
                )
            except Exception:
                rect_text = ""

            line = (
                f"{index:04d} | "
                f"type={control_type!r} | "
                f"name={name!r} | "
                f"automation_id={automation_id!r} | "
                f"class={class_name!r} | "
                f"rect={rect_text}"
            )

            lines.append(
                line
            )

        except Exception as error:
            lines.append(
                f"{index:04d} | "
                f"<unable to inspect control: {error}>"
            )

    return lines


def print_interesting_lines(
    lines: list[str],
) -> None:
    """
    Print controls most likely related to throughput results.
    """
    keywords = (
        "download",
        "upload",
        "ping",
        "jitter",
        "loss",
        "server",
        "verizon",
        "bridgewater",
        "mbps",
        "ms",
    )

    interesting = [
        line
        for line in lines
        if any(
            keyword in line.lower()
            for keyword in keywords
        )
    ]

    print(
        "\nPotential result controls"
    )
    print(
        "=" * 100
    )

    if not interesting:
        print(
            "No obvious result controls were exposed by UI Automation."
        )
        return

    for line in interesting:
        print(
            line
        )


def main() -> int:
    print(
        "Looking for the Speedtest desktop window..."
    )

    try:
        window = find_speedtest_window()

        print(
            "Speedtest window found:"
        )
        print(
            window.window_text()
        )

        lines = collect_controls(
            window
        )

        OUTPUT_FILE.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

        print_interesting_lines(
            lines
        )

        print(
            "\nFull UI control tree saved to:"
        )
        print(
            OUTPUT_FILE.resolve()
        )

        print(
            "\nLeave Speedtest on the completed result screen "
            "when running this diagnostic."
        )

        return 0

    except Exception as error:
        print(
            f"\nERROR: {error}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )