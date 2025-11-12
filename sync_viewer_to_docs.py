#!/usr/bin/env python3
"""Sync the generated `viewer/` output into `docs/` so GitHub Pages can serve it."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy viewer/ into docs/ for GitHub Pages.")
    parser.add_argument("--viewer", "-v", type=Path, default=Path("viewer"), help="Source viewer folder.")
    parser.add_argument("--docs", "-d", type=Path, default=Path("docs"), help="Target docs folder.")
    parser.add_argument("--clean", action="store_true", help="Purge the docs folder before copying.")
    return parser.parse_args()


def purge_path(target: Path) -> None:
    if not target.exists():
        return
    for child in target.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def main() -> None:
    args = parse_args()
    viewer = args.viewer.resolve()
    docs = args.docs.resolve()

    if not viewer.is_dir():
        raise SystemExit(f"{viewer} does not exist or is not a directory.")

    if args.clean and docs.exists():
        purge_path(docs)
    docs.mkdir(parents=True, exist_ok=True)

    for item in viewer.iterdir():
        dest = docs / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    print(f"Synced {viewer} --> {docs}")


if __name__ == "__main__":
    main()
