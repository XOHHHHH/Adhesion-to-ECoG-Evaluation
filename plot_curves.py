"""Draw unsmoothed peel curves from instrument CSVs as self-contained SVG files."""

from __future__ import annotations

import argparse
import json
import math
import re
from html import escape
from pathlib import Path

import pandas as pd

from peel_analysis import FORCE_COLUMN, read_instrument_csv


COLORS = ("#176a8a", "#bf4d30", "#427d46", "#8258a5", "#a67516", "#b04d75", "#4c6973", "#826545")
DISPLACEMENT_COLUMN = re.compile(r"^(?:位移|Displacement)_(\d+)$", re.IGNORECASE)


def _curves(frame: pd.DataFrame, width_mm: float) -> list[tuple[str, list[tuple[float, float]]]]:
    if not math.isfinite(width_mm) or width_mm <= 0:
        raise ValueError("width_mm must be a positive finite measured width")
    width_m = width_mm / 1000.0
    displacement = {
        match.group(1): name
        for name in frame.columns
        if (match := DISPLACEMENT_COLUMN.fullmatch(str(name).strip()))
    }
    curves = []
    for name in frame.columns:
        match = FORCE_COLUMN.fullmatch(str(name).strip())
        if not match or match.group(1) not in displacement:
            continue
        x = pd.to_numeric(frame[displacement[match.group(1)]], errors="coerce")
        y = pd.to_numeric(frame[name], errors="coerce") / width_m
        points = [
            (float(xv), float(yv))
            for xv, yv in zip(x, y)
            if pd.notna(xv) and pd.notna(yv) and math.isfinite(float(xv)) and math.isfinite(float(yv))
        ]
        if len(points) < 2:
            continue
        # Display-only thinning; peak statistics are computed separately from all raw points.
        stride = max(1, math.ceil(len(points) / 1500))
        peak_index = max(range(len(points)), key=lambda index: points[index][1])
        indices = sorted(set(range(0, len(points), stride)) | {peak_index, len(points) - 1})
        shown = [points[index] for index in indices]
        curves.append((f"曲线 {match.group(1)}", shown))
    if not curves:
        raise ValueError("No matching raw force and displacement columns")
    return curves


def make_svg(frame: pd.DataFrame, width_mm: float, title: str) -> str:
    curves = _curves(frame, width_mm)
    all_points = [point for _, points in curves for point in points]
    xmin, xmax = min(p[0] for p in all_points), max(p[0] for p in all_points)
    ymin, ymax = min(0.0, min(p[1] for p in all_points)), max(p[1] for p in all_points)
    if xmax == xmin:
        xmax = xmin + 1.0
    if ymax == ymin:
        ymax = ymin + 1.0

    left, right, top, bottom = 88, 760, 58, 462
    sx = lambda value: left + (value - xmin) / (xmax - xmin) * (right - left)
    sy = lambda value: bottom - (value - ymin) / (ymax - ymin) * (bottom - top)
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="540" viewBox="0 0 1000 540">',
        '<rect x="0" y="0" width="1000" height="540" fill="#fff"/>',
        f'<text x="88" y="34" font-size="20" font-family="Arial,sans-serif" fill="#222">{escape(title)}</text>',
        f'<path d="M{left},{top}V{bottom}H{right}" fill="none" stroke="#555" stroke-width="1.5"/>',
    ]
    for tick in range(5):
        xf = xmin + tick / 4 * (xmax - xmin)
        yf = ymin + tick / 4 * (ymax - ymin)
        px, py = sx(xf), sy(yf)
        lines.append(f'<path d="M{px:.1f},{bottom}v5 M{left-5},{py:.1f}h5" stroke="#666"/>')
        lines.append(f'<text x="{px:.1f}" y="{bottom+23}" text-anchor="middle" font-size="12">{xf:.3g}</text>')
        lines.append(f'<text x="{left-9}" y="{py+4:.1f}" text-anchor="end" font-size="12">{yf:.3g}</text>')
    lines.append('<text x="424" y="515" text-anchor="middle" font-size="15">位移（原始导出单位，请核实）</text>')
    lines.append('<text transform="translate(25 265) rotate(-90)" text-anchor="middle" font-size="15">单位宽度剥离力 (N/m)</text>')
    for index, (label, points) in enumerate(curves):
        color = COLORS[index % len(COLORS)]
        path = " ".join(("M" if i == 0 else "L") + f"{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(points))
        lines.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.6" opacity="0.9"/>')
        ly = 83 + index * 27
        lines.append(f'<path d="M805,{ly-5}h25" stroke="{color}" stroke-width="2"/>')
        lines.append(f'<text x="840" y="{ly}" font-size="14">{escape(label)}</text>')
    lines.append('</svg>')
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("figures"))
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        raw_path = Path(entry["raw_file"])
        if not raw_path.is_absolute():
            raw_path = manifest_path.parent / raw_path
        frame, _ = read_instrument_csv(raw_path.resolve())
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(entry["sample_set_id"]))
        output = args.out_dir / f"{safe_id}.svg"
        output.write_text(make_svg(frame, float(entry["width_mm"]), str(entry["sample_set_id"])), encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()

