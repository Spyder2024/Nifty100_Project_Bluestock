"""CLI runner — compute and persist valuation estimates.

Usage:
    python -m src.analytics.run_valuation
    python -m src.analytics.run_valuation --year 2024
    python -m src.analytics.run_valuation --wacc 0.10 --terminal-growth 0.04
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.valuation import (  # noqa: E402
    compute_all_valuations,
    load_valuations,
)

DB_PATH = PROJECT_ROOT / "output" / "nifty100.db"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute intrinsic valuations for Nifty 100 companies."
    )
    parser.add_argument(
        "--year",
        type=str,
        default=None,
        help="Fiscal year, e.g. '2024'. Default: all years.",
    )
    parser.add_argument(
        "--wacc",
        type=float,
        default=0.12,
        help="WACC (default: 0.12).",
    )
    parser.add_argument(
        "--terminal-growth",
        type=float,
        default=0.05,
        help="Terminal growth rate (default: 0.05).",
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))

    print(
        f"Computing valuations  WACC={args.wacc}  "
        f"terminal_growth={args.terminal_growth}"
    )
    print(f"  Year filter: {args.year or 'ALL'}")

    count = compute_all_valuations(
        conn,
        year=args.year,
        wacc=args.wacc,
        terminal_growth=args.terminal_growth,
    )
    print(f"  Inserted {count} valuation records.\n")

    # Summary
    val_df = load_valuations(conn)
    if not val_df.empty:
        n_cos = val_df["company_id"].nunique()
        print(f"Summary across {n_cos} companies:")
        for col in (
            "graham_number",
            "dcf_intrinsic_value",
            "ddm_intrinsic_value",
            "relative_avg_value",
        ):
            if col in val_df.columns:
                valid = val_df[col].dropna()
                if not valid.empty:
                    print(
                        f"  {col:30s}  "
                        f"median={valid.median():10.2f}  "
                        f"mean={valid.mean():10.2f}  "
                        f"non-null={len(valid)}/{len(val_df)}"
                    )

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
