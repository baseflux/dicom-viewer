#!/usr/bin/env python3
"""Trim the published `docs/` viewer so animations keep every Nth thumbnail while stills remain intact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retain fewer thumbnails in docs for animated series.")
    parser.add_argument("--docs", "-d", type=Path, default=Path("docs"), help="Docs folder that GitHub Pages publishes.")
    parser.add_argument("--sample-rate", type=int, default=2, help="Keep every Nth thumbnail for animations.")
    return parser.parse_args()


def sample_frames(frames: Iterable[str], rate: int, min_keep: int = 2) -> list[str]:
    if rate <= 1:
        return list(frames)
    frames = list(frames)
    if len(frames) <= min_keep:
        return frames
    sampled = [frames[i] for i in range(0, len(frames), rate)]
    if frames[-1] != sampled[-1]:
        sampled.append(frames[-1])
    return sampled


def run_trim(args: argparse.Namespace) -> None:
    manifest_path = args.docs / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"No manifest found at {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    keep_paths: set[Path] = set()
    for entry in manifest.get("series", []):
        frames = entry.get("frames", [])
        if not frames:
            continue
        if entry.get("frame_count", 0) > 1:
            sampled = sample_frames(frames, args.sample_rate)
            entry["frames"] = sampled
            entry["frame_count"] = len(sampled)
        keep_paths.update(args.docs / f for f in entry["frames"])

    thumbnails_root = args.docs / "thumbnails"
    for path in thumbnails_root.rglob("*.jpg"):
        if path not in keep_paths:
            path.unlink()

    for dir_path in sorted(thumbnails_root.rglob("*"), reverse=True):
        if dir_path.is_dir() and not any(dir_path.iterdir()):
            dir_path.rmdir()

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Trimmed docs thumbnails with sample rate {args.sample_rate}")


def main() -> None:
    args = parse_args()
    run_trim(args)


if __name__ == "__main__":
    main()
