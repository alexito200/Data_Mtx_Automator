"""
app.py — Register Form Filler (Streamlit)
==========================================
Loads a list of Register # values (Excel upload or pasted text) and types
each one into a browser form for you:

    Register # -> Enter -> "1" -> Enter -> Tab x7 -> "081926" -> Enter x2

>>> IMPORTANT: run this LOCALLY <<<
    streamlit run app.py
The app simulates keystrokes on the computer it runs on. That only reaches
your browser form if the app runs on YOUR machine. It will NOT work deployed
to Streamlit Community Cloud or any remote server (no desktop to type into).
"""

import time

import pandas as pd
import streamlit as st

import filler_core as core

st.set_page_config(page_title="Register Form Filler", layout="wide")
st.title("Register Form Filler")

# --------------------------------------------------------------------------- #
# How it works
# --------------------------------------------------------------------------- #
with st.expander("How this works — read me first", expanded=False):
    st.markdown(
        """
**Run locally.** Start it with `streamlit run app.py` on the same computer you
enter data on. It types keystrokes into your desktop, so it can't work on a
remote/cloud server.

**The flow for each record**
1. Load your data (upload the `.xlsx` or paste one Register # per line).
2. Click into the **Register #** field of the form in your browser.
3. Pick a record here and click **Fill** — you get a short countdown to
   switch back to the browser, then it enters: *Register # → Enter → "1" →
   Enter → Tab ×7 → "081926" → (optionally: Tab ×1 → one more value) →
   Enter ×2*.

**All of it is editable below** — field 2/3/4 values, every Tab count, the
final Enter count, and whether field 4 happens at all — in case the
destination form changes.

**Abort anytime:** slam your mouse into any screen corner to stop typing.
        """
    )

if not core.PYAUTOGUI_OK:
    st.error(
        "Keyboard control is unavailable here, so filling is disabled. "
        "Install requirements and run locally on a machine with a display "
        "(`pip install -r requirements.txt` then `streamlit run app.py`). "
        f"Details: {core.PYAUTOGUI_ERR}"
    )

# --------------------------------------------------------------------------- #
# 1) Load data
# --------------------------------------------------------------------------- #
st.subheader("1) Load your data")
method = st.radio(
    "Data source",
    ["Upload Excel (.xlsx)", "Paste data"],
    horizontal=True,
    help="Excel upload is recommended — it matches your existing files.",
)

records = None
label = None

if method.startswith("Upload"):
    up = st.file_uploader("Upload your Register # file", type=["xlsx", "xlsm"])
    if up is not None:
        try:
            label, records = core.parse_excel(up)
        except Exception as exc:
            st.error(f"Could not read that file: {exc}")
else:
    txt = st.text_area(
        "Paste Register # values — one per line",
        height=160,
        placeholder="9883840-2\n9892320-4\n9887672-5",
    )
    skip_first = st.checkbox("First pasted row is a header (skip it)", value=False)
    if txt.strip():
        rows = core.parse_pasted(txt)
        if skip_first and rows:
            rows = rows[1:]
        records = rows
        label = "Register #"

# Persist across reruns
if records:
    st.session_state["records"] = records
    st.session_state["label"] = label

records = st.session_state.get("records")
label = st.session_state.get("label") or "Register #"

if not records:
    st.info("Load a file or paste data to begin.")
    st.stop()

dedupe_on = st.checkbox(
    "Remove duplicate Register # values (keep the first occurrence)",
    value=True,
    help="Applies to whichever loading method you used above, before the "
    "preview and the fill list below.",
)
removed = 0
if dedupe_on:
    records, removed = core.dedupe(records)

st.dataframe(pd.DataFrame(records, columns=[label]), use_container_width=True, height=240)
if dedupe_on and removed:
    st.caption(
        f"{len(records)} unique register number(s) loaded "
        f"({removed} duplicate(s) removed)."
    )
else:
    st.caption(f"{len(records)} register number(s) loaded.")

# --------------------------------------------------------------------------- #
# 2) Fixed values & field navigation
# --------------------------------------------------------------------------- #
st.subheader("2) Fixed values & field navigation")
c1, c2 = st.columns(2)
second_value = c1.text_input(
    "Value typed after Register # (field 2)",
    "1",
    help="Typed the same for every record, then Enter is pressed.",
)
third_value = c2.text_input(
    "Value typed after the Tab-jump (field 3)",
    "081926",
    help="Typed the same for every record, then Enter is pressed (see the "
    "Enter-count field below).",
)

tab_count = st.number_input(
    "Tabs to reach field 3",
    1, 30, 7,
    help="How many times Tab is pressed after field 2 to reach field 3.",
)

fill_fourth_field = st.checkbox(
    "Also fill a field right after field 3",
    value=True,
    help="Inserts one more Tab-jump and one more fixed value between field "
    "3 and the Enter presses below. Turn off to leave the sequence exactly "
    "as it was (stop after field 3).",
)
if fill_fourth_field:
    c5, c6 = st.columns(2)
    tabs_after_third = c5.number_input(
        "Tabs to reach field 4",
        1, 30, 1,
        help="How many times Tab is pressed after field 3 to reach field 4.",
    )
    fourth_value = c6.text_input(
        "Value typed into field 4",
        "",
        help="Typed the same for every record, right before the Enter "
        "presses below run.",
    )
else:
    tabs_after_third, fourth_value = 1, ""

final_enters = st.number_input(
    "Enter presses after field 4" if fill_fourth_field else "Enter presses after field 3",
    1, 5, 2,
    help="Runs last, after whichever field is actually last in the "
    "sequence above (field 4 when that toggle is on, otherwise field 3). "
    "The destination form needs Enter pressed twice by default to finish "
    "the record.",
)

