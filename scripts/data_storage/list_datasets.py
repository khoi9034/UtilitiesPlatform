from __future__ import annotations

import argparse

from common import SAFE_CATALOG_FIELDS, load_config, safe_catalog_rows


def matches(row: dict[str, str], args: argparse.Namespace) -> bool:
    filters = {
        "utility_type": args.utility_type,
        "current_stage": args.stage,
        "source_format": args.source_format,
        "sensitivity_level": args.sensitivity,
        "approved_for_export": args.export_approval,
    }
    return all(not value or row.get(field, "").lower() == value.lower() for field, value in filters.items())


def print_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("No utility datasets have been registered yet.")
        return
    fields = ["dataset_name", "utility_type", "source_format", "current_stage", "sensitivity_level", "approved_for_export"]
    widths = {field: max(len(field), *(len(row.get(field, "")) for row in rows)) for field in fields}
    print(" | ".join(field.ljust(widths[field]) for field in fields))
    print("-+-".join("-" * widths[field] for field in fields))
    for row in rows:
        print(" | ".join(row.get(field, "").ljust(widths[field]) for field in fields))


def main() -> int:
    parser = argparse.ArgumentParser(description="List registered datasets without exposing source paths.")
    parser.add_argument("--utility-type")
    parser.add_argument("--stage")
    parser.add_argument("--source-format")
    parser.add_argument("--sensitivity")
    parser.add_argument("--export-approval", choices=["true", "false"])
    args = parser.parse_args()

    rows = [row for row in safe_catalog_rows(load_config()) if matches(row, args)]
    print_table([{field: row.get(field, "") for field in SAFE_CATALOG_FIELDS} for row in rows])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
