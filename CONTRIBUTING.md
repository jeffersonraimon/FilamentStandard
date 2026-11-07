# Contributing

Thanks for helping! Issues and pull requests are welcome in English or Portuguese.

## Ground rules
- The plugin must stay a **single file** (`filament_standard.py`) with **no third-party dependencies**: Orca Cloud distributes single `.py` files, and a declared dependency makes OrcaSlicer run `uv pip install` on every activation.
- Everything that does not need OrcaSlicer lives in plain functions at module level, so it can be tested without the host.
- Every user-visible string goes in `STRINGS` in **both** languages. `tests/test_core.py` checks that the keys and placeholders match and that the page uses only known keys.
- The helper must never write `OrcaSlicer.conf` while OrcaSlicer is running: OrcaSlicer would overwrite the file when it exits.

## Setup
```bash
python -m pip install pytest ruff
python -m pytest
python -m ruff check .
```

## Testing in OrcaSlicer
1. Install the file with **Plugins → Install local plugin**.
2. After editing it, reinstall it or restart OrcaSlicer.
3. Python tracebacks appear in OrcaSlicer's log, under the `log/` folder of the data directory.

## Releasing
1. Bump `VERSION` and the `# version =` header line. The test suite checks that they match.
2. Add the changes to `CHANGELOG.md`.
3. Publish a GitHub release `vX.Y.Z` (`gh release create`). The `publish-orcacloud.yml` workflow tests the code, attaches both editions and uploads the cloud edition to Orca Cloud.
4. See [docs/PUBLISHING.md](docs/PUBLISHING.md) for the Orca Cloud setup.
