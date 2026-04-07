"""Parser for Wolt order history CSV exports."""

import csv
from datetime import datetime

from .common import make_expense


def _parse_wolt_date(date_str: str) -> str | None:
    """Parse Wolt date like '3/27/26 2:13:00 PM' to 'YYYY-MM-DD'."""
    date_str = date_str.strip()
    for fmt in ("%m/%d/%y %I:%M:%S %p", "%m/%d/%y %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_wolt(file_path: str, tax_factor: float = 1.0) -> list[dict]:
    """
    Parse a Wolt order history CSV export.

    tax_factor: multiplier applied to each order amount to reflect the
      real cost after income tax considerations (used when Wolt
      payments come from pre-tax salary at your marginal rate).

    Skips:
    - Rows with amount = 0 (cancelled orders or gift-card-covered orders)
    - "Wolt Gift Card" rows (balance top-ups, tracked via CC)
    """
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        expenses = []

        for row in reader:
            store = row.get("Store", "").strip()
            if store == "Wolt Gift Card":
                continue

            date = _parse_wolt_date(row.get("Date", ""))
            if not date:
                continue

            amount_str = row.get("Amount", "").replace(",", "").strip()
            try:
                amount = float(amount_str)
            except ValueError:
                continue

            if amount == 0:
                continue

            expense = make_expense(date=date, source="wolt", description=store, amount=amount)
            expense["סכום"] = round(amount * tax_factor, 2)
            expenses.append(expense)

    return expenses