entry_mode_choice = st.radio(
    "How to enter the Register # itself",
    ["Paste (Ctrl/Cmd+V)", "Type it"],
    horizontal=True,
    help="Paste copies the value to the clipboard and pastes it — matches "
    "\"copy and paste\" in the described flow. Switch to Type if the form "
    "doesn't accept pasted input well.",
)
register_entry_mode = "paste" if entry_mode_choice.startswith("Paste") else "type"
if register_entry_mode == "paste" and not core.PYPERCLIP_OK:
    st.warning(
        "Paste mode needs the 'pyperclip' package, which isn't installed yet. "
        "Install it (pip install pyperclip) and restart, or switch to "
        "'Type it' for now."
    )

# --------------------------------------------------------------------------- #
# 3) Timing
# --------------------------------------------------------------------------- #
st.subheader("3) Timing")
t1, t2, t3 = st.columns(3)
secs = t1.number_input("Seconds to switch to your form", 1, 30, 5)
interval = t2.number_input(
    "Typing speed (sec/char)", 0.0, 0.5, 0.02, step=0.01,
    help="Delay between characters for typed fields (not used for a pasted "
    "Register #). Raise a little if a field's characters come out jumbled.",
)
field_delay = t3.number_input(
    "Delay between fields (sec)", 0.0, 1.0, 0.05, step=0.01,
    help="Pause after each field, Tab, and Enter so the form's scripts can "
    "keep up. If values are landing in the wrong place, raise this.",
)

with st.expander("Tab glitch fix (optional)"):
    st.caption(
        "If the destination form ever swallows a Tab during the 7-tab jump, "
        "field 3 lands in the wrong box. Two ways to guard against it:"
    )
    detect_text_field = st.checkbox(
        "Auto-detect lost focus and re-Tab (recommended, Windows)", value=False,
        help="After the Tab-jump, check what has keyboard focus. If the "
        "caret is NOT in a text field (it 'disappears' onto a button/label), "
        "send another Tab, up to the cap below.",
    )
    max_extra_tabs = st.number_input(
        "Max extra Tabs to try", 1, 5, 2,
        help="Safety cap so a misread can never run past the row.",
    )
    if detect_text_field and not core.UIA_OK:
        st.warning(
            "Focus detection needs the 'uiautomation' package, which isn't "
            "available yet. Install it (no admin needed): "
            "pip install uiautomation — then fully restart. Until then this "
            "toggle does nothing extra."
        )
    st.markdown("---")
    st.caption(
        "Simplest fallback: if the form always eats exactly one Tab, just "
        "raise \"Tabs to reach field 3\" above by one instead of relying on "
        "detection."
    )

# --------------------------------------------------------------------------- #
# 4) Fill
# --------------------------------------------------------------------------- #
st.subheader("4) Fill")

if "idx" not in st.session_state:
    st.session_state.idx = 0
st.session_state.idx = max(0, min(st.session_state.idx, len(records) - 1))
i = st.session_state.idx

nav1, nav2, nav3 = st.columns([1, 3, 1])
if nav1.button("Prev", use_container_width=True):
    st.session_state.idx = max(0, i - 1)
    st.rerun()
nav2.markdown(f"**Record {i + 1} of {len(records)}** — {records[i]}")
if nav3.button("Next", use_container_width=True):
    st.session_state.idx = min(len(records) - 1, i + 1)
    st.rerun()

disabled = not core.PYAUTOGUI_OK
fill_one = st.button("▶ Fill this record", type="primary", disabled=disabled)

st.markdown("---")
gap = st.number_input("Pause between records when filling several (sec)", 1, 60, 3)

start_at = st.number_input(
    "Start filling from record #",
    min_value=1,
    max_value=len(records),
    value=i + 1,
    step=1,
    help="Runs from this record through the last one in the list — useful "
    "for resuming a batch that stopped partway through, without re-filling "
    "records you already did.",
)
remaining = len(records) - int(start_at) + 1
fill_from_here = st.button(
    f"▶▶ Fill from record {int(start_at)} to the end ({remaining} record(s))",
    disabled=disabled,
)

fill_all = st.button(
    "▶▶▶ Fill ALL records from the beginning (test with one first!)",
    disabled=disabled,
)


def run_fill(indices):
    ph = st.empty()
    for s in range(int(secs), 0, -1):
        ph.warning(
            f"Switch to your form and click the Register # field… starting "
            f"in {s}s (slam the mouse into a screen corner to abort)"
        )
        time.sleep(1)
    try:
        for k, idx in enumerate(indices):
            ph.info(f"Typing record {idx + 1}: {records[idx]}…")
            core.type_record(
                records[idx],
                second_value=second_value,
                third_value=third_value,
                tab_count=int(tab_count),
                fill_fourth_field=fill_fourth_field,
                fourth_value=fourth_value,
                tabs_after_third=int(tabs_after_third),
                final_enters=int(final_enters),
                register_entry_mode=register_entry_mode,
                interval=float(interval),
                field_delay=float(field_delay),
                detect_text_field=detect_text_field,
                max_extra_tabs=int(max_extra_tabs),
            )
            if k < len(indices) - 1:
                ph.info(f"Record {idx + 1} done. Next in {int(gap)}s…")
                time.sleep(int(gap))
        ph.success(f"Done — {len(indices)} record(s) filled.")
    except Exception as exc:
        # Report exactly which record it was on, so a retry/resume knows
        # where to set "Start filling from record #".
        ph.error(f"Stopped at record {idx + 1} ({records[idx]}): {exc}")


if fill_one:
    run_fill([st.session_state.idx])
if fill_from_here:
    run_fill(list(range(int(start_at) - 1, len(records))))
if fill_all:
    run_fill(list(range(len(records))))
