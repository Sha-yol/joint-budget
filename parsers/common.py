"""Shared utilities for expense parsers."""

import csv
import uuid
from datetime import datetime


def make_expense_id(date: str, source: str, description: str, amount: float) -> str:
    """Generate a deterministic UUID from the 4 identifying fields."""
    key = f"{date}|{source}|{description}|{amount:.2f}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def make_expense(date: str, source: str, description: str, amount: float) -> dict:
    """Build a normalized expense dict with a deterministic _id."""
    return {
        "_id": make_expense_id(date, source, description, amount),
        "תאריך": date,
        "מקור": source,
        "תיאור": description,
        "סכום": amount,
    }


def find_csv_header(lines: list[str]) -> int | None:
    """Find the index of the Splitwise CSV header line ('Date,...')."""
    for i, line in enumerate(lines):
        if line.strip().startswith("Date,"):
            return i
    return None


def read_splitwise_csv(file_path: str) -> tuple[list[str], csv.DictReader]:
    """Read a Splitwise CSV, skip leading notes, return (lines, reader)."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header_idx = find_csv_header(lines)
    if header_idx is None:
        raise ValueError(f"Could not find CSV header in {file_path}")

    reader = csv.DictReader(lines[header_idx:])
    return lines, reader


def parse_cost(row: dict) -> float | None:
    """Extract and validate the Cost field from a Splitwise row."""
    cost_str = row.get("Cost", "").replace(",", "").strip()
    if not cost_str:
        return None
    try:
        return float(cost_str)
    except ValueError:
        return None


def parse_splitwise_date(row: dict) -> str | None:
    """Parse and normalize a Splitwise date field to YYYY-MM-DD."""
    date_raw = row.get("Date", "").strip()
    if not date_raw:
        return None
    try:
        return datetime.strptime(date_raw, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def is_payment(row: dict) -> bool:
    """Check if a Splitwise row is a payment (settlement), not an expense."""
    return row.get("Category", "").strip() == "Payment"
