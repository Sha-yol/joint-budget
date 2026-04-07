# joint-budget

Consolidate joint credit-card, Splitwise, and Wolt expenses into a single Google Sheet for monthly household budgeting.

Built for an Israeli household workflow: Hebrew-headed Isracard exports, Splitwise expenses split across multiple people and groups, and Wolt orders charged from pre-tax salary.

## What it does

Drop your monthly export files into one folder and run one command. The tool:

- Parses **Isracard credit card** Excel exports (Hebrew headers, multi-card aware).
- Parses **Splitwise** CSV exports — both 1:1 and group exports (computes your household's combined share from the per-person columns).
- Parses **Wolt** order-history CSV, with an optional tax-factor adjustment for pre-tax-salary benefits.
- Appends new rows to your Google Sheet using a deterministic UUID per expense, so re-running is **idempotent** — nothing is ever duplicated or overwritten.
- Never touches the manual columns (`קטגוריית תקציב`, `הערות`) — you fill those in by hand after syncing.

## Quick start

```bash
# 1. Install
uv sync

# 2. Configure
cp config.example.yaml config.yaml
# edit config.yaml: spreadsheet_id, credentials_path, person_names, input_dir

# 3. Preview without touching the sheet
uv run python sync_expenses.py config.yaml --dry-run

# 4. Sync for real
uv run python sync_expenses.py config.yaml
```

Full setup — Google service account, sharing the sheet with it, etc. — is in [SETUP.md](SETUP.md).

## Monthly workflow

1. Export each CC statement from Isracard (Excel).
2. Export Splitwise (1:1 and each group) as CSV.
3. Export Wolt order history (if applicable).
4. Drop all files into the folder referenced by `input_dir`.
5. `uv run python sync_expenses.py config.yaml`
6. Fill in budget categories and notes directly in the Google Sheet.

Safe to include overlapping months of files — deduplication by deterministic ID handles it.

## Input sources

### Credit card — Isracard Excel

Downloaded from the Isracard dashboard. The parser extracts the last 4 digits of the card from the header area and uses them as the `מקור` (source) value, so transactions from different cards stay distinguishable in the sheet.

### Splitwise — regular (1:1)

A 1:1 Splitwise export has ≤2 person columns after `Currency`. The full `Cost` column is imported as the joint amount.

### Splitwise — group (3+ people)

For group exports (3+ person columns), only your household's **combined share** is imported. Per row, for each configured household member:

- Negative value → that person owes → their share = `|value|`
- Positive value → that person paid → their share = `Cost - value`
- Zero → not involved, contributes nothing

The household members come from `person_names` in config, matched case-insensitively against Splitwise column headers. `Category == Payment` rows (settlements) are filtered out.

### Wolt order history

Tab-separated CSV export. `Wolt Gift Card` top-ups are skipped (they already appear on the CC). Zero-amount rows (cancellations, orders fully covered by a gift card) are skipped. If `wolt_tax_factor` is set, every order amount is multiplied by it — useful when Wolt is paid from pre-tax salary at a marginal tax rate (a factor below 1 discounts each order accordingly).

## Configuration

See [`config.example.yaml`](config.example.yaml) for the annotated template. Key fields:

| Key | Purpose |
| --- | --- |
| `spreadsheet_id` | From `docs.google.com/spreadsheets/d/{THIS}/edit` |
| `credentials_path` | Path to your Google service account JSON key |
| `sheet_name` | Worksheet tab name (default `expenses`) |
| `person_names` | Household members, matched against Splitwise group columns |
| `wolt_tax_factor` | Optional multiplier for Wolt amounts (default `1.0`) |
| `input_dir` | Folder to auto-scan for export files |

The `input_dir` workflow is preferred; for explicit file lists, use `cc_files`, `splitwise_regular_files`, `splitwise_group_files`, `wolt_files`. See [`config_test.yaml`](config_test.yaml) for an example pointing at `example_input/`.

## Sheet layout

Each row written by the sync has this shape:

```
_id | תאריך | מקור | תיאור | סכום | קטגוריית תקציב | הערות
```

- `_id` — deterministic UUID5 of `date|source|description|amount`; powers the idempotent upsert.
- `תאריך` / `מקור` / `תיאור` / `סכום` — date, source, description, amount. Written by the tool.
- `קטגוריית תקציב` / `הערות` — budget category and notes. Manual, never modified by the tool.

## Project layout

```
sync_expenses.py        # entry point
sheets.py               # Google Sheets idempotent upsert
parsers/
  cc.py                 # Isracard Excel
  splitwise.py          # Splitwise regular + group
  wolt.py               # Wolt order history
  discover.py           # auto-classify files in input_dir
  common.py             # make_expense, make_expense_id, shared helpers
config.example.yaml     # config template
config_test.yaml        # config pointing at example_input/
example_input/          # anonymized sample files for dry-run validation
SETUP.md                # Google service account walkthrough
```

## Development notes

- Python 3.10+, dependencies managed by `uv` (`pyproject.toml` / `uv.lock`).
- No test suite. Validate parser changes with `uv run python sync_expenses.py config_test.yaml --dry-run`.
- `credentials.json` and `config.yaml` are gitignored.
- Re-running the real sync is safe — the deterministic `_id` guarantees existing rows are never re-inserted or overwritten.
