# Changelog

All notable changes to this project are documented here. Versions follow [Semantic Versioning](https://semver.org/).

## [3.0.3] - 2026-11-07
### Added
- **Nozzle columns are filled from preset names:**
  - *Use current list as standard*, Spoolman sync and adding a printer fill an empty nozzle column when a matching preset exists, case-insensitive: "Multfila PLA 0.2" for "MULTFILA PLA", or "Generic PLA @BBL A1 0.2 nozzle" for "Generic PLA @BBL A1". Columns you already filled are never changed.
  - Capturing on a 0.2 printer finds the base preset for the default column ("Multfila PLA 0.2" → default "MULTFILA PLA").

### Changed
- An empty nozzle cell shows, in grey, the default preset it falls back to, with a tooltip that explains it.

## [3.0.2] - 2026-11-07
### Fixed
- **Settings on a fresh install:** with an empty list, changing the language or the Spoolman URL did nothing, and *Sync with Spoolman* cleared the URL and said it was not set. The settings were saved through *Save standard*, which refuses an empty list. They now save on their own, and syncing works with an empty list, which is a good way to build the list from Spoolman.
- **Unsaved edits:** changing a setting no longer discards edits to the list that you have not saved yet.

## [3.0.1] - 2026-11-07
### Changed
- Releases now go out through `.github/workflows/publish-orcacloud.yml`, which runs when a GitHub release is **published**. Orca Cloud accepts only the OIDC token of that connected release workflow. The workflow tests the code, builds both editions, attaches them to the release and uploads the cloud edition to Orca Cloud. `ci.yml` only runs the tests.

## [3.0.0] - 2026-11-07
Two editions are built from the same source.

### Editions
| Edition | File | Where | What it can do |
|---|---|---|---|
| **Cloud** | `filament_standard_any.py` | Orca Cloud | Uses only the plugin API and its own storage folder. It never reads `OrcaSlicer.conf` or user preset files and never starts programs. |
| **Full** | `filament_standard.py` | GitHub | Everything above, plus the opt-in full restore. |

`scripts/build_release.py` creates the cloud edition by removing the `>>> full-edition` blocks.

### Added
- **Apply prices to presets:** writes each preset's price per kg through the plugin API, as an unsaved edit you then save in OrcaSlicer. Available in both editions.
- **Spoolman consent:** the plugin asks before the first connection to a Spoolman host and connects only to the host you confirmed. The network permission is requested for that host only.

### Changed
- The cloud edition has no first-run import from other installs, because that reads files outside the plugin's own folder.
- The cloud edition's tab hides the full-restore controls.

## [2.2.0] - 2026-11-07
### Security and privacy
- The full restore is **off by default**. It has to be enabled under *Full restore*, which explains what it changes, and it asks for confirmation each time.
- The full restore changes only the `orca_presets` entries of the selected printers. Other keys of `OrcaSlicer.conf`, such as printer access codes, are written back unchanged and are never copied or logged.
- Backups hold only the entries that change (`orca_presets.json`) and the filament presets whose price changes, no longer a copy of the whole `OrcaSlicer.conf`.
- The first-run import reads only this plugin's own folders (`filamentos_padrao`, `filament_standard*`), never other plugins' data. It no longer carries over the Spoolman URL or the full-restore opt-in.

### Added
- `--undo <data dir> <backup folder>`: puts back what a full restore changed.

## [2.1.1] - 2026-11-07
### Changed
- Release file renamed to `filament_standard_any.py`: Orca Cloud requires a target suffix (`_any` = every OS and architecture). The plain `filament_standard.py` is still attached to GitHub releases.
- Releases publish to Orca Cloud from CI (GitHub OIDC, no secrets) once the repository is connected to the plugin.
- The first run reuses the standard of any other install of the plugin: a local install before subscribing on Orca Cloud, or the 1.x "Filamentos Padrão". Orca Cloud installs keep their data in a different folder.

## [2.1.0] - 2026-11-07
### Added
- Plugin icon: a 20 px tab icon in OrcaSlicer's style (embedded in the plugin) and the brand icon `assets/icon.svg` / `assets/icon-512.png` for the README and the Orca Cloud listing.

## [2.0.0] - 2026-11-07
First public release, as **FilamentStandard**.

### Added
- English and Portuguese interface: it follows OrcaSlicer's language, or can be set in Settings.
- Support for any printer: presets per nozzle diameter (a *default* column plus one column per diameter), and an explicit list of target printer profiles instead of a name regex.
- Multi-extruder printers keep one flush matrix per extruder.
- JSON import and export.
- *Add current printer* button and a printer filter.
- `--restore` command-line mode for restoring with OrcaSlicer closed.
- Automatic migration from the 1.x "Filamentos Padrão" storage.
- Test suite (86 tests, including a fake OrcaSlicer host) and CI on Windows, macOS and Linux.

### Changed
- Spoolman is optional and has no hard-coded host. The network permission is requested only for the configured URL.
- Sorting on sync groups by the brand Spoolman reports, and can be turned off.
- The full-restore helper runs on macOS and Linux (`python3`, `pgrep`) as well as Windows.

## [1.0.2] - 2026-11-07 (private, "Filamentos Padrão")
- The full-restore helper applies the latest saved standard instead of the snapshot taken when it was scheduled.

## [1.0.1] - 2026-11-07 (private)
- *Use current list as standard* keeps the Spoolman spool of each slot by matching preset and colour.

## [1.0.0] - 2026-11-07 (private)
- First version: standard list, live restore, full restore on close, Spoolman sync, auto-restore on New project.
