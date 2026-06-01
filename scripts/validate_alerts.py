from __future__ import annotations

from pathlib import Path

import great_expectations as ge
import pandas as pd

REQUIRED_COLUMNS = [
    "alert_id", "source", "service", "owner_team", "tier", "environment", "title",
    "metric_name", "metric_value", "threshold", "severity",
]


def main() -> None:
    src = Path("data/generated/alerts.csv")
    out = Path("data/validated/alerts.csv")
    df = pd.read_csv(src)
    gdf = ge.from_pandas(df)
    results = [
        gdf.expect_table_columns_to_match_set(REQUIRED_COLUMNS, exact_match=True),
        gdf.expect_column_values_to_not_be_null("alert_id"),
        gdf.expect_column_values_to_be_between("tier", 0, 3),
        gdf.expect_column_values_to_be_in_set("environment", ["prod", "staging"]),
        gdf.expect_column_values_to_be_in_set("severity", ["low", "medium", "high", "critical"]),
        gdf.expect_column_values_to_be_between("metric_value", min_value=0, strict_min=True),
        gdf.expect_column_values_to_be_between("threshold", min_value=0, strict_min=True),
    ]
    failures = [r for r in results if not r.success]
    if failures:
        raise SystemExit(f"Great Expectations validation failed: {failures}")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"validated {len(df)} alerts -> {out}")


if __name__ == "__main__":
    main()
