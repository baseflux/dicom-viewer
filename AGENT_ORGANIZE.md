# OrganizeDICOM Agent

This agent automates the reorganization of the macOS DICOM folder into surgery/modality trees and exports PNG frames for each series so playback tooling can loop through ordered samples.

## Setup
1. Ensure dependencies are installed in your Python 3 environment: `pip install numpy pillow pydicom pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg`.  
2. At minimum install `numpy` (`pip install numpy`) before running the script; the others are required for pixel decoding.

## Task
Run the agent from the repository root:

```
python3 organize_dicoms.py --input DICOM --output dicom_01 [--copy-dicom]
```

• `--copy-dicom` places the original `.dcm` files under each `dcm/` subfolder next to the exported PNGs.  
• Provide `--shoulder-from/--shoulder-to` and `--ankle-from/--ankle-to` if you want date-based filtering; otherwise keyword heuristics are used.

## Output
- Two top-level folders `01_surg_shoulder` and `02_surg_ankle` (plus `_unsorted` for anything unmatched).  
- Within each, modality buckets like `XRAY`, `CT`, and `MRI`.  
- Each series folder contains sequential `frame_XXXX.png` images ready for looped playback and a `series.info.txt` summary of metadata.
