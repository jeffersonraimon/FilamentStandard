<p align="center"><img src="assets/icon.svg" width="160" alt="FilamentStandard"></p>

# FilamentStandard

**Keep one standard filament list for your printers in OrcaSlicer: same order, same colours and the right preset for each nozzle. Restore the list after opening someone else's project, and sync spools and prices from [Spoolman](https://github.com/Donkie/Spoolman).**

[Leia em português](README.pt-BR.md)

[![CI](https://github.com/jeffersonraimon/FilamentStandard/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jeffersonraimon/FilamentStandard/actions/workflows/ci.yml)

> An OrcaSlicer **2.5+** Python plugin. It is a single file, `filament_standard.py`, and has no dependencies.

## Why

OrcaSlicer keeps one filament list per printer profile, in `orca_presets` inside `OrcaSlicer.conf`. Two things break that list:

- Every profile has its own list, so when you switch from the 0.4 to the 0.2 nozzle the slots no longer line up and the colours change places.
- Opening a `.3mf` project replaces the list of the active profile with the project's filaments. Filaments you don't have become "Generic PLA" or "Bambu PLA Basic", and the next *New project* keeps that list.

FilamentStandard keeps one standard list: slot → filament preset per nozzle diameter, colour and Spoolman spool. It puts that list back whenever you want.

## Features

| | |
|---|---|
| **Standard list editor** | A tab with one row per slot: colour, the preset for each nozzle diameter (the *default* column is used when a nozzle has no preset of its own), the Spoolman spool, and what the current project has in that slot. |
| **Use current list as standard** | Captures the slots and colours of the open project. Spools are kept by matching preset and colour. |
| **Restore presets now** | Re-assigns the preset of every existing slot live, through the plugin API. |
| **Full restore on close** | A small helper waits for OrcaSlicer to close, then does everything the API can't: it writes the list (presets, colours, flush matrix) into **every selected printer profile** and writes the prices into your filament presets. It backs everything up first and can reopen OrcaSlicer. |
| **Spoolman sync** *(optional)* | Previews new and removed spools, colour changes and the average price per kg of each preset, then applies them only when you confirm. Spools of an unknown filament ask for a preset once and remember it. |
| **Restore on New project** *(optional, off by default)* | Re-assigns the presets whenever a new project starts. |
| **Any printer** | Bambu Lab, Prusa, Creality, Voron/Klipper and others. Presets are chosen per nozzle diameter, and multi-extruder printers keep one flush matrix per extruder. |
| **English / Português** | Follows OrcaSlicer's language, or can be set in Settings. |
| **Import / export** | Copy the standard as JSON to share it or keep it under version control. |

### What the plugin API can and can't do

The OrcaSlicer 2.5 plugin API can assign a preset to an **existing** slot (`orca.host.preset.filament.begin_update`). It can't add or remove slots, and it can't set a slot's colour. That is why the **full restore** exists: it edits `OrcaSlicer.conf` while OrcaSlicer is closed, the same way OrcaSlicer itself writes it, MD5 checksum included.

## Install

1. Download [`filament_standard.py`](https://github.com/jeffersonraimon/FilamentStandard/releases/latest), or subscribe to **FilamentStandard** on Orca Cloud once it's listed.
2. In OrcaSlicer open **Plugins** → *More plugin install options* → **Install local plugin** and pick the file.
3. Accept the permission prompts:
   - **threads**: for the live restore;
   - **network**: only for the Spoolman host you configure;
   - **launch a program**: for the full-restore helper.
4. A new **FilamentStandard** tab appears.

**Requirement for the full restore:** a Python 3 interpreter on `PATH`, because the helper runs outside OrcaSlicer:

| System | Interpreter used |
|---|---|
| Windows | `pythonw`, `pyw`, `python` or `py` |
| macOS / Linux | `python3` |

Everything else runs inside OrcaSlicer's bundled Python.

## Quick start

1. Set up the filaments and colours you want in a project, the way you like them ordered.
2. **Use current list as standard**.
3. Under **Printer profiles**, tick every printer or nozzle profile that should share the list. The nozzle diameter is read from the profile. Fill the `0.2 mm` (or other) column for filaments that have a nozzle-specific preset.
4. **Save standard**.
5. Whenever a project messes the list up:
   - **Restore presets now** fixes the presets of the existing slots;
   - **Full restore on close**, then close OrcaSlicer, fixes everything, colours and slot count included.

### Spoolman

Under **Settings**, set the Spoolman URL, for example `http://192.168.1.10:7912`, then use **Sync with Spoolman**.

- Each spool is matched to a slot by its ID, shown in the *Spool* column.
- When **sort on sync** is on, the list is ordered PLA white, PLA black, other PLA by brand, then PETG white, PETG black, other PETG, then other materials.
- Prices are the average `price / initial weight` of the active spools of each preset. They are written to the preset's *filament cost* on the next full restore.

## Where things are stored

| What | Where |
|---|---|
| Standard list and settings | `<OrcaSlicer data dir>/orca_plugins/plugin_data/<plugin>/standard.json` |
| Pending full restore | `job.json` in the same folder |
| Helper log | `apply.log` in the same folder |
| Backups (one per full restore) | `<OrcaSlicer data dir>/backup-filament-standard-<date>/`, with `OrcaSlicer.conf` and the filament presets |

The OrcaSlicer data dir is `%APPDATA%\OrcaSlicer` on Windows, `~/Library/Application Support/OrcaSlicer` on macOS and `~/.config/OrcaSlicer` on Linux.

### Command line

With OrcaSlicer closed, the same file restores a standard without the GUI:

```bash
python filament_standard.py --restore "<OrcaSlicer data dir>" standard.json
```

## How it works

- **Live restore:** for each slot whose preset differs, it calls `orca.host.preset.filament.begin_update(slot, preset).commit()` from a worker thread, as the API requires.
- **Full restore:**
  - writes `job.json` and starts `python filament_standard.py --apply job.json` detached;
  - the helper polls until no OrcaSlicer process is left and reads the **latest** `standard.json`;
  - for every selected printer profile it rewrites the `filament`, `filament_NN`, `filament_colors`, `filament_multi_colors`, `filament_color_types` and per-slot keys, and the flush matrix and vector;
  - it re-serialises the file exactly like OrcaSlicer (tab indentation, raw UTF-8, `# MD5 checksum` of the LF text).
- **Flush volumes:** a Python port of OrcaSlicer's colour-based `FlushVolCalc` plus a minimum purge of 92 mm³. You can always press *Recalculate* in OrcaSlicer's flushing-volumes dialog.
- **Prices:** written to `filament_cost` in `user/<id>/filament/<preset>.json`. The `.info` file is marked `sync_info = update` so OrcaSlicer uploads the change if you use cloud sync.

## Development

```bash
python -m pip install pytest ruff
python -m pytest          # unit and integration tests, including a fake OrcaSlicer host
python -m ruff check .
```

- **CI:** runs on Windows, macOS and Linux with Python 3.10–3.13.
- **Releases:** pushing a tag `vX.Y.Z` that matches `VERSION` attaches `filament_standard.py` to a GitHub release.
- **Contributing:** see [CONTRIBUTING.md](CONTRIBUTING.md).
- **Orca Cloud:** see [docs/PUBLISHING.md](docs/PUBLISHING.md).

## License

[MIT](LICENSE) © Jefferson J. Raimon
