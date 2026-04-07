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

No test suite exists yet. Run the tool with `--dry-run` to validate parsing logic against real input files. `config_test.yaml` + `example_input/` (committed, anonymized) exists for exactly this purpose.

Note: `main.py` is an unused placeholder left over from `uv init`. The real entry point is `sync_expenses.py`.

## Architecture

The tool reads expense exports and appends new rows to a Google Sheet, using a deterministic UUID (`_id`) for idempotent upsert — re-running never duplicates or overwrites existing rows.

**Data flow:** config.yaml → `sync_expenses.py` → parsers → `sheets.py` → Google Sheets

### Input sources

Two input modes, configured in `config.yaml`:
- **`input_dir`** — auto-discovers and classifies all files in a directory (preferred)
- **Explicit lists** (`cc_files`, `splitwise_regular_files`, `splitwise_group_files`, `wolt_files`) — for manual file specification

### Parsers (`parsers/`)

- `cc.py` — Isracard Excel exports. Extracts CC last-4 digits as source identifier; reads Hebrew-header transaction table (columns: date, business name, ..., charge amount)
- `splitwise.py` — Two variants:
  - **Regular** (1:1): uses total `Cost` column as the joint expense
  - **Group** (3+ people): computes combined share for configured `person_names` using sign convention (negative = owes, positive = paid and is owed → share = `Cost - value`, zero = not involved). `Category == "Payment"` rows (settlements) are filtered out.
- `wolt.py` — Wolt order-history CSV (tab-separated). Skips `Wolt Gift Card` top-ups (already on CC) and zero-amount rows. Applies `wolt_tax_factor` multiplier to each amount — intended for when Wolt is paid from pre-tax salary at a marginal tax rate (a factor below 1 discounts each NIS accordingly). Default factor is `1.0`.
- `common.py` — Shared: `make_expense()` builds normalized dicts; `make_expense_id()` generates a UUID5 from `date|source|description|amount:.2f` via `NAMESPACE_URL`. Also holds Splitwise CSV helpers (header detection, cost/date parsing, payment filter).
- `discover.py` — File classification for `input_dir` mode:
  - `.xlsx` → CC if the Hebrew header `תאריך רכישה` is found in the first 15 rows.
  - `.csv` → `wolt` if header exactly matches `["Date","Category","Amount","Currency Symbol","Store"]`; else Splitwise based on header `["Date","Description","Category","Cost","Currency",…]` and the count of non-empty person columns after `Currency` (≤2 → regular, 3+ → group).

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
- `config_test.yaml` — committed; uses explicit file lists pointed at `example_input/`. Use this for `--dry-run` validation of parser changes.

### Config keys

- `spreadsheet_id`, `credentials_path`, `sheet_name` — Google Sheets target
- `person_names` — matched case-insensitively against Splitwise group column headers
- `wolt_tax_factor` — multiplier applied per Wolt order amount (default `1.0`)
- `input_dir` **or** explicit lists: `cc_files`, `splitwise_regular_files`, `splitwise_group_files`, `wolt_files`
