# Changelog

All notable changes to this project are documented here. Versions follow [Semantic Versioning](https://semver.org/).

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
