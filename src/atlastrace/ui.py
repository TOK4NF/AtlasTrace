from __future__ import annotations

import json
import os
import shutil
import sys


RESET = "\033[0m"
BOLD = "\033[1m"
PURPLE = "\033[38;5;141m"
PURPLE_DARK = "\033[38;5;99m"
PURPLE_LIGHT = "\033[38;5;183m"

ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
_COLOR_READY = False
_COLOR_SUPPORTED: bool | None = None

BANNER_LINES = [
    r"    ___   __  __              ______                     ",
    r"   /   | / /_/ /___ ______   /_  __/________ _________  ",
    r"  / /| |/ __/ / __ `/ ___/    / / / ___/ __ `/ ___/ _ \ ",
    r" / ___ / /_/ / /_/ (__  )    / / / /  / /_/ / /__/  __/",
    r"/_/  |_\__/_/\__,_/____/    /_/ /_/   \__,_/\___/\___/ ",
]


def _try_enable_windows_vt() -> bool:
    try:
        import ctypes
    except Exception:
        return False

    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        if handle in (0, -1):
            return False
        mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
            return False
        if mode.value & ENABLE_VIRTUAL_TERMINAL_PROCESSING:
            return True
        return kernel32.SetConsoleMode(
            handle,
            mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING,
        ) != 0
    except Exception:
        return False


def supports_color() -> bool:
    global _COLOR_READY, _COLOR_SUPPORTED

    if os.getenv("NO_COLOR") is not None or os.getenv("ATLASTRACE_PLAIN") == "1":
        _COLOR_SUPPORTED = False
        return False

    if _COLOR_SUPPORTED is not None:
        return _COLOR_SUPPORTED

    if not sys.stdout.isatty():
        _COLOR_SUPPORTED = False
        return False

    if os.name == "nt" and not _COLOR_READY:
        _COLOR_READY = True
        _COLOR_SUPPORTED = _try_enable_windows_vt()
        return _COLOR_SUPPORTED

    _COLOR_SUPPORTED = True
    return _COLOR_SUPPORTED


def tint(text: str, color: str = PURPLE) -> str:
    if not supports_color():
        return text
    return f"{color}{text}{RESET}"


def clear_screen() -> None:
    if not sys.stdout.isatty():
        return
    os.system("cls" if os.name == "nt" else "clear")


def terminal_width(default: int = 110) -> int:
    try:
        return shutil.get_terminal_size((default, 30)).columns
    except OSError:
        return default


def hr(width: int, char: str = "═") -> str:
    return char * max(1, width)


def center_text(text: str, width: int) -> str:
    if len(text) >= width:
        return text[:width]
    return text.center(width)


def render_box(title: str, lines: list[str], *, width: int | None = None) -> str:
    box_width = width or min(110, terminal_width() - 2)
    inner = max(20, box_width - 2)
    top = f"+{hr(inner, '-')}+"
    heading = f"|{center_text(title, inner)}|"
    divider = f"+{hr(inner, '-')}+"
    body = []
    for line in lines:
        trimmed = line[:inner]
        body.append(f"|{trimmed.ljust(inner)}|")
    bottom = f"+{hr(inner, '-')}+"
    return "\n".join([top, heading, divider, *body, bottom])


def print_banner() -> None:
    width = min(110, terminal_width() - 2)
    body = BANNER_LINES + [
        "",
        "AtlasTrace :: Correlation, Breach Intelligence, Passive Enrichment",
        "lawful mode only | datasets + observables + identity + archive + HIBP-style checks",
    ]
    print(tint(render_box("ATLASTRACE", body, width=width), PURPLE_LIGHT))


def print_json(value: object) -> None:
    payload = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True)
    print(tint(payload, PURPLE))


def print_line(text: str, *, accent: str = PURPLE) -> None:
    print(tint(text, accent))


def print_error(text: str) -> None:
    print(tint(text, PURPLE_DARK), file=sys.stderr)


def print_section(title: str, lines: list[str], *, accent: str = PURPLE) -> None:
    width = min(110, terminal_width() - 2)
    print(tint(render_box(title, lines, width=width), accent))
