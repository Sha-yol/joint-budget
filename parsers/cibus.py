"""Parser for Cibus (Pluxee) meal-card xlsx exports."""

from datetime import datetime

import openpyxl

from .common import make_expense


_HEADER_MARKER = "שם בית העסק"
_STATUS_DONE = "הסתיים"
_GIFT_CARD = "Wolt - Wolt Gift Card"
_WOLT_PREFIX = "Wolt - "


def _normalize_store(description: str) -> str:
    """Strip the 'Wolt - ' prefix so descriptions can be matched against Wolt CSV rows."""
    if description.startswith(_WOLT_PREFIX):
        return description[len(_WOLT_PREFIX):]
    return description


def parse_cibus(file_path: str, pretax_factor: float = 1.0) -> list[dict]:
    """
    Parse a Cibus meal-card xlsx export.

    pretax_factor: multiplier applied to the Cibus-credit (employer) portion of each
      transaction to reflect post-tax cost. The CC supplement portion (שולם באשראי)
      is NOT discounted because it comes from a personal CC, not from pre-tax salary.

    Skips:
    - "Wolt - Wolt Gift Card" rows (loading the Wolt wallet, not an expense)
    - Rows whose status is not "הסתיים" (incomplete/cancelled)
    - Rows where both employer and CC portions are 0
    """
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    header_row_idx = None
    for i, row in enumerate(rows):
        cell = str(row[0] or "")
        if _HEADER_MARKER in cell:
            header_row_idx = i
            break

    if header_row_idx is None:
        raise ValueError(f"Could not find Cibus header in {file_path}")

    expenses = []
    for row in rows[header_row_idx + 1:]:
        business = row[0]
        date_cell = row[1]
        status = row[4]
        employer = row[9] or 0
        cc = row[11] or 0

        if not business or not isinstance(business, str):
            continue
        description = business.strip()

        if description == _GIFT_CARD:
            continue
        if str(status or "").strip() != _STATUS_DONE:
            continue
        if employer == 0 and cc == 0:
            continue

        if isinstance(date_cell, datetime):
            date = date_cell.strftime("%Y-%m-%d")
        elif isinstance(date_cell, str):
            try:
                date = datetime.strptime(date_cell.split(" ")[0], "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                continue
        else:
            continue

        employer = float(employer)
        cc = float(cc)
        gross = round(employer + cc, 2)

        expense = make_expense(date=date, source="cibus", description=description, amount=gross)
        expense["סכום"] = round(employer * pretax_factor + cc, 2)
        expense["_meta"] = {
            "kind": "cibus",
            "store_norm": _normalize_store(description),
            "employer": employer,
            "cc": cc,
        }
        expenses.append(expense)

    return expenses
