"""The release builder used by CI (scripts/build_release.py)."""
import importlib.util
import os
import re

import pytest

from conftest import ROOT


@pytest.fixture(scope="module")
def build_release():
    spec = importlib.util.spec_from_file_location("build_release", os.path.join(ROOT, "scripts", "build_release.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def current_version():
    with open(os.path.join(ROOT, "filament_standard.py"), encoding="utf-8") as stream:
        return re.search(r'^VERSION = "([^"]+)"', stream.read(), re.M).group(1)


def test_build_current_version(build_release, tmp_path):
    version = current_version()
    notes = build_release.build("v" + version, str(tmp_path))
    assert sorted(os.listdir(tmp_path)) == ["filament_standard.py", "filament_standard_any.py", "notes.md"]
    cloud = (tmp_path / "filament_standard_any.py").read_text(encoding="utf-8")
    full = (tmp_path / "filament_standard.py").read_text(encoding="utf-8")
    assert 'EDITION = "cloud"' in cloud and "OrcaSlicer.conf" not in cloud
    assert 'EDITION = "full"' in full and "def restore(" in full and "full-edition" not in full
    assert "## Install" in notes and "filament_standard.py" in notes and "Orca Cloud" in notes
    assert "## [" not in notes  # only this version's section


def test_orca_cloud_file_name_has_a_target_suffix(build_release):
    # Orca Cloud: <name>_<target>.py with target in the documented list
    targets = ("macosx_arm64", "macosx_x86_64", "macosx_universal", "macosx", "linux", "linux_arm64",
               "linux_x86_64", "win_arm64", "win_x86_64", "win", "any")
    stem = build_release.ORCA_CLOUD_NAME[:-3]
    assert any(stem.endswith("_" + t) for t in targets)


def test_build_rejects_wrong_tag(build_release, tmp_path):
    with pytest.raises(SystemExit):
        build_release.build("v0.0.1", str(tmp_path))


def test_changelog_section(build_release):
    text = "# Log\n\n## [1.1.0] - x\n- new\n\n## [1.0.0] - y\n- old\n"
    assert build_release.changelog_section(text, "1.1.0") == "- new\n"
    assert build_release.changelog_section(text, "1.0.0") == "- old\n"
    with pytest.raises(SystemExit):
        build_release.changelog_section(text, "2.0.0")


def test_every_version_has_a_changelog_entry(build_release):
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as stream:
        assert build_release.changelog_section(stream.read(), current_version()).strip()


def test_cli_prints_non_ascii_notes_on_a_legacy_console(tmp_path):
    """CI on Windows uses cp1252 for stdout; the notes contain characters such as "→"."""
    import subprocess
    import sys
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_release.py"), "v" + current_version()],
                          capture_output=True, env=env, cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
