# Register Form Filler

A small local Streamlit app that types a list of **Register #** values into a
browser form for you. For each record it enters the Register #, presses
**Enter**, types **"1"**, presses **Enter**, presses **Tab seven times** to
reach the next field, types **"081926"**, and finishes with **Enter twice**.
The two typed values, the Tab count, and the final Enter count are all
adjustable from the app.

---

## ⚠️ Must run locally

This app simulates keystrokes on the computer it runs on. That only reaches
your browser form when the app runs on **your own machine**:

```bash
streamlit run app.py
```

It will **not** work deployed to Streamlit Community Cloud or any remote
server — there is no desktop there for it to type into.

---

## Setup

```bash
# from the project folder
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Platform notes for the keystroke part (pyautogui / pyperclip):
- **macOS** — grant Accessibility permission to your terminal / Python in
  System Settings → Privacy & Security → Accessibility.
- **Linux** — works under X11; Wayland may block synthetic key events.

---

## Using it

1. **Load data** — upload your `.xlsx` (a single **Register #** column,
   recommended) or paste one Register # per line.
2. **Open the form** in your browser and click into its **Register #**
   field.
3. Back in the app, pick a record and click **Fill**. You get a short
   countdown to switch to the browser, then it enters the record.
4. Use **Prev / Next** to step through records, **Fill ALL** to run the
   whole list from the top, or set **"Start filling from record #"** and
   click **Fill from record N to the end** to run a range instead — handy
   for resuming a batch that stopped partway through (test a single record
   first).

**If a batch run stops partway through** (error, mouse-corner abort, closed
laptop), the status message names the exact record it stopped on — e.g.
*"Stopped at record 214 (9842841-0): …"*. Set **"Start filling from record
#"** to that same number and click **Fill from record N to the end** to
pick back up without re-entering anything already done.

**Abort anytime:** slam the mouse into any screen corner.

---

## The flow, field by field

| Step | Action |
| --- | --- |
| 1 | Register # is entered into the focused field, then **Enter** |
| 2 | The fixed **field 2 value** ("1" by default) is typed, then **Enter** |
| 3 | **Tab** is pressed 7 times (adjustable) to reach field 3, then the fixed **field 3 value** ("081926" by default) is typed |
| 3b *(optional)* | **Tab** is pressed 1 more time (adjustable) to reach field 4, then the fixed **field 4 value** is typed |
| 4 | **Enter** is pressed twice (adjustable) |

Step 3b is controlled by **"Also fill a field right after field 3"** — on by
default. Turn it off to stop at field 3, exactly like before this option
existed. When it's on, field 4's Tab count and value are both editable, same
as field 3's.

**Enter always runs last**, whichever field ends up being the last one — the
"Enter presses" control sits below the field-4 settings for that reason, and
its label switches between *"after field 3"* and *"after field 4"* to match.
Same count, same setting, it just fires later when field 4 is turned on.

The app then moves to the next record and repeats.

**Register # entry mode:** by default the app copies the Register # to the
clipboard and pastes it (Ctrl+V, or Cmd+V on macOS) rather than typing it
character by character, matching "copy and paste" in the original
description. Switch to **"Type it"** in the app if your form doesn't behave
well with pasted input — that mode needs no extra setup, while paste mode
needs the `pyperclip` package (already listed in `requirements.txt`).

**Field 2's value, field 3's value, the Tab count, and the Enter count after
field 3 are all editable** under "2) Fixed values & field navigation" in case
the destination form changes.

---

## Data format

The Excel reader looks for a column whose header contains "register"
(case-insensitive) — matching a header like `Register #` — and reads every
non-empty value below it as one record. If no such header is found, it falls
back to the first column. Values are used exactly as stored (e.g.
`9883840-2`) — no reformatting, since the test file already stores them as
plain text with the hyphen included.

For pasted data, put one Register # per line. If a line has extra
Tab/comma-separated columns, only the first is used. Tick *"First pasted row
is a header"* if you include a header line.

**Duplicates:** right after loading (either method), *"Remove duplicate
Register # values"* is on by default — it keeps each value's first
occurrence and drops later repeats, and shows how many were removed. Untick
it to keep every row, including repeats.

---

## Tab glitch fix (optional)

If the destination form ever swallows a Tab during the 7-tab jump, field 3
lands in the wrong box. In the **"Tab glitch fix"** expander:

**1. Auto-detect lost focus (recommended, Windows only).** Turn on
*"Auto-detect lost focus and re-Tab."* After the Tab-jump it asks Windows what
has keyboard focus; if the caret is not in a text field, it sends another Tab
— up to *Max extra Tabs* (default 2) — until it is, or until focus can't be
read. Needs the `uiautomation` package:

```
pip install uiautomation
```

(no admin required; then fully restart). If focus can't be read for any
reason, it safely does nothing extra.

**2. Simplest fallback.** If the form always eats exactly one Tab, just raise
**"Tabs to reach field 3"** by one instead of relying on detection.

---

## Files

- `app.py` — the Streamlit interface.
- `filler_core.py` — data parsing + the keystroke engine (no UI).
- `requirements.txt` — dependencies.
