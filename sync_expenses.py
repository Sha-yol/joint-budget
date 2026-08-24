#!/usr/bin/env python3
"""
Expense Sync - Consolidate CC and Splitwise expenses into Google Sheets.

Usage:
    python sync_expenses.py config.yaml [--dry-run]
"""

import sys
from pathlib import Path

import yaml

from parsers import (
    discover_files,
    parse_mizrahi_ccs_excel,
    parse_splitwise_regular,
    parse_splitwise_group,
)
from sheets import sync_to_sheets


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_expenses(config: dict) -> list[dict]:
    """Parse all input files and return a flat list of expense dicts."""
    person_names = config.get("person_names", ["Alice", "Bob"])
    all_expenses = []

    input_dir = config.get("input_dir")
    if input_dir:
        discovered = discover_files(input_dir)
        print(f"Scanning {input_dir}/ ...")
        all_discovered = (
            discovered["mizrahi_ccs"]
            + discovered["splitwise_regular"]
            + discovered["splitwise_group"]
        )
        skipped = [
            str(f)
            for f in sorted(Path(input_dir).iterdir())
            if str(f) not in all_discovered and not f.name.startswith(".")
        ]
        print(f"  Mizrahi CCs files:      {[Path(p).name for p in discovered['mizrahi_ccs']]}")
        print(f"  Splitwise (1:1):        {[Path(p).name for p in discovered['splitwise_regular']]}")
        print(f"  Splitwise (group 3+):   {[Path(p).name for p in discovered['splitwise_group']]}")
        if skipped:
            print(f"  Skipped (unrecognized): {[Path(p).name for p in skipped]}")
        print()

        for path in discovered["mizrahi_ccs"]:
            print(f"Parsing Mizrahi CCs: {path}")
            expenses = parse_mizrahi_ccs_excel(path)
            print(f"  → {len(expenses)} transactions")
            all_expenses.extend(expenses)

        for path in discovered["splitwise_regular"]:
            print(f"Parsing Splitwise regular: {path}")
            expenses = parse_splitwise_regular(path)
            print(f"  → {len(expenses)} expenses")
            all_expenses.extend(expenses)

        for path in discovered["splitwise_group"]:
            print(f"Parsing Splitwise group: {path}")
            expenses = parse_splitwise_group(path, person_names)
            print(f"  → {len(expenses)} expenses (combined share)")
            all_expenses.extend(expenses)
    else:
        for mz_file in config.get("mizrahi_ccs_files", []):
            path = mz_file["path"]
            print(f"Parsing Mizrahi CCs file: {path}")
            expenses = parse_mizrahi_ccs_excel(path)
            print(f"  → {len(expenses)} transactions")
            all_expenses.extend(expenses)

        for sw_file in config.get("splitwise_regular_files", []):
            path = sw_file["path"]
            print(f"Parsing Splitwise regular: {path}")
            expenses = parse_splitwise_regular(path)
            print(f"  → {len(expenses)} expenses")
            all_expenses.extend(expenses)

        for sw_file in config.get("splitwise_group_files", []):
            path = sw_file["path"]
            print(f"Parsing Splitwise group: {path}")
            expenses = parse_splitwise_group(path, person_names)
            print(f"  → {len(expenses)} expenses (combined share)")
            all_expenses.extend(expenses)

    return all_expenses


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <config.yaml> [--dry-run]")
        sys.exit(1)

    config_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    config = load_config(config_path)
    all_expenses = collect_expenses(config)

    print(f"\nTotal: {len(all_expenses)} expenses from all sources.")

    if dry_run:
        print("\n[DRY RUN] Would upload the following expenses:")
        all_expenses.sort(key=lambda x: x["תאריך"])
        for exp in all_expenses:
            print(f"  {exp['תאריך']}  {exp['מקור']:>10}  {exp['סכום']:>10.2f}  {exp['תיאור']}")
        return

    added = sync_to_sheets(
        expenses=all_expenses,
        spreadsheet_id=config["spreadsheet_id"],
        credentials_path=config["credentials_path"],
        sheet_name=config.get("sheet_name", "expenses"),
    )
    print(f"\nDone. {added} new rows added to the sheet.")


if __name__ == "__main__":
    main()
