"""Audit 90-degree peel exports without changing or smoothing the raw data."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

import pandas as pd


FORCE_COLUMN = re.compile(r"^(?:力|Force)_(\d+)$", re.IGNORECASE)
REQUIRED = (
    "sample_set_id",
    "batch_id",
    "formulation_id",
    "treatment",
    "substrate",
    "width_mm",
    "raw_file",
)


def read_instrument_csv(path: Path) -> tuple[pd.DataFrame, str]:
    """Read the original instrument file; reject processed N/m exports."""
    errors: list[str] = []
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            frame = pd.read_csv(path, encoding=encoding, low_memory=False)
        except (UnicodeError, pd.errors.ParserError) as exc:
            errors.append(f"{encoding}: {exc}")
            continue
        if any(FORCE_COLUMN.fullmatch(str(column).strip()) for column in frame.columns):
            return frame, encoding
        errors.append(f"{encoding}: no raw 力_# / Force_# columns")
    raise ValueError(f"Not a supported raw-force CSV: {path}\n" + "\n".join(errors))


def summarize_curves(frame: pd.DataFrame, width_mm: float) -> list[dict]:
    """Return one result per raw force column; never smooth or baseline-correct."""
    if not math.isfinite(width_mm) or width_mm <= 0:
        raise ValueError("width_mm must be a positive finite measured width")
    width_m = width_mm / 1000.0
    results: list[dict] = []
    for column in frame.columns:
        match = FORCE_COLUMN.fullmatch(str(column).strip())
        if not match:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        values = values[values.notna() & values.map(math.isfinite)]
        if values.empty:
            raise ValueError(f"No numeric raw force values in {column}")
        peak_force_n = float(values.max())
        if peak_force_n <= 0:
            raise ValueError(f"Non-positive peak in {column}; check force sign and units")
        results.append(
            {
                "replicate_id": int(match.group(1)),
                "raw_force_column": str(column),
                "n_points": int(len(values)),
                "peak_force_N": peak_force_n,
                "peak_force_per_width_N_per_m": peak_force_n / width_m,
            }
        )
    if not results:
        raise ValueError("No raw force columns found")
    return sorted(results, key=lambda row: row["replicate_id"])


def _summary(values: list[float]) -> tuple[float, float | None]:
    return statistics.mean(values), statistics.stdev(values) if len(values) > 1 else None


def analyze_manifest(manifest_path: Path) -> dict:
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must be a non-empty JSON list")

    curves: list[dict] = []
    sources: list[dict] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each manifest item must be an object")
        missing = [field for field in REQUIRED if field not in entry or entry[field] == ""]
        if missing:
            raise ValueError(f"Missing manifest fields: {', '.join(missing)}")
        sample_set_id = str(entry["sample_set_id"])
        if sample_set_id in seen:
            raise ValueError(f"Duplicate sample_set_id: {sample_set_id}")
        seen.add(sample_set_id)

        source_path = Path(str(entry["raw_file"]))
        if not source_path.is_absolute():
            source_path = manifest_path.parent / source_path
        source_path = source_path.resolve()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)

        width_mm = float(entry["width_mm"])
        frame, encoding = read_instrument_csv(source_path)
        curve_rows = summarize_curves(frame, width_mm)
        metadata = {field: entry[field] for field in REQUIRED if field != "raw_file"}
        curves.extend([{**metadata, **row} for row in curve_rows])
        sources.append(
            {
                "sample_set_id": sample_set_id,
                "raw_file": str(source_path),
                "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                "encoding": encoding,
                "n_curves": len(curve_rows),
            }
        )

    batch_groups: dict[tuple, list[float]] = defaultdict(list)
    for row in curves:
        key = (row["formulation_id"], row["treatment"], row["substrate"], row["batch_id"])
        batch_groups[key].append(row["peak_force_per_width_N_per_m"])
    batches: list[dict] = []
    for (formulation_id, treatment, substrate, batch_id), values in sorted(batch_groups.items()):
        mean, sd = _summary(values)
        batches.append(
            {
                "formulation_id": formulation_id,
                "treatment": treatment,
                "substrate": substrate,
                "batch_id": batch_id,
                "n_curves": len(values),
                "mean_peak_N_per_m": mean,
                "sd_between_curves_N_per_m": sd,
            }
        )

    condition_groups: dict[tuple, list[float]] = defaultdict(list)
    for row in batches:
        key = (row["formulation_id"], row["treatment"], row["substrate"])
        condition_groups[key].append(row["mean_peak_N_per_m"])
    conditions: list[dict] = []
    for (formulation_id, treatment, substrate), values in sorted(condition_groups.items()):
        mean, sd = _summary(values)
        conditions.append(
            {
                "formulation_id": formulation_id,
                "treatment": treatment,
                "substrate": substrate,
                "n_independent_batches": len(values),
                "mean_of_batch_means_N_per_m": mean,
                "sd_between_batches_N_per_m": sd,
            }
        )
    return {
        "method": "Unsmoothed maximum of original force in N divided by recorded width in m",
        "sources": sources,
        "curves": curves,
        "batches": batches,
        "conditions": conditions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Private manifest JSON with raw CSV paths")
    parser.add_argument("--out", type=Path, default=Path("results.json"))
    args = parser.parse_args()
    result = analyze_manifest(args.manifest.resolve())
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(result['curves'])} curves, {len(result['batches'])} batches to {args.out}")


if __name__ == "__main__":
    main()

