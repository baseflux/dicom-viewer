#!/usr/bin/env python3
"""Walk the organized `dicom_01` tree, classify each series as still/animation, and emit
a manifest + HTML quickviewer for local browsing."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Local DICOM Quickviewer</title>
  <style>
    :root {
      font-family: "Inter", system-ui, -apple-system, sans-serif;
      background: #101116;
      color: #f4f4f4;
    }
    body {
      margin: 0;
      padding: 1rem;
    }
    h1 {
      margin-bottom: 0.5rem;
    }
    #series {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1rem;
    }
    article {
      background: #171823;
      border: 1px solid #2f2f3a;
      border-radius: 0.75rem;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    article.animation {
      border-width: 2px;
      border-color: #9f7bff;
      box-shadow: 0 0 20px rgba(159, 123, 255, 0.4);
    }
    article.still {
      border-width: 2px;
      border-color: #ff9e00;
      box-shadow: 0 0 20px rgba(255, 158, 0, 0.35);
    }
    article:hover {
      border-color: #449af7;
    }
    article img {
      width: 100%;
      border-radius: 0.5rem;
      object-fit: cover;
      background: #0b0b11;
    }
    .meta {
      font-size: 0.85rem;
      color: #c7c7c7;
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .badge {
      padding: 0.15rem 0.5rem;
      border-radius: 999px;
      background: #2d313c;
      border: 1px solid transparent;
      transition: border-color 0.2s ease;
    }
    .info {
      font-size: 0.75rem;
      color: #99a0b5;
      line-height: 1.4;
      max-height: 5rem;
      overflow: hidden;
    }
    .filters {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1rem;
    }
    .filter {
      padding: 0.4rem 1rem;
      border-radius: 0.5rem;
      border: 1px solid #2f2f3a;
      background: #1f2233;
      color: #f4f4f4;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s ease, border-color 0.2s ease;
    }
    .filter.active {
      border-color: #9f7bff;
      background: #2f1e4d;
    }
    .filters,
    .group-filters {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-bottom: 1rem;
    }
    .filter,
    .group-filter {
      padding: 0.4rem 1rem;
      border-radius: 0.5rem;
      border: 1px solid #2f2f3a;
      background: #1f2233;
      color: #f4f4f4;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s ease, border-color 0.2s ease;
    }
    .filter.active,
    .group-filter.active {
      border-color: #9f7bff;
      background: #2f1e4d;
    }
    .note {
      margin: 0;
      margin-bottom: 1rem;
      padding: 0.65rem 1rem;
      border: 1px dashed #9f7bff;
      border-radius: 0.65rem;
      background: #1f2233;
      color: #e9e0ff;
      font-size: 0.9rem;
    }
    .badge.animation-label {
      border-color: #9f7bff;
      color: #fef5ff;
      background: rgba(159, 123, 255, 0.2);
    }
    .badge.still-label {
      border-color: #ff9e00;
      color: #fff0d8;
      background: rgba(255, 158, 0, 0.2);
    }
  </style>
</head>
<body>
  <h1>Local DICOM Quickviewer</h1>
  <p>Auto-generated from the organized `dicom_01` tree.</p>
  <div class="filters">
    <button class="filter active" data-filter="all">All</button>
    <button class="filter" data-filter="animation">Animation</button>
    <button class="filter" data-filter="still">Stills</button>
  </div>
  <div class="group-filters">
    <button class="group-filter active" data-group="all">All Series</button>
    <button class="group-filter" data-group="surgery01">Surgery 01</button>
    <button class="group-filter" data-group="surgery02">Surgery 02</button>
    <button class="group-filter" data-group="xray">X-ray</button>
    <button class="group-filter" data-group="ct">CT</button>
    <button class="group-filter" data-group="brain">Brain</button>
    <button class="group-filter" data-group="chest">Chest</button>
    <button class="group-filter" data-group="limbs">Limbs</button>
  </div>
  <div class="note">Purple cards loop while hovered; orange cards are stills. Use the filters to focus.</div>
  <div id="series">Loading…</div>
  <script>
    const container = document.getElementById("series");
    const manifestPath = "manifest.json";
    const filterButtons = document.querySelectorAll(".filter");
    const groupButtons = document.querySelectorAll(".group-filter");
    let activeFilter = "all";
    let activeGroup = "all";
    filterButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        activeFilter = btn.dataset.filter;
        updateFilterStates();
      });
    });
    groupButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        activeGroup = btn.dataset.group;
        updateFilterStates();
      });
    });

    function updateFilterStates() {
      filterButtons.forEach(btn => btn.classList.toggle("active", btn.dataset.filter === activeFilter));
      groupButtons.forEach(btn => btn.classList.toggle("active", btn.dataset.group === activeGroup));
      applyFilters();
    }

    function applyFilters() {
      const cards = container.querySelectorAll("article");
      cards.forEach(card => {
        const typeMatch =
          activeFilter === "all" ||
          (activeFilter === "animation" && card.classList.contains("animation")) ||
          (activeFilter === "still" && card.classList.contains("still"));
        const groupMatch = activeGroup === "all" || matchesGroup(card, activeGroup);
        card.style.display = typeMatch && groupMatch ? "flex" : "none";
      });
    }

    function matchesGroup(card, group) {
      const surgery = card.dataset.surgery || "";
      const modality = card.dataset.modality || "";
      const seriesName = card.dataset.seriesName || "";
      switch (group) {
        case "surgery01":
          return surgery.startsWith("01") || surgery.includes("surg_shoulder");
        case "surgery02":
          return surgery.startsWith("02") || surgery.includes("surg_ankle");
        case "xray":
          return modality.includes("xray");
        case "ct":
          return modality.includes("ct");
        case "brain":
          return surgery.includes("brain") || seriesName.includes("brain");
        case "chest":
          return surgery.includes("chest");
        case "limbs":
          return surgery.includes("lowerlimb") || surgery.includes("extremity") || seriesName.includes("leg") || seriesName.includes("hip");
        default:
          return true;
      }
    }
    fetch(manifestPath)
      .then(res => res.json())
      .then(render)
      .catch(err => {
        document.getElementById("series").textContent = "Failed to load manifest.";
        console.error(err);
      });

    function render(data) {
      container.innerHTML = "";
      data.series.forEach(entry => {
        const card = document.createElement("article");
        const heading = document.createElement("h2");
        heading.textContent = `${entry.surgery} · ${entry.modality}`;
        const previewIndex = Math.min(entry.frames.length - 1, entry.preview_index ?? 0);
        const img = document.createElement("img");
        img.src = entry.frames[previewIndex] || entry.preview || "";
        img.alt = entry.series;
        img.loading = "lazy";
        card.dataset.surgery = entry.surgery?.toLowerCase() || "";
        card.dataset.modality = entry.modality?.toLowerCase() || "";
        card.dataset.seriesName = entry.series?.toLowerCase() || "";
        card.append(heading, img);
        const badge = document.createElement("div");
        badge.className = "badge";
        badge.textContent = entry.type.toUpperCase();
        const count = document.createElement("span");
        count.textContent = `${entry.frame_count} frame${entry.frame_count === 1 ? "" : "s"}`;
        const isAnimation = entry.type === "animation" && entry.frames.length > 1;
        const isStill = entry.frame_count <= 1;
        const meta = document.createElement("div");
        meta.className = "meta";
        meta.append(badge, count);
        const infobox = document.createElement("div");
        infobox.className = "info";
        infobox.textContent = entry.series;
        if (entry.info_text) {
          infobox.textContent += "\\n" + entry.info_text;
        }
        card.append(meta, infobox);
        if (isAnimation) {
          badge.classList.add("animation-label");
          img.style.cursor = "ew-resize";
          card.classList.add("animation");
          const frames = entry.frames;
          const frameCount = frames.length;
          let idx = previewIndex;
          let loopHandle = null;
          let resumeHandle = null;
          const setFrame = index => {
            const safe = Math.max(0, Math.min(frameCount - 1, index));
            idx = safe;
            img.src = frames[safe];
          };

          const startLoop = () => {
            if (loopHandle) return;
            loopHandle = setInterval(() => {
              setFrame((idx + 1) % frameCount);
            }, 600);
          };
          const stopLoop = () => {
            if (loopHandle) {
              clearInterval(loopHandle);
              loopHandle = null;
            }
          };
          const scheduleResume = () => {
            if (resumeHandle) {
              clearTimeout(resumeHandle);
            }
            resumeHandle = setTimeout(() => {
              startLoop();
            }, 800);
          };
          const scrub = event => {
            const bounds = img.getBoundingClientRect();
            const x = event.clientX - bounds.left;
            const ratio = bounds.width ? Math.max(0, Math.min(1, x / bounds.width)) : 0;
            setFrame(Math.floor(ratio * (frameCount - 1)));
          };

          const handleMouseMove = event => {
            scrub(event);
            stopLoop();
            scheduleResume();
          };

          img.addEventListener("mousemove", handleMouseMove);
          img.addEventListener("mouseenter", event => {
            scrub(event);
            startLoop();
          });
          img.addEventListener("mouseleave", () => {
            stopLoop();
            if (resumeHandle) {
              clearTimeout(resumeHandle);
            }
            setFrame(previewIndex);
          });

          img.addEventListener("touchmove", event => {
            event.preventDefault();
            const touch = event.touches[0];
            if (touch) {
              const bounds = img.getBoundingClientRect();
              const x = touch.clientX - bounds.left;
              const ratio = bounds.width ? Math.max(0, Math.min(1, x / bounds.width)) : 0;
              setFrame(Math.floor(ratio * (frameCount - 1)));
              stopLoop();
              scheduleResume();
            }
          }, { passive: false });
        }
        if (isStill) {
          badge.classList.add("still-label");
          card.classList.add("still");
        }
        container.appendChild(card);
      });
      applyFilter(activeFilter);
    }
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Make a manifest+HTML quickviewer for dicom_01.")
    parser.add_argument("--root", "-r", type=Path, default=Path("dicom_01"), help="Organized DICOM root.")
    parser.add_argument("--viewer", "-v", type=Path, default=Path("viewer"), help="Output directory for viewer artifacts.")
    parser.add_argument("--max-frames", type=int, default=0, help="How many frames per series to reference in the manifest (0=all).")
    parser.add_argument("--thumb-width", type=int, default=640, help="Maximum width for generated JPEG thumbnails.")
    parser.add_argument("--thumb-quality", type=int, default=75, help="JPEG quality (1-95) for thumbnails.")
    return parser.parse_args()


def read_series_info(series_dir: Path) -> Dict[str, str]:
    info_path = series_dir / "series.info.txt"
    info: Dict[str, str] = {}
    if not info_path.exists():
        return info
    for line in info_path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        info[key.strip()] = value.strip()
    return info


def build_manifest(root: Path, viewer_dir: Path, max_frames: Optional[int], thumb_width: int, thumb_quality: int) -> Dict[str, List[Dict]]:
    html_base = viewer_dir.resolve()
    series_data: List[Dict] = []
    for surgery in sorted(p for p in root.iterdir() if p.is_dir()):
        for modality in sorted(p for p in surgery.iterdir() if p.is_dir()):
            for series in sorted(
                p for p in modality.iterdir() if p.is_dir() and p.name != "dcm"
            ):
                frames = sorted(series.glob("frame_*.png"))
                if not frames:
                    continue
                if max_frames and max_frames > 0:
                    selected = frames[:max_frames]
                else:
                    selected = frames
                rel_frames = [
                    os.path.relpath(
                        str(create_thumbnail(frame, root, viewer_dir, series, thumb_width, thumb_quality)),
                        str(html_base),
                    )
                    for frame in selected
                ]
                info = read_series_info(series)
                info_text = ", ".join(f"{k}: {v}" for k, v in info.items() if v)
                preview_index = 0
                if len(frames) > 2:
                    preview_index = len(frames) // 2
                elif len(frames) == 2:
                    preview_index = 0
                info = read_series_info(series)
                info_text = ", ".join(f"{k}: {v}" for k, v in info.items() if v)
                record = {
                    "surgery": surgery.name,
                    "modality": modality.name,
                    "series": series.name,
                    "frame_count": len(frames),
                    "type": "animation" if len(frames) > 1 else "still",
                    "frames": rel_frames,
                    "info_text": info_text,
                    "preview": rel_frames[preview_index] if rel_frames else "",
                    "preview_index": preview_index,
                }
                series_data.append(record)
    return {
        "root": str(root.resolve()),
        "generated": datetime.utcnow().isoformat() + "Z",
        "series": series_data,
    }


def create_thumbnail(frame: Path, root: Path, viewer_dir: Path, series: Path, width: int, quality: int) -> Path:
    rel_series = series.relative_to(root)
    thumb_dir = viewer_dir / "thumbnails" / rel_series
    thumb_dir.mkdir(parents=True, exist_ok=True)
    dest = thumb_dir / f"{frame.stem}.jpg"
    if not dest.exists() or dest.stat().st_mtime < frame.stat().st_mtime:
        with Image.open(frame) as img:
            img = img.convert("RGB")
            max_dim = 65500
            scale = min(
                1.0,
                width / img.width if img.width else 1.0,
                max_dim / img.height if img.height else 1.0,
            )
            if scale < 1.0:
                new_width = max(1, int(img.width * scale))
                new_height = max(1, int(img.height * scale))
                img = img.resize((new_width, new_height), Image.LANCZOS)
            img.save(dest, format="JPEG", quality=quality, optimize=True, progressive=True)
    return dest


def main() -> None:
    args = parse_args()
    if not args.root.is_dir():
        raise SystemExit(f"{args.root} does not exist or is not a directory.")
    args.viewer.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(args.root, args.viewer, args.max_frames, args.thumb_width, args.thumb_quality)
    manifest_path = args.viewer / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    index_path = args.viewer / "index.html"
    index_path.write_text(HTML_TEMPLATE, encoding="utf-8")
    print(f"Viewer ready at {index_path.resolve()} (open in browser).")


if __name__ == "__main__":
    main()
