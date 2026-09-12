# Windows Dependency Compatibility & Audioop Audit

## 1. Executive Summary

During initial Windows CI execution on `windows-latest` (Python 3.11), package resolution failed on `audioop-lts>=0.2.2`. This audit examines the origin, dependency chain, platform/Python availability, and correct resolution strategy for `audioop-lts`.

---

## 2. Dependency Chain Analysis

- **Direct Usage in HotChords Codebase:** None. Neither `backend/` nor `hotchords.py` imports `audioop` directly.
- **Transitive Requirement:** `lv-chordia` $\rightarrow$ `pydub` $\rightarrow$ `audioop`.
- **Python Standard Library Evolution:**
  - **Python 3.10, 3.11, 3.12:** The `audioop` C extension is built directly into the Python standard library. No external package is needed or exists on PyPI for these versions.
  - **Python 3.13+:** Python removed `audioop` from the standard library (PEP 594). `audioop-lts` was published on PyPI as an LTS port specifically with metadata `Requires-Python: >=3.13`.

---

## 3. Failure Root Cause on Windows Python 3.11

When `pip install -r requirements.txt` ran in a Python 3.11 environment:
1. `pip` parsed the bare dependency `audioop-lts>=0.2.2`.
2. PyPI returned no compatible distributions because `audioop-lts` wheels only exist for Python 3.13 and newer.
3. `pip` failed with `ERROR: Could not find a version that satisfies the requirement audioop-lts>=0.2.2`.
4. Downstream packages (`pydantic`, `numpy`, `librosa`) were never installed, leading to subsequent import and collection errors.

---

## 4. Technical Resolution

The correct standard solution is PEP 508 environment markers in `requirements.txt`:

```text
audioop-lts>=0.2.2; python_version >= "3.13"
```

### Impact:
- **Python 3.10, 3.11, 3.12 (Windows / macOS / Linux):** `audioop-lts` is ignored by `pip`. Python's native built-in `audioop` is utilized. All core libraries (`numpy`, `pydantic`, `librosa`, `torch`, `uvicorn`, `fastapi`) install cleanly.
- **Python 3.13+ (Local dev / macOS):** `audioop-lts` installs automatically to restore compatibility for `pydub`.

---

## 5. Console Encoding Audit (`preflight.py`)

- **Root Cause:** `preflight.py` used `\u2713` (Unicode checkmark) which raised `UnicodeEncodeError` under Windows console default code page `cp1252`.
- **Fix:** Replaced non-ASCII characters with universal ASCII status indicators: `[OK]`, `[FAIL]`, `[INFO]`.
- **Regression Test:** Added automated tests verifying ASCII-safe console output across all platforms.
