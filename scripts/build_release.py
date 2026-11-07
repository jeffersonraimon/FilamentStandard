"""Build the release files from filament_standard.py.

Usage: python scripts/build_release.py v3.0.0

* checks that the tag matches VERSION and the "# version =" header of the plugin;
* writes ``dist/filament_standard_any.py``, the **cloud edition** for Orca Cloud. Its name ends in
  ``_any`` (every OS/architecture), as Orca Cloud requires. Every block between
  ``>>> full-edition`` and ``<<< full-edition`` is removed, so the file uses only the plugin API
  and its own storage folder;
* writes ``dist/filament_standard.py``, the **full edition** (GitHub), with the markers removed;
* writes the CHANGELOG section of that version, plus install notes, to ``dist/notes.md``.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "filament_standard.py")
ORCA_CLOUD_NAME = "filament_standard_any.py"
FULL_NAME = "filament_standard.py"
BEGIN, END = ">>> full-edition", "<<< full-edition"

INSTALL = """
## Install
- **Orca Cloud:** subscribe to *FilamentStandard* in OrcaSlicer's plugin browser (cloud edition: live restore, prices and Spoolman through the plugin API).
- **Full edition:** download `filament_standard.py` below and use OrcaSlicer 2.5+ **Plugins > Install local plugin**. It adds the opt-in full restore that edits `OrcaSlicer.conf` (slot count and colours).

[README](https://github.com/jeffersonraimon/FilamentStandard#readme) · [Português](https://github.com/jeffersonraimon/FilamentStandard/blob/main/README.pt-BR.md)
"""


def plugin_versions(text):
    constant = re.search(r'^VERSION = "([^"]+)"', text, re.M)
    header = re.search(r'^# version = "([^"]+)"', text, re.M)
    return (constant.group(1) if constant else ""), (header.group(1) if header else "")


def make_edition(source, edition):
    """Return the source of one edition: 'cloud' drops the full-edition blocks, 'full' keeps them."""
    out, depth = [], 0
    for number, line in enumerate(source.split("\n"), 1):
        if BEGIN in line:
            depth += 1
            if depth > 1:
                raise SystemExit("nested %s at line %d" % (BEGIN, number))
            continue
        if END in line:
            if depth == 0:
                raise SystemExit("unmatched %s at line %d" % (END, number))
            depth -= 1
            continue
        if depth and edition == "cloud":
            continue
        out.append(line)
    if depth:
        raise SystemExit("unterminated %s" % BEGIN)
    text = "\n".join(out)
    text, n = re.subn(r'^EDITION = "full"$', 'EDITION = "%s"' % edition, text, count=1, flags=re.M)
    if n != 1:
        raise SystemExit('EDITION = "full" not found')
    return text


def changelog_section(changelog, version):
    match = re.search(r"^## \[%s\][^\n]*\n(.*?)(?=^## \[|\Z)" % re.escape(version), changelog, re.M | re.S)
    if not match:
        raise SystemExit("CHANGELOG.md has no section for %s" % version)
    return match.group(1).strip() + "\n"


def build(tag, out_dir):
    version = tag[1:] if tag.startswith("v") else tag
    with open(PLUGIN, encoding="utf-8") as stream:
        source = stream.read()
    constant, header = plugin_versions(source)
    if not (constant == header == version):
        raise SystemExit("tag %s does not match VERSION %s / header %s" % (tag, constant, header))
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as stream:
        notes = changelog_section(stream.read(), version) + INSTALL
    os.makedirs(out_dir, exist_ok=True)
    for name, edition in ((ORCA_CLOUD_NAME, "cloud"), (FULL_NAME, "full")):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as stream:
            stream.write(make_edition(source, edition))
    with open(os.path.join(out_dir, "notes.md"), "w", encoding="utf-8", newline="\n") as stream:
        stream.write(notes)
    return notes


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(build(sys.argv[1], os.path.join(ROOT, "dist")))
