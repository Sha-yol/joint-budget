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
    parse_cc_excel,
    parse_cibus,
    parse_splitwise_regular,
    parse_splitwise_group,
    parse_wolt,
)
from sheets import sync_to_sheets


_WOLT_PREFIX = "Wolt - "


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_expenses(config: dict) -> list[dict]:
    """Parse all input files and return a flat list of expense dicts."""
    person_names = config.get("person_names", ["Alice", "Bob"])
    pretax_factor = config.get("pretax_factor", 1.0)
    all_expenses = []

    input_dir = config.get("input_dir")
    if input_dir:
        discovered = discover_files(input_dir, person_names)
        print(f"Scanning {input_dir}/ ...")
        all_discovered = (
            discovered["cc_files"]
            + discovered["cibus"]
            + discovered["splitwise_regular"]
            + discovered["splitwise_group"]
            + discovered["wolt"]
        )
        skipped = [
            str(f)
            for f in sorted(Path(input_dir).iterdir())
            if str(f) not in all_discovered and not f.name.startswith(".")
        ]
        print(f"  CC files:               {[Path(p).name for p in discovered['cc_files']]}")
        print(f"  Cibus files:            {[Path(p).name for p in discovered['cibus']]}")
        print(f"  Splitwise (1:1):        {[Path(p).name for p in discovered['splitwise_regular']]}")
        print(f"  Splitwise (group 3+):   {[Path(p).name for p in discovered['splitwise_group']]}")
        print(f"  Wolt orders:            {[Path(p).name for p in discovered['wolt']]}")
        if skipped:
            print(f"  Skipped (unrecognized): {[Path(p).name for p in skipped]}")
        print()

        for path in discovered["cc_files"]:
            print(f"Parsing CC: {path}")
            expenses = parse_cc_excel(path)
            print(f"  → {len(expenses)} transactions (CC {expenses[0]['מקור'] if expenses else '?'})")
            all_expenses.extend(expenses)

        for path in discovered["cibus"]:
            print(f"Parsing Cibus: {path}")
            expenses = parse_cibus(path, pretax_factor=pretax_factor)
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

        for path in discovered["wolt"]:
            print(f"Parsing Wolt orders: {path}")
            expenses = parse_wolt(path, pretax_factor=pretax_factor)
            print(f"  → {len(expenses)} orders")
            all_expenses.extend(expenses)
    else:
        for cc_file in config.get("cc_files", []):
            path = cc_file["path"]
            print(f"Parsing CC file: {path}")
            expenses = parse_cc_excel(path)
            print(f"  → {len(expenses)} transactions (CC {expenses[0]['מקור'] if expenses else '?'})")
            all_expenses.extend(expenses)

        for cibus_file in config.get("cibus_files", []):
            path = cibus_file["path"]
            print(f"Parsing Cibus file: {path}")
            expenses = parse_cibus(path, pretax_factor=pretax_factor)
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

        for wolt_file in config.get("wolt_files", []):
            path = wolt_file["path"]
            print(f"Parsing Wolt orders: {path}")
            expenses = parse_wolt(path, pretax_factor=pretax_factor)
            print(f"  → {len(expenses)} orders")
            all_expenses.extend(expenses)

    return all_expenses


def _dedup_cibus_wolt(expenses: list[dict], pretax_factor: float) -> list[dict]:
    """
    Reconcile Cibus 'Wolt - X' rows with matching Wolt CSV rows.

    A Wolt order paid via Cibus appears in BOTH the Cibus xlsx and the Wolt CSV.
    For each such pair, drop the Wolt row (keeping the Cibus row, since it carries
    the employer/CC split) and override the Cibus row's סכום using the Wolt gross
    as authoritative — Wolt reports the actual final amount after refunds (e.g. for
    weight-based items where extra credit was reserved and refunded).

    Math (X = Cibus credit, Y = CC supplement, W = Wolt gross, Z = X+Y-W = refund):
        adjusted_employer = X - Z = W - Y
        final amount      = (X - Z) * pretax_factor + Y

    The Cibus row's _id is NOT touched — it was computed from the Cibus gross
    (employer + cc) and must remain invariant to both pretax_factor changes and
    Wolt-CSV presence so reruns stay idempotent.
    """
    # Index Wolt rows by (date, store_norm) — list per bucket since duplicates are possible.
    wolt_buckets: dict[tuple[str, str], list[dict]] = {}
    for exp in expenses:
        meta = exp.get("_meta")
        if meta and meta.get("kind") == "wolt":
            key = (exp["תאריך"], meta["store_norm"])
            wolt_buckets.setdefault(key, []).append(exp)

    dropped_wolt_ids = set()
    for exp in expenses:
        meta = exp.get("_meta")
        if not (meta and meta.get("kind") == "cibus"):
            continue
        if not exp["תיאור"].startswith(_WOLT_PREFIX):
            continue

        key = (exp["תאריך"], meta["store_norm"])
        bucket = wolt_buckets.get(key)
        if not bucket:
            continue

        # Pick the first un-dropped Wolt candidate in the bucket.
        match = None
        for candidate in bucket:
            if id(candidate) not in dropped_wolt_ids:
                match = candidate
                break
        if match is None:
            continue

        dropped_wolt_ids.add(id(match))

        wolt_gross = match["_meta"]["raw_amount"]    # W
        cibus_cc = meta["cc"]                         # Y
        adjusted_employer = max(wolt_gross - cibus_cc, 0)   # X - Z
        exp["סכום"] = round(adjusted_employer * pretax_factor + cibus_cc, 2)   # (X-Z)*F + Y

    # Build the output: drop matched Wolt rows, strip _meta from everything.
    result = []
    for exp in expenses:
        if exp.get("_meta", {}).get("kind") == "wolt" and id(exp) in dropped_wolt_ids:
            continue
        exp.pop("_meta", None)
        result.append(exp)
    return result


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <config.yaml> [--dry-run]")
        sys.exit(1)

    config_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    config = load_config(config_path)
    pretax_factor = config.get("pretax_factor", 1.0)
    all_expenses = collect_expenses(config)
    before = len(all_expenses)
    all_expenses = _dedup_cibus_wolt(all_expenses, pretax_factor)
    deduped = before - len(all_expenses)
    if deduped:
        print(f"\nDeduplicated {deduped} Wolt rows matched against Cibus.")

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
