"""Auto-discover and classify input files in a directory."""

import csv
from pathlib import Path

import openpyxl


_WOLT_HEADER = ["Date", "Category", "Amount", "Currency Symbol", "Store"]


def _classify_csv(file_path: str) -> str | None:
    """
    Classify a CSV as 'splitwise_regular', 'splitwise_group', 'wolt', or None.

    Wolt CSVs have a header: Date,Category,Amount,Currency Symbol,Store
    Splitwise CSVs have a header starting with "Date,Description,Category,Cost,Currency".
    Regular (1:1) exports have exactly 2 person columns after Currency.
    Group exports have 3+ person columns.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header_line = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Date,") or stripped.startswith("Date\t"):
            header_line = line
            break

    if header_line is None:
        return None

    delimiter = "\t" if "\t" in header_line else ","
    reader = csv.reader([header_line], delimiter=delimiter)
    fields = [f.strip() for f in next(reader)]

    if fields == _WOLT_HEADER:
        return "wolt"

    expected_start = ["Date", "Description", "Category", "Cost", "Currency"]
    if fields[:5] != expected_start:
        return None

    person_cols = [f.strip() for f in fields[5:] if f.strip()]

    if len(person_cols) <= 2:
        return "splitwise_regular"
    else:
        return "splitwise_group"


def _is_cc_excel(file_path: str) -> bool:
    """Check if an Excel file looks like an Isracard CC export."""
    try:
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
        for row in ws.iter_rows(max_row=15, values_only=True):
            cell = str(row[0] or "")
            if "תאריך רכישה" in cell:
                return True
        return False
    except Exception:
        return False


def _is_cibus_excel(file_path: str) -> bool:
    """Check if an Excel file looks like a Cibus meal-card export."""
    try:
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
        for row in ws.iter_rows(max_row=10, values_only=True):
            cell = str(row[0] or "")
            if "שם בית העסק" in cell:
                return True
        return False
    except Exception:
        return False


def discover_files(input_dir: str, person_names: list[str]) -> dict:
    """
    Auto-discover and classify input files in a directory.

    Returns:
        {
            "cc_files": [path, ...],
            "splitwise_regular": [path, ...],
            "splitwise_group": [path, ...],
        }
    """
    input_path = Path(input_dir)
    result = {"cc_files": [], "cibus": [], "splitwise_regular": [], "splitwise_group": [], "wolt": []}

    for f in sorted(input_path.iterdir()):
        if f.suffix.lower() in (".xlsx", ".xls"):
            if _is_cibus_excel(str(f)):
                result["cibus"].append(str(f))
            elif _is_cc_excel(str(f)):
                result["cc_files"].append(str(f))
        elif f.suffix.lower() == ".csv":
            csv_type = _classify_csv(str(f))
            if csv_type:
                result[csv_type].append(str(f))

    return result
