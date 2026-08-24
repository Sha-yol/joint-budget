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
- **Explicit lists** (`cc_files`, `cibus_files`, `mizrahi_ccs_files`, `splitwise_regular_files`, `splitwise_group_files`, `wolt_files`) — for manual file specification

### Parsers (`parsers/`)

- `mizrahi_ccs.py` — Mizrahi bank "all credit cards" xlsx export. Has 3 currency tabs (`חיובים בשקלים` / `בדולרים` / `באירו`); only the NIS sheet is read (foreign-currency sheets are currently empty). Inside the NIS sheet, multiple card blocks are stacked vertically — each begins with a header `חשבון כרטיס: ... ארבע ספרות אחרונות NNNN`, then a transaction table. The parser walks all blocks, emitting rows whose `מקור` is the per-block last-4. Zero-amount rows (e.g. waived `דמי כרטיס`) are skipped. Date format is `dd/mm/yyyy` (unlike Isracard's `dd.mm.yy`).
- `cc.py` — Isracard Excel exports. Extracts CC last-4 digits as source identifier; reads Hebrew-header transaction table (columns: date, business name, ..., charge amount)
- `splitwise.py` — Two variants:
  - **Regular** (1:1): uses total `Cost` column as the joint expense
  - **Group** (3+ people): computes combined share for configured `person_names` using sign convention (negative = owes, positive = paid and is owed → share = `Cost - value`, zero = not involved). `Category == "Payment"` rows (settlements) are filtered out.
- `wolt.py` — Wolt order-history CSV (tab-separated). Skips `Wolt Gift Card` top-ups (loading the Wolt wallet, accounted for via Cibus or CC) and zero-amount rows. Applies `pretax_factor` to each amount — intended for when Wolt is paid from pre-tax salary at a marginal tax rate (a factor below 1 discounts each NIS accordingly). Default factor is `1.0`.
- `cibus.py` — Cibus (Pluxee) meal-card xlsx exports. Each row has an employer/Cibus-credit portion (`השתתפות המעסיק`) and an optional CC supplement (`שולם באשראי`) used when Cibus credit runs short. The amount written to the sheet is `employer × pretax_factor + cc` — the CC supplement is NOT discounted because it comes from a personal CC, not pre-tax salary. Skips `Wolt - Wolt Gift Card` rows (loading Wolt wallet, not an expense) and rows whose status is not `הסתיים`. The `_id` is computed from the gross (`employer + cc`) so it's invariant to `pretax_factor` changes.
- `common.py` — Shared: `make_expense()` builds normalized dicts; `make_expense_id()` generates a UUID5 from `date|source|description|amount:.2f` via `NAMESPACE_URL`. Also holds Splitwise CSV helpers (header detection, cost/date parsing, payment filter).
- `discover.py` — File classification for `input_dir` mode:
  - `.xlsx` → Cibus if `שם בית העסק` is found in the first 10 rows; else Mizrahi CCs if the sheet `חיובים בשקלים` exists and contains `חשבון כרטיס` in its first 3 rows; else Isracard CC if `תאריך רכישה` is found in the first 15 rows. Order matters since all three formats are xlsx.
  - `.csv` → `wolt` if header exactly matches `["Date","Category","Amount","Currency Symbol","Store"]`; else Splitwise based on header `["Date","Description","Category","Cost","Currency",…]` and the count of non-empty person columns after `Currency` (≤2 → regular, 3+ → group).

### Cibus ↔ Wolt deduplication

A Wolt order paid directly via Cibus (or via Cibus-funded Wolt credit) appears in **both** the Cibus xlsx and the Wolt CSV. After all parsers run, `_dedup_cibus_wolt()` in `sync_expenses.py` matches each Cibus row whose description starts with `Wolt - ` against Wolt rows by `(date, store_norm)` (store_norm strips the `Wolt - ` prefix). On match, the Wolt row is dropped and the Cibus row's `סכום` is overridden using the Wolt gross as authoritative — Wolt reports the actual final amount after refunds (e.g. for weight-based items where extra credit was reserved and refunded back to Cibus credit). The Cibus row's `_id` is left untouched so reruns are idempotent regardless of whether the Wolt CSV is present.

Math (X = Cibus credit, Y = CC supplement, W = Wolt gross, Z = X+Y-W = presumed refund):
- final amount written = `(X - Z) * pretax_factor + Y` = `(W - Y) * pretax_factor + Y`

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
- `pretax_factor` — multiplier applied to Wolt amounts and to the Cibus-credit portion of Cibus rows (default `1.0`)
- `input_dir` **or** explicit lists: `cc_files`, `cibus_files`, `mizrahi_ccs_files`, `splitwise_regular_files`, `splitwise_group_files`, `wolt_files`
