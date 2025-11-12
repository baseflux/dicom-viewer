#!/usr/bin/env python3
"""
Organize the local DICOM dump into surgery+modality folders and export ordered PNG frames
for looped playback.

Usage example:
  ./organize_dicoms.py --input DICOM --output dicom_01 --copy-dicom
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Tuple, Dict, Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sort DICOMs into surgery/modality trees with PNG frames.")
    parser.add_argument("--input", "-i", type=Path, default=Path("DICOM"), help="Source folder containing raw DICOM files.")
    parser.add_argument("--output", "-o", type=Path, default=Path("dicom_01"), help="Destination root for organized data.")
    parser.add_argument("--shoulder-from", default="", help="Inclusive StudyDate lower bound for shoulder surgery (YYYYMMDD).")
    parser.add_argument("--shoulder-to", default="", help="Inclusive StudyDate upper bound for shoulder surgery (YYYYMMDD).")
    parser.add_argument("--ankle-from", default="", help="Inclusive StudyDate lower bound for ankle surgery (YYYYMMDD).")
    parser.add_argument("--ankle-to", default="", help="Inclusive StudyDate upper bound for ankle surgery (YYYYMMDD).")
    parser.add_argument("--copy-dicom", action="store_true", help="Duplicate original DICOM files within each series folder.")
    return parser.parse_args()


def ensure_imaging_deps() -> Tuple[Any, Any, Any]:
    try:
        import numpy as np
    except ImportError as error:  # pragma: no cover
        print("Install numpy (pip install numpy) before running.", file=sys.stderr)
        raise SystemExit(1) from error

    try:
        from PIL import Image
    except ImportError as error:
        print("Install Pillow (pip install pillow) before running.", file=sys.stderr)
        raise SystemExit(1) from error

    try:
        import pydicom
        from pydicom.pixel_data_handlers.util import apply_voi_lut
    except ImportError as error:
        print("Install pydicom (pip install pydicom pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg) before running.", file=sys.stderr)
        raise SystemExit(1) from error

    return np, Image, (pydicom, apply_voi_lut)


def looks_like_dicom(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            header = handle.read(132)
        return len(header) >= 132 and header[128:132] == b"DICM"
    except OSError:
        return False


def sanitize(name: str, default: str = "Series") -> str:
    name = (name or "").strip().replace("\0", "")
    name = re.sub(r"[^\w\-\.\s]+", "_", name)
    name = re.sub(r"\s+", "_", name)
    return (name[:80] or default)


MODALITY_GROUPS = {
    "CR": "XRAY",
    "DX": "XRAY",
    "DR": "XRAY",
    "PX": "XRAY",
    "XA": "XRAY",
    "RF": "XRAY",
    "CT": "CT",
    "MR": "MRI",
    "US": "US",
    "NM": "NM",
    "PT": "PET",
    "MG": "MAMMO",
    "OT": "OTHER",
    "SC": "SECONDARY",
}


def infer_modality_group(ds) -> str:
    mod = str(getattr(ds, "Modality", "")).upper().strip()
    if mod in MODALITY_GROUPS:
        return MODALITY_GROUPS[mod]
    text = " ".join(str(getattr(ds, attr, "")) for attr in ("StudyDescription", "SeriesDescription", "ProtocolName", "BodyPartExamined"))
    text = text.upper()
    for keyword, group in (("MRI", "MRI"), ("CT", "CT"), ("XRAY", "XRAY"), ("ULTRASOUND", "US")):
        if keyword in text:
            return group
    return "OTHER"


KEYWORDS = {
    "SHOULDER": "01_surg_shoulder",
    "ROTATOR": "01_surg_shoulder",
    "CLAVICLE": "01_surg_shoulder",
    "HUMERUS": "01_surg_shoulder",
    "AC JOINT": "01_surg_shoulder",
    "ANKLE": "02_surg_ankle",
    "MALLEOLUS": "02_surg_ankle",
    "TIBIA": "02_surg_ankle",
    "FIBULA": "02_surg_ankle",
    "FOOT": "02_surg_ankle",
    "TALAR": "02_surg_ankle",
}

UNSORTED_FIELDS = ("StudyDescription", "SeriesDescription", "ProtocolName", "BodyPartExamined")


def normalize_unsorted_label(ds) -> str:
    pieces = []
    for attr in UNSORTED_FIELDS:
        value = str(getattr(ds, attr, "") or "").strip()
        if value:
            pieces.append(value)
    if not pieces:
        return "_unsorted"
    identifier = " ".join(dict.fromkeys(pieces))  # preserve order, drop duplicates
    study_date = str(getattr(ds, "StudyDate", "") or "")
    if study_date:
        identifier = f"{study_date} {identifier}"
    return sanitize(identifier, default="_unsorted")


def in_range(date: str, lo: str, hi: str) -> bool:
    if not re.fullmatch(r"\d{8}", date or ""):
        return False
    if lo and date < lo:
        return False
    if hi and date > hi:
        return False
    return True


def classify_surgery(ds, ranges: Dict[str, Tuple[str, str]]) -> str:
    study_date = str(getattr(ds, "StudyDate", "") or "")
    text = " ".join(str(getattr(ds, attr, "")) for attr in ("StudyDescription", "SeriesDescription", "ProtocolName", "BodyPartExamined")).upper()

    if ranges["shoulder"][0] and in_range(study_date, *ranges["shoulder"]):
        return "01_surg_shoulder"
    if ranges["ankle"][0] and in_range(study_date, *ranges["ankle"]):
        return "02_surg_ankle"

    for keyword, label in KEYWORDS.items():
        if keyword in text:
            return label

    return normalize_unsorted_label(ds)


def series_key(ds) -> str:
    study_date = str(getattr(ds, "StudyDate", ""))
    series_num = str(getattr(ds, "SeriesNumber", "0"))
    desc = sanitize(str(getattr(ds, "SeriesDescription", "")))
    return f"{study_date}_S{series_num.zfill(3)}_{desc}"


def slice_sort_key(ds) -> Tuple[int, float]:
    try:
        instance = int(getattr(ds, "InstanceNumber", 0))
    except (TypeError, ValueError):
        instance = 0
    z = float("inf")
    try:
        ipp = getattr(ds, "ImagePositionPatient", None)
        if ipp and len(ipp) >= 3:
            z = float(ipp[2])
    except (TypeError, ValueError):
        pass
    return instance, z


def to_uint8(arr, np_module):
    arr = arr.astype(np_module.float32)
    minimum, maximum = float(arr.min()), float(arr.max())
    if maximum == minimum:
        return np_module.zeros_like(arr, dtype=np_module.uint8)
    scaled = (arr - minimum) / (maximum - minimum) * 255.0
    return scaled.astype(np_module.uint8)


def normalize_array(arr, np_module):
    arr = np_module.asarray(arr)
    while arr.ndim > 3:
        arr = arr.reshape(-1, *arr.shape[-2:])
    arr = np_module.squeeze(arr)
    return arr


def main() -> None:
    args = parse_args()
    input_dir = args.input.expanduser().resolve()
    output_root = args.output.expanduser().resolve()
    np_module, Image, (pydicom, apply_voi_lut) = ensure_imaging_deps()

    if not input_dir.is_dir():
        print(f"Input directory {input_dir} does not exist.", file=sys.stderr)
        raise SystemExit(1)

    output_root.mkdir(parents=True, exist_ok=True)

    ranges = {
        "shoulder": (args.shoulder_from, args.shoulder_to),
        "ankle": (args.ankle_from, args.ankle_to),
    }

    storyteller: Dict[Tuple[str, str, str], list[Path]] = defaultdict(list)
    meta_info: Dict[Tuple[str, str, str], Dict[str, str]] = {}

    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        if not (path.suffix.lower() == ".dcm" or looks_like_dicom(path)):
            continue
        try:
            ds = pydicom.dcmread(path, force=True)
        except Exception:
            continue
        if "PixelData" not in ds:
            continue

        surgery = classify_surgery(ds, ranges)
        modality = infer_modality_group(ds)
        s_key = series_key(ds)
        bucket = (surgery, modality, s_key)
        storyteller[bucket].append(path)
        if bucket not in meta_info:
            meta_info[bucket] = {
                "StudyDate": str(getattr(ds, "StudyDate", "")),
                "StudyTime": str(getattr(ds, "StudyTime", "")),
                "SeriesNumber": str(getattr(ds, "SeriesNumber", "")),
                "SeriesDescription": str(getattr(ds, "SeriesDescription", "")),
                "Modality": str(getattr(ds, "Modality", "")),
                "BodyPartExamined": str(getattr(ds, "BodyPartExamined", "")),
            }

    total_saved = 0
    skipped = 0

    for (surgery, modality, s_key), paths in storyteller.items():
        sanitized_mod = sanitize(modality, default="MOD")
        series_dir = output_root / surgery / sanitized_mod / sanitize(s_key)
        series_dir.mkdir(parents=True, exist_ok=True)

        datasets: list[Tuple[Tuple[int, float], Any, Path]] = []
        for src in paths:
            try:
                ds = pydicom.dcmread(src, force=True)
                datasets.append((slice_sort_key(ds), ds, src))
            except Exception as exc:
                print(f"⚠️  Skip {src.name}: {exc}")
        if not datasets:
            skipped += 1
            continue
        datasets.sort(key=lambda item: item[0])

        idx = 0
        for order, ds, src in datasets:
            try:
                arr = apply_voi_lut(ds.pixel_array, ds)
            except Exception:
                arr = ds.pixel_array
            if str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
                arr = arr.max() - arr
            arr = normalize_array(arr, np_module)
            if arr.ndim == 3 and arr.shape[-1] in (3, 4):
                frames = [arr]
            elif arr.ndim == 3:
                frames = [to_uint8(arr[i], np_module) for i in range(arr.shape[0])]
            else:
                frames = [to_uint8(arr, np_module)]

            for frame in frames:
                idx += 1
                png_path = series_dir / f"frame_{idx:04d}.png"
                frame = normalize_array(frame, np_module)
                img = Image.fromarray(frame)
                if img.mode not in {"L", "RGB", "RGBA"}:
                    img = img.convert("L")
                img.save(png_path, format="PNG", optimize=True)

        if idx:
            meta_path = series_dir / "series.info.txt"
            info = meta_info[(surgery, modality, s_key)]
            meta_path.write_text("\n".join(f"{k}: {v}" for k, v in info.items()) + "\n", encoding="utf-8")
            if args.copy_dicom:
                dcm_dir = series_dir / "dcm"
                dcm_dir.mkdir(exist_ok=True)
                for _, ds, src in datasets:
                    target = dcm_dir / src.name
                    if not target.exists():
                        target.write_bytes(src.read_bytes())
            print(f"✅ {surgery}/{sanitized_mod}/{sanitize(s_key)}  ({idx} PNG frames)")
            total_saved += 1
        else:
            skipped += 1

    print(f"\n📊 Done. Series with frames: {total_saved} | Series skipped: {skipped}")


if __name__ == "__main__":
    main()
