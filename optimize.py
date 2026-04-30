#!/usr/bin/env python3
"""
PNG Optimizer — lossless compression with optional resizing.

Pipeline:
  1. Resize (Pillow, LANCZOS) — only downscales, preserves aspect ratio.
  2. Re-encode losslessly via Pillow with optimize=True.
  3. Final lossless squeeze via oxipng (preferred) or optipng (fallback).

Designed for Ubuntu. Skips non-PNG files in source/.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

DEFAULT_MAX_DIM = 1280
SOURCE_DIR = Path("source")
DIST_DIR = Path("dist")


def find_optimizer():
    """Return (tool_name, tool_path) or (None, None) if not installed."""
    for tool in ("oxipng", "optipng"):
        path = shutil.which(tool)
        if path:
            return tool, path
    return None, None


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def resize_if_needed(img: Image.Image, max_dim: int):
    """Downscale longest side to max_dim, preserve aspect ratio. Never upscale."""
    w, h = img.size
    longest = max(w, h)
    if longest <= max_dim:
        return img, False
    scale = max_dim / longest
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return img.resize(new_size, Image.LANCZOS), True


def run_lossless_tool(tool: str, path: Path) -> None:
    """Run oxipng or optipng on path. Raises CalledProcessError on failure."""
    if tool == "oxipng":
        cmd = ["oxipng", "-o", "max", "--strip", "safe", "-q", str(path)]
    else:  # optipng
        cmd = ["optipng", "-o7", "-strip", "all", "-quiet", str(path)]
    subprocess.run(cmd, check=True, capture_output=True)


def optimize_one(src_path: Path, dst_path: Path, max_dim: int, tool):
    """Optimize a single PNG. Returns (orig_bytes, final_bytes, was_resized)."""
    orig_bytes = src_path.stat().st_size

    with Image.open(src_path) as img:
        # Preserve transparency for palette PNGs (otherwise alpha can be lost).
        if img.mode == "P" and "transparency" in img.info:
            img = img.convert("RGBA")
        img.load()
        out_img, was_resized = resize_if_needed(img, max_dim)
        out_img.save(dst_path, format="PNG", optimize=True)

    if tool:
        try:
            run_lossless_tool(tool, dst_path)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="replace").strip() if e.stderr else ""
            print(f"  ! {tool} failed on {src_path.name}: {stderr}", file=sys.stderr)

    return orig_bytes, dst_path.stat().st_size, was_resized


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lossless PNG optimizer for web/UI assets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--source", type=Path, default=SOURCE_DIR, help="Source folder")
    parser.add_argument("--dist", type=Path, default=DIST_DIR, help="Destination folder")
    parser.add_argument("--max-dim", type=int, default=DEFAULT_MAX_DIM,
                        help="Cap longest side in pixels (use 0 to disable resizing)")
    parser.add_argument("--no-tool", action="store_true",
                        help="Skip the external oxipng/optipng pass")
    args = parser.parse_args()

    if not args.source.is_dir():
        print(f"x Source folder not found: {args.source}", file=sys.stderr)
        return 1

    args.dist.mkdir(parents=True, exist_ok=True)
    max_dim = args.max_dim if args.max_dim > 0 else 10**9  # effectively no cap

    tool, tool_path = (None, None) if args.no_tool else find_optimizer()
    if args.no_tool:
        print("-- Skipping external optimizer (--no-tool).")
    elif tool:
        print(f"-- Using {tool} ({tool_path}) for final lossless pass.")
    else:
        print("!! Neither oxipng nor optipng found. Install one for ~10-30% extra savings:")
        print("     sudo apt install oxipng     # preferred")
        print("     sudo apt install optipng    # fallback")
        print("   Continuing with Pillow-only optimization.\n")

    pngs = sorted(p for p in args.source.iterdir()
                  if p.is_file() and p.suffix.lower() == ".png")
    if not pngs:
        print(f"No .png files found in {args.source}/")
        return 0

    total_before = total_after = 0
    cap_label = f"{args.max_dim}px" if args.max_dim > 0 else "none"
    print(f"\nOptimizing {len(pngs)} file(s) -> {args.dist}/")
    print(f"Max longest side: {cap_label} | Strategy: lossless\n")
    header = f"{'File':<40} {'Before':>10} {'After':>10} {'Saved':>8}  Resized"
    print(header)
    print("-" * len(header))

    for src in pngs:
        dst = args.dist / src.name
        try:
            before, after, resized = optimize_one(src, dst, max_dim, tool)
        except Exception as e:
            print(f"x {src.name}: {e}", file=sys.stderr)
            continue
        total_before += before
        total_after += after
        saved_pct = (1 - after / before) * 100 if before else 0
        flag = "yes" if resized else "-"
        name = src.name if len(src.name) <= 40 else src.name[:37] + "..."
        print(f"{name:<40} {human_size(before):>10} {human_size(after):>10} "
              f"{saved_pct:>7.1f}%  {flag}")

    print("-" * len(header))
    if total_before:
        total_saved_pct = (1 - total_after / total_before) * 100
        print(f"{'TOTAL':<40} {human_size(total_before):>10} "
              f"{human_size(total_after):>10} {total_saved_pct:>7.1f}%")
    print(f"\nDone. Output in: {args.dist}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
