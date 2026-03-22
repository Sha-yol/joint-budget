"""Parser for Isracard credit card Excel exports."""

import re
from datetime import datetime

import openpyxl

from .common import make_expense


def parse_cc_excel(file_path: str) -> list[dict]:
    """
    Parse an Isracard credit card Excel export.

    The file has a header area with the CC last-4 digits, followed by
    a transaction table starting with a Hebrew header row.
    """
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    # Extract CC last 4 from the header area (e.g., "מסטרקארד - 1234")
    cc_last4 = None
    header_row_idx = None

    for i, row in enumerate(rows):
        cell = str(row[0] or "")
        match = re.search(r"[-–]\s*(\d{4})", cell)
        if match and cc_last4 is None:
            cc_last4 = match.group(1)
        if "תאריך רכישה" in cell:
            header_row_idx = i
            break

    if cc_last4 is None:
        raise ValueError(f"Could not find CC last-4 in {file_path}")
    if header_row_idx is None:
        raise ValueError(f"Could not find transaction header in {file_path}")

    expenses = []
    for row in rows[header_row_idx + 1:]:
        date_str = row[0]
        business_name = row[1]
        charge_amount = row[4]  # סכום חיוב

        if date_str is None or not isinstance(date_str, str) or not re.match(r"\d{2}\.\d{2}\.\d{2}", date_str):
            continue

        try:
            date_obj = datetime.strptime(date_str, "%d.%m.%y")
            formatted_date = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue

        expenses.append(make_expense(
            date=formatted_date,
            source=cc_last4,
            description=str(business_name or "").strip(),
            amount=round(float(charge_amount), 2),
        ))

    return expenses
