"""
filler_core.py
==============
Pure logic for the Register Form Filler:
  * reading the Register # list (Excel upload or pasted text)
  * the keystroke "typing" engine that drives the browser form

The Streamlit UI (app.py) imports from here. Keeping this separate makes the
parsing testable without a running Streamlit/desktop session — same split as
the original Projection Form Filler.
"""

from __future__ import annotations

import math
import sys
import time
from typing import List, Optional, Tuple

import pandas as pd

# --------------------------------------------------------------------------- #
# pyautogui is only needed when actually typing. Import it defensively so this
# module can be imported (and the parsers tested) on a headless machine.
# --------------------------------------------------------------------------- #
try:
    import pyautogui

    pyautogui.FAILSAFE = True  # slam mouse into a screen corner to abort
    PYAUTOGUI_OK = True
    PYAUTOGUI_ERR = ""
except Exception as exc:  # ImportError, or "no display" at import time
    pyautogui = None
    PYAUTOGUI_OK = False
    PYAUTOGUI_ERR = str(exc)

# --------------------------------------------------------------------------- #
# pyperclip powers "paste" entry for the Register # field (copy to clipboard,
# then Ctrl+V / Cmd+V) instead of typing it character by character. Imported
# defensively for the same reason as pyautogui above.
# --------------------------------------------------------------------------- #
try:
    import pyperclip

    PYPERCLIP_OK = True
    PYPERCLIP_ERR = ""
except Exception as exc:
    pyperclip = None
    PYPERCLIP_OK = False
    PYPERCLIP_ERR = str(exc)

# --------------------------------------------------------------------------- #
# uiautomation (Windows UI Automation) powers the optional "re-Tab until the
# cursor is back in a text field" glitch recovery — same mechanism as the
# original Projection Form Filler. Imported defensively so the rest of the
# app runs where it isn't installed (non-Windows, or not yet pip-installed).
# --------------------------------------------------------------------------- #
try:
    import uiautomation as _uia

    UIA_OK = True
    UIA_ERR = ""
except Exception as exc:
    _uia = None
    UIA_OK = False
    UIA_ERR = str(exc)

# macOS uses Cmd for clipboard/selection shortcuts; everywhere else it's Ctrl.
CTRL_OR_CMD = "command" if sys.platform == "darwin" else "ctrl"


# --------------------------------------------------------------------------- #
# Value formatting
# --------------------------------------------------------------------------- #
def fmt(v) -> str:
    """Turn any cell value into a clean string for typing.

    Notably: 137.0 -> "137" (in case a future file stores numbers as floats),
    NaN -> "". Register # values in the current data are already plain text
    (e.g. "9883840-2"), so this mostly guards against odd cell types.
    """
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        return str(int(v)) if v.is_integer() else ("%g" % v)
    # numpy scalars, if numpy is present
    try:
        import numpy as np

        if isinstance(v, np.integer):
            return str(int(v))
        if isinstance(v, np.floating):
            fv = float(v)
            return "" if math.isnan(fv) else (str(int(fv)) if fv.is_integer() else ("%g" % fv))
    except Exception:
        pass
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def _find_register_header(raw: pd.DataFrame, max_scan: int) -> Tuple[Optional[int], Optional[int]]:
    """Scan the first `max_scan` rows of a sheet for a cell containing
    "register" (case-insensitive) — matching a header like "Register #".
    Returns (header_row, col), or (None, None) if no such cell is found.
    """
    for idx in range(min(max_scan, len(raw))):
        cells = [str(x).strip().lower() for x in raw.iloc[idx].tolist()]
        for j, c in enumerate(cells):
            if "register" in c:
                return idx, j
    return None, None


def list_register_sheets(xls: pd.ExcelFile, max_scan: int = 15) -> List[Tuple[str, int, int]]:
    """Scan every sheet in the workbook for a "Register #"-style header and
    report how much data sits below it.

    Workbooks like this one often carry many sheets — pivot-table
    drill-throughs, one-off breakdowns, the actual master list — and more
    than one can have a column that happens to contain "register". Returns
    one (sheet_name, non_blank_count, unique_count) tuple per sheet that has
    such a column, sorted so the most "list-like" sheets come first (most
    *distinct* values first, then most non-blank values). A sheet that's the
    same value repeated (a drill-through for one record) sorts behind a
    sheet that's a clean list of different ones, even if the repeated sheet
    happens to have more rows.
    """
    results: List[Tuple[str, int, int]] = []
    for name in xls.sheet_names:
        raw = xls.parse(name, header=None)
        header_row, col = _find_register_header(raw, max_scan)
        if header_row is None:
            continue
        vals = [fmt(v) for v in raw.iloc[header_row + 1 :, col].tolist()]
        vals = [v for v in vals if v != ""]
        results.append((name, len(vals), len(set(vals))))
    results.sort(key=lambda t: (-t[2], -t[1]))
    return results


