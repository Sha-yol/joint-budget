# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Preview what would be synced (no changes made)
uv run python sync_expenses.py config.yaml --dry-run

# Actually upload to Google Sheets
uv run python sync_expenses.py config.yaml

# Using test config (example_input files)
uv run python sync_expenses.py config_test.yaml --dry-run
```

No test suite exists yet. Run the tool with `--dry-run` to validate parsing logic against real input files. `config_test.yaml` points at `example_input/` for exactly this purpose. That folder is gitignored (it holds real financial exports), so populate it locally before running the test config.

Note: `main.py` is an unused placeholder left over from `uv init`. The real entry point is `sync_expenses.py`.

## Architecture

The tool reads expense exports and appends new rows to a Google Sheet, using a deterministic UUID (`_id`) for idempotent upsert — re-running never duplicates or overwrites existing rows.

**Data flow:** config.yaml → `sync_expenses.py` → parsers → `sheets.py` → Google Sheets

### Input sources

Two input modes, configured in `config.yaml`:
- **`input_dir`** — auto-discovers and classifies all files in a directory (preferred)
- **Explicit lists** (`mizrahi_ccs_files`, `splitwise_regular_files`, `splitwise_group_files`) — for manual file specification

### Parsers (`parsers/`)

- `mizrahi_ccs.py` — Mizrahi bank "all credit cards" xlsx export. Has 3 currency tabs (`חיובים בשקלים` / `בדולרים` / `באירו`); only the NIS sheet is read (the foreign-currency sheets are typically empty). Inside the NIS sheet, multiple card blocks are stacked vertically — each begins with a header `חשבון כרטיס: ... ארבע ספרות אחרונות NNNN`, then a transaction table. The parser walks all blocks, emitting rows whose `מקור` is the per-block last-4. Zero-amount rows (e.g. a waived `דמי כרטיס`) are skipped. Date format is `dd/mm/yyyy`.
- `splitwise.py` — Two variants:
  - **Regular** (1:1): uses total `Cost` column as the joint expense
  - **Group** (3+ people): computes combined share for configured `person_names` using sign convention (negative = owes, positive = paid and is owed → share = `Cost - value`, zero = not involved). `Category == "Payment"` rows (settlements) are filtered out.
- `common.py` — Shared: `make_expense()` builds normalized dicts; `make_expense_id()` generates a UUID5 from `date|source|description|amount:.2f` via `NAMESPACE_URL`. Also holds Splitwise CSV helpers (header detection, cost/date parsing, payment filter).
- `discover.py` — File classification for `input_dir` mode:
  - `.xlsx` → Mizrahi CCs if the sheet `חיובים בשקלים` exists and contains `חשבון כרטיס` in its first 3 rows.
  - `.csv` → Splitwise based on header `["Date","Description","Category","Cost","Currency",…]` and the count of non-empty person columns after `Currency` (≤2 → regular, 3+ → group).

### Normalized expense dict

All parsers produce dicts with these keys (Hebrew field names match sheet columns):
```python
{"_id": str, "תאריך": "YYYY-MM-DD", "מקור": str, "תיאור": str, "סכום": float}
```

### Google Sheets (`sheets.py`)

Sheet columns: `_id, תאריך, מקור, תיאור, סכום, קטגוריית תקציב, הערות`

The last two columns (`קטגוריית תקציב`, `הערות`) are manually filled by the user and are never touched by the sync.

### Credentials & config files

- `credentials.json` — Google service account key (gitignored)
- `config.yaml` — active config (gitignored); `config.example.yaml` is the template
- `config_test.yaml` — committed; uses explicit file lists pointed at `example_input/` (gitignored, supplied locally). Use this for `--dry-run` validation of parser changes.
- `example_input/`, `input/` — gitignored; hold real exports and must never be committed.

### Config keys

- `spreadsheet_id`, `credentials_path`, `sheet_name` — Google Sheets target
- `person_names` — matched case-insensitively against Splitwise group column headers
- `input_dir` **or** explicit lists: `mizrahi_ccs_files`, `splitwise_regular_files`, `splitwise_group_files`
