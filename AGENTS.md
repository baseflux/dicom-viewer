# Repository Guidelines

## Project Structure & Module Organization
- Keep production code inside `src/` or the `dicom/` package so imports stay predictable; drop-in modules belong beside the package `__init__.py`.
- Place isolated units and fixtures under `tests/unit/`, wider flows under `tests/integration/`, and reusable assets (schemas, sample data, regulatory notes) in `assets/` or `resources/`.
- Configuration templates (`configs/`, `.env.example`) document the runtime variables; refer to them before introducing new CLI flags or environment variables.

## Build, Test, and Development Commands
- `pip install -r requirements.txt` – mirrors what CI installs and should be rerun after dependency changes.
- `python -m pytest tests/` – executes every test, including parametrized flows; add `-k <name>` for focused runs.
- `pytest --cov=dicom tests/` – verifies coverage for the core package; keep the total above the project’s existing baseline.
- `ruff check src tests` and `black --check src tests` – enforce linting/formatting rules before merging; run `pre-commit run --all-files` when updating hooks.
- `python -m build` (or `make build` if present) – packages the project for release; update `pyproject.toml` accordingly when adding metadata.
- `python3 organize_dicoms.py --input DICOM --output dicom_01 [--copy-dicom]` – reads metadata to split the shoulder and ankle surgeries, creates modality folders (XRAY/CT/MRI/…), and emits numbered PNG frames for each series so playback tools can consume them.
- `python3 build_quickviewer.py --root dicom_01 --viewer viewer [--max-frames 0]` – scans the organized tree, tags every series as a still or animation, writes `viewer/manifest.json`, and drops a `viewer/index.html` you can open locally to preview the data (pass `--max-frames 0` to reference every exported frame instead of the default nine).
  - `python3 sync_viewer_to_docs.py --viewer viewer --docs docs [--clean]` – copies the latest viewer output into `docs/`, purging it first if you pass `--clean`, so GitHub Pages (pointed at `docs/`) serves the viewer exactly as generated.
  - `python3 prune_docs_thumbnails.py --docs docs --sample-rate 2` – after syncing, remove every-others thumbnail from animation series and rewrite `docs/manifest.json` so the Pages site only loads the kept frames.

## GitHub Pages Deployment
- After generating or updating the viewer (`build_quickviewer.py`), run `sync_viewer_to_docs.py` and commit the refreshed `docs/` folder.
- Optionally run `prune_docs_thumbnails.py` after the sync step to reduce the number of thumbnails uploaded for GitHub Pages (keep every 2nd frame for animations, keep all stills).
- In the repository’s settings enable GitHub Pages and point it at the `docs/` folder (default or `gh-pages` branch); GitHub will serve `docs/index.html` at `https://<user>.github.io/<repo>/`.
- Repeat the build + sync workflow whenever the organized DICOM data changes so the published viewer and manifest stay in sync.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation, explicit imports, and single quotes for strings unless escaping requires double quotes.
- Prefer descriptive names: modules and functions in `snake_case`, classes in `PascalCase`, constants in `UPPER_SNAKE_CASE`.
- Keep public APIs documented via inline docstrings, and annotate public functions with type hints; run `ruff` to catch unused imports and type issues.
- Commit formatting edits through `black`; stray formatting changes should land in their own commits.

## Testing Guidelines
- Name test files `tests/<layer>/test_<feature>.py` and classes `Test<Feature>`.
- Fixtures live alongside the tests they support; reuse shared fixtures from `tests/conftest.py`.
- Target deterministic tests: seed randomness if needed and pin timeouts in `pytest.ini`.
- Record test failures with reproduction steps in issues before attempting fixes.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `chore:`, etc.) so changelog automation stays reliable; include scope when it clarifies the surface area.
- Open PRs with a descriptive summary, testing checklist, and linked issue/bug report; capture screenshots when a UI change is involved.
- Tag reviewers explicitly in the PR description and ensure CI-green status before merging.

## Security & Configuration Tips
- Never check secrets into the repo; keep credentials in `secrets/` vaults and reference them via `.env`.
- Document any third-party service keys or scopes you need in `SECURITY.md` or a shared ops note.