def parse_excel(xls: pd.ExcelFile, sheet_name, max_scan: int = 15) -> Tuple[str, List[str]]:
    """Read one sheet of a workbook into (column_label, register_numbers).

    `sheet_name` must be picked explicitly (e.g. from `list_register_sheets`)
    rather than defaulting to the first sheet — a workbook can have many
    sheets, and the first one isn't necessarily the right one.

    Finds the header row by locating a cell containing "register"
    (case-insensitive) within the first `max_scan` rows of that sheet — and
    reads that column. Falls back to treating row 0 as the header and column
    0 as the data if no such cell is found on the chosen sheet.
    """
    raw = xls.parse(sheet_name, header=None)

    header_row, col = _find_register_header(raw, max_scan)
    if header_row is None:
        header_row, col = 0, 0  # fall back: assume the first row/column is the header

    label = fmt(raw.iat[header_row, col]) or "Register #"

    records: List[str] = []
    for r in range(header_row + 1, len(raw)):
        val = fmt(raw.iat[r, col])
        if val != "":
            records.append(val)
    return label, records


def parse_pasted(text: str) -> List[str]:
    """Parse pasted text into a flat list of Register # values.

    One value per line. If a line has multiple Tab- or comma-separated
    columns (e.g. pasted straight from a wider sheet), only the first is
    used — the rest of the flow only needs the Register #.
    """
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    records: List[str] = []
    for ln in lines:
        if "\t" in ln:
            first = ln.split("\t", 1)[0]
        elif "," in ln:
            first = ln.split(",", 1)[0]
        else:
            first = ln
        val = fmt(first.strip())
        if val != "":
            records.append(val)
    return records


def dedupe(records: List[str]) -> Tuple[List[str], int]:
    """Remove duplicate Register # values, keeping each one's first
    occurrence and otherwise preserving the original order.

    Returns (deduped_records, number_removed).
    """
    seen = set()
    out: List[str] = []
    for r in records:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out, len(records) - len(out)


# --------------------------------------------------------------------------- #
# Focus detection (Windows UI Automation)
# --------------------------------------------------------------------------- #
def focus_is_text_field():
    """Best-effort check of what currently has keyboard focus.

    Returns:
        True  -> focus is on an editable text field
        False -> focus is on something that is NOT a text field
                 (button, label, blank area -> the caret "disappears")
        None  -> couldn't determine (UI Automation unavailable or query failed)

    Everything is wrapped in try/except: if the check ever fails we return None
    and the caller does nothing extra, so a detection hiccup can never crash a
    fill or send a stray Tab. Same mechanism as the original filler.
    """
    if not UIA_OK:
        return None
    try:
        try:
            import comtypes  # COM must be initialised on the calling thread

            comtypes.CoInitialize()
        except Exception:
            pass
        ctrl = _uia.GetFocusedControl()
    except Exception:
        return None

    if ctrl is None:
        return False
    try:
        ct = ctrl.ControlType
    except Exception:
        return None
    # Edit = ordinary <input>/<textarea>; Document = rich/contenteditable.
    if ct in (_uia.ControlType.EditControl, _uia.ControlType.DocumentControl):
        return True
    return False


