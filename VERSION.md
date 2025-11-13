Current snapshot: clean viewer structure with animation/still cards and RGB thumbnails.
Timestamp: 2025-11-12T06:20:00Z

Rebuild steps to return:
1. `python3 organize_dicoms.py --input DICOM --output dicom_01`
2. `python3 build_quickviewer.py --root dicom_01 --viewer viewer`
3. `python3 sync_viewer_to_docs.py --viewer viewer --docs docs --clean`
4. `python3 prune_docs_thumbnails.py --docs docs --sample-rate 1`
5. `git add viewer docs build_quickviewer.py build_quickviewer.py`
6. `git commit -m "Rebuild viewer snapshot"`
7. `git push`
