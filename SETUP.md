# Expense Sync – Setup Guide

## 1. Install dependencies

```bash
uv sync
```

This creates a `.venv` and installs everything from `pyproject.toml`.

## 2. Set up Google Sheets API access

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Google Sheets API**: APIs & Services → Library → search "Google Sheets API" → Enable
4. Create a **Service Account**: APIs & Services → Credentials → Create Credentials → Service Account
   - Give it a name (e.g., `expense-sync`)
   - No special roles needed
5. Create a key for the service account: click the service account → Keys → Add Key → JSON
6. Save the downloaded JSON file as `credentials.json` in this folder

## 3. Prepare the Google Sheet

1. Create a new Google Sheet (or use an existing one)
2. Copy the spreadsheet ID from the URL: `docs.google.com/spreadsheets/d/{THIS_PART}/edit`
3. Share the sheet with your service account email (found in `credentials.json` under `client_email`), giving it **Editor** access

## 4. Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`:
- Set `spreadsheet_id` to your sheet ID
- Set `credentials_path` to the path of your JSON key file
- Set `input_dir` to the folder where you'll drop export files

## 5. Run

```bash
# Preview what would be uploaded (no changes made):
uv run python sync_expenses.py config.yaml --dry-run

# Actually upload:
uv run python sync_expenses.py config.yaml
```

## Monthly workflow

1. Export the "all credit cards" statement from Mizrahi (Excel download)
2. Export Splitwise: regular expenses + each group export
3. Drop all files into your `input_dir` folder
4. Run `uv run python sync_expenses.py config.yaml`
5. Fill in budget categories and notes in the Google Sheet

Re-running is safe – existing rows are never duplicated or overwritten.
Safe to include overlapping months of CC files – dedup handles it.