# --------------------------------------------------------------------------- #
# Typing engine
# --------------------------------------------------------------------------- #
def type_record(
    register: str,
    *,
    second_value: str = "1",
    field8_value: str = "081926",
    tabs_to_field8: int = 7,
    fill_field9: bool = False,
    field9_value: str = "",
    tabs_after_field8: int = 0,
    final_enters: int = 2,
    register_entry_mode: str = "paste",  # "paste" or "type"
    interval: float = 0.0,
    field_delay: float = 0.0,
    detect_text_field: bool = False,
    max_extra_tabs: int = 2,
) -> None:
    """Type one record into whatever window currently has focus.

    Sequence (mirrors the destination form):
        1. Register #      -> Enter
        2. second_value     ("1" by default)      -> Enter
        3. Tab x tabs_to_field8 (7 by default) to reach field 8, then
           field8_value     ("081926" by default)
        3b. [optional, fill_field9] Tab x tabs_after_field8 (0 by default —
            the form highlights field 9 on its own, no Tab needed) to reach
            field 9, then Ctrl+A/Cmd+A to select whatever's already in it,
            then field9_value (typing over the selection replaces it)
        4. Enter x final_enters (2 by default) — fires after step 3b when
           fill_field9 is on, otherwise right after step 3

    register_entry_mode="paste" copies `register` to the clipboard and sends
    Ctrl+V (Cmd+V on macOS) instead of typing it character by character,
    matching "copy and paste" for that field specifically. second_value,
    field8_value, and field9_value are always typed with pyautogui, matching
    "type" in the described flow.

    fill_field9 toggles step 3b on/off. When off, the sequence is exactly
    steps 1-3 then final_enters — nothing about the existing flow changes.
    When on, field 9 is filled in right before those same Enter(s), which is
    why final_enters always runs last regardless of the toggle.
    tabs_after_field8 defaults to 0 because the destination form moves focus
    to field 9 by itself once field 8 is filled — set it above 0 only if
    that stops being true. Once there, a select-all (Ctrl+A / Cmd+A on
    macOS) runs before field9_value is typed, so it overwrites whatever's
    already in the field instead of getting inserted alongside it.

    field_delay pauses briefly after each typed/pasted value, after each
    Enter, and after each Tab. On forms that run JavaScript per field
    (validation, auto-advance), actions fired too fast can be dropped. A
    small delay (e.g. 0.05-0.1s) lets the form keep up.

    detect_text_field (Windows only, needs `uiautomation`) is the same
    glitch-recovery idea as the original filler: after a Tab-jump (step 3's,
    and — even at 0 Tabs — step 3b's, as a check that the auto-advance
    actually happened), check whether focus actually landed in a text field.
    If it didn't (some external forms swallow a Tab, or an auto-advance
    doesn't fire), send extra Tabs — up to `max_extra_tabs` — until it does,
    or until the check itself can't be read. Off by default; if a form
    always eats exactly the same number of Tabs, it's simpler to just raise
    `tabs_to_field8` / `tabs_after_field8` instead of turning this on.
    """
    if not PYAUTOGUI_OK:
        raise RuntimeError(
            "Keyboard control is unavailable (pyautogui could not start). "
            "This app must run locally on a machine with a display."
        )

    def settle():
        if field_delay:
            time.sleep(field_delay)  # let the form finish processing

    def enter_once():
        pyautogui.press("enter")
        settle()

    def select_all():
        pyautogui.hotkey(CTRL_OR_CMD, "a")
        settle()

    def tab_once():
        pyautogui.press("tab")
        settle()

    def tab_jump(n: int):
        """Press Tab `n` times, then (if enabled) recover from a swallowed
        Tab — or a missed auto-advance — by sending more until focus is
        back in a text field."""
        for _ in range(max(0, int(n))):
            tab_once()
        if not detect_text_field:
            return
        extra = 0
        while extra < max_extra_tabs:
            if focus_is_text_field() is False:
                tab_once()
                extra += 1
            else:
                break  # in a text field, or focus unknown -> stop

    def put_register(value: str):
        if value == "":
            return
        if register_entry_mode == "paste":
            if not PYPERCLIP_OK:
                raise RuntimeError(
                    "Paste mode needs the 'pyperclip' package "
                    "(pip install pyperclip), or switch to Type mode."
                )
            pyperclip.copy(value)
            pyautogui.hotkey(CTRL_OR_CMD, "v")
        else:
            pyautogui.write(value, interval=interval)
        settle()

    def put_typed(value: str):
        if value != "":
            pyautogui.write(value, interval=interval)
        settle()

    # Step 1: Register #
    put_register(register)
    enter_once()

    # Step 2: fixed second value
    put_typed(second_value)
    enter_once()

    # Step 3: Tab-jump to field 8, then its fixed value
    tab_jump(tabs_to_field8)
    put_typed(field8_value)

    # Step 3b (optional): field 9 — no Tab needed by default, the form
    # auto-highlights it once field 8 is filled; select-all first so the
    # typed value replaces whatever's already there
    if fill_field9:
        tab_jump(tabs_after_field8)
        select_all()
        put_typed(field9_value)

    # Step 4: Enter(s)
    for _ in range(max(1, int(final_enters))):
        enter_once()
