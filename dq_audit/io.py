"""Input helpers for CSV and Parquet datasets."""

from __future__ import annotations

from pathlib import Path

import polars as pl


def read_dataset(path: str | Path) -> pl.DataFrame:
    """Read a CSV or Parquet dataset into a Polars DataFrame."""
    input_path = Path(path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    suffix = input_path.suffix.lower()

    if suffix == ".csv":
        return pl.read_csv(input_path, null_values=[""])

    if suffix == ".parquet":
        return pl.read_parquet(input_path)

    raise ValueError(
        f"Unsupported input file type: {suffix!r}. Supported types: .csv, .parquet"
    )
