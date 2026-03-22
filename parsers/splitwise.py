"""Parsers for Splitwise CSV exports (regular and group)."""

from .common import (
    make_expense,
    read_splitwise_csv,
    parse_cost,
    parse_splitwise_date,
    is_payment,
)


def parse_splitwise_regular(file_path: str) -> list[dict]:
    """
    Parse a Splitwise export for a 1:1 relationship (non-group).

    Uses the total Cost column since it's the joint expense.
    Filters out Payment-type entries.
    """
    _, reader = read_splitwise_csv(file_path)
    expenses = []

    for row in reader:
        date = parse_splitwise_date(row)
        if not date or is_payment(row):
            continue

        cost = parse_cost(row)
        if cost is None:
            continue

        expenses.append(make_expense(
            date=date,
            source="splitwise",
            description=row["Description"].strip(),
            amount=round(cost, 2),
        ))

    return expenses


def parse_splitwise_group(
    file_path: str,
    person_names: list[str],
) -> list[dict]:
    """
    Parse a Splitwise group export.

    Computes the combined share for the specified persons.
    For each person:
      - Negative column value -> their share = |value| (they owe)
      - Positive column value -> their share = Cost - value (they paid)
      - Zero -> not involved in this expense

    Filters out Payment-type entries.
    """
    _, reader = read_splitwise_csv(file_path)
    fieldnames = reader.fieldnames
    expenses = []

    for row in reader:
        date = parse_splitwise_date(row)
        if not date or is_payment(row):
            continue

        cost = parse_cost(row)
        if cost is None:
            continue

        # Compute combined share for the specified persons
        combined_share = 0.0
        for name in person_names:
            col_value = None
            for field in fieldnames:
                if name.lower() in field.lower():
                    col_value = float(row[field].replace(",", ""))
                    break

            if col_value is None or col_value == 0:
                continue
            elif col_value < 0:
                combined_share += abs(col_value)
            else:
                combined_share += (cost - col_value)

        if combined_share <= 0:
            continue

        expenses.append(make_expense(
            date=date,
            source="splitwise",
            description=row["Description"].strip(),
            amount=round(combined_share, 2),
        ))

    return expenses
