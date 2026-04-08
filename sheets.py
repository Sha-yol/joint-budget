"""Google Sheets sync with idempotent upsert logic."""

import sys

try:
    import gspread
except ImportError:
    gspread = None

HEADERS = ["_id", "תאריך", "מקור", "תיאור", "סכום", "קטגוריית תקציב", "הערות"]
ID_COL_IDX = 0


def sync_to_sheets(
    expenses: list[dict],
    spreadsheet_id: str,
    credentials_path: str,
    sheet_name: str = "expenses",
) -> int:
    """
    Upload expenses to Google Sheets with idempotent logic.

    - Creates the sheet/headers if they don't exist
    - Only appends rows whose _id doesn't already exist
    - Never modifies manual columns of existing rows

    Returns the number of new rows added.
    """
    if gspread is None:
        print("Error: gspread is not installed. Run: pip install gspread")
        sys.exit(1)

    gc = gspread.service_account(filename=credentials_path)
    spreadsheet = gc.open_by_key(spreadsheet_id)

    # Get or create the worksheet
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=sheet_name, rows=1000, cols=len(HEADERS)
        )
        worksheet.append_row(HEADERS)
        print(f"Created new sheet '{sheet_name}' with headers.")

    # Read existing data
    existing_data = worksheet.get_all_values()

    # Ensure headers exist
    if not existing_data or existing_data[0] != HEADERS:
        if not existing_data:
            worksheet.append_row(HEADERS)
            existing_data = [HEADERS]
        else:
            print(f"Warning: existing headers {existing_data[0]} don't match expected {HEADERS}")
            print("Proceeding with existing sheet structure.")

    # Build set of existing _id values (column A)
    existing_ids = set()
    for row in existing_data[1:]:
        if len(row) > ID_COL_IDX and row[ID_COL_IDX]:
            existing_ids.add(row[ID_COL_IDX])

    # Filter to only new expenses
    new_expenses = [exp for exp in expenses if exp["_id"] not in existing_ids]

    if not new_expenses:
        print("No new expenses to add.")
        return 0

    # Sort by date and append
    new_expenses.sort(key=lambda x: x["תאריך"])

    rows_to_add = [
        [exp["_id"], exp["תאריך"], "'" + exp["מקור"], exp["תיאור"], exp["סכום"], "", ""]
        for exp in new_expenses
    ]

    worksheet.append_rows(rows_to_add, value_input_option="USER_ENTERED")
    print(f"Added {len(rows_to_add)} new expenses.")
    return len(rows_to_add)
