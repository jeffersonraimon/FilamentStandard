"""Build the release files: dist/filament_standard_any.py, dist/filament_standard.py and dist/notes.md.

Usage: python scripts/build_release.py v2.1.1

* checks that the tag matches VERSION and the "# version =" header of the plugin;
* copies the plugin under the Orca Cloud name (``_any`` = every OS/architecture) and the plain name;
* writes the CHANGELOG section of that version, plus install instructions, as the release notes.
"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "filament_standard.py")
ORCA_CLOUD_NAME = "filament_standard_any.py"

INSTALL = """
## Install
- **Orca Cloud:** subscribe to *FilamentStandard* in OrcaSlicer's plugin browser.
- **Manual:** download `filament_standard_any.py` below and use OrcaSlicer 2.5+ **Plugins > Install local plugin**.

[README](https://github.com/jeffersonraimon/FilamentStandard#readme) · [Português](https://github.com/jeffersonraimon/FilamentStandard/blob/main/README.pt-BR.md)
"""


def plugin_versions(text):
    constant = re.search(r'^VERSION = "([^"]+)"', text, re.M)
    header = re.search(r'^# version = "([^"]+)"', text, re.M)
    return (constant.group(1) if constant else ""), (header.group(1) if header else "")


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
    shutil.copyfile(PLUGIN, os.path.join(out_dir, ORCA_CLOUD_NAME))
    shutil.copyfile(PLUGIN, os.path.join(out_dir, "filament_standard.py"))
    with open(os.path.join(out_dir, "notes.md"), "w", encoding="utf-8", newline="\n") as stream:
        stream.write(notes)
    return notes


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(build(sys.argv[1], os.path.join(ROOT, "dist")))
