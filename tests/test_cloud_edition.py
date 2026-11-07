"""The Orca Cloud edition: built by stripping the full-edition blocks, it must use only the plugin API
and its own storage folder (Orca Cloud's review rejects reading OrcaSlicer.conf or user preset files)."""
import importlib.util
import os
import re
import sys

import pytest

from conftest import ROOT, FakeHost, make_fake_orca, spool


@pytest.fixture(scope="module")
def build_release():
    spec = importlib.util.spec_from_file_location("build_release_c", os.path.join(ROOT, "scripts", "build_release.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cloud_source(build_release):
    with open(os.path.join(ROOT, "filament_standard.py"), encoding="utf-8") as stream:
        return build_release.make_edition(stream.read(), "cloud")


@pytest.mark.parametrize("token", [
    "OrcaSlicer.conf", "read_conf", "write_conf", "orca_presets", "subprocess", "shutil", "Popen",
    "os.walk", "listdir", "filament_dir", "preset_folder", "find_previous", "restore_full", "--apply",
    "full-edition", "APPIMAGE", "sys.executable",
])
def test_cloud_edition_has_no_local_file_or_process_access(cloud_source, token):
    assert token not in cloud_source


def test_cloud_edition_compiles_and_is_marked(cloud_source):
    compile(cloud_source, "filament_standard_any.py", "exec")
    assert re.search(r'^EDITION = "cloud"$', cloud_source, re.M)
    assert '# name = "FilamentStandard"' in cloud_source


def test_full_edition_keeps_everything(build_release):
    with open(os.path.join(ROOT, "filament_standard.py"), encoding="utf-8") as stream:
        source = stream.read()
    full = build_release.make_edition(source, "full")
    assert "full-edition" not in full
    assert "def restore(" in full and 'EDITION = "full"' in full
    assert len(full.splitlines()) == len(source.splitlines()) - source.count(">>> full-edition") * 2


def test_markers_are_balanced(build_release):
    with pytest.raises(SystemExit):
        build_release.make_edition('EDITION = "full"\n# >>> full-edition\nx = 1\n', "cloud")
    with pytest.raises(SystemExit):
        build_release.make_edition('EDITION = "full"\n# <<< full-edition\n', "cloud")
    with pytest.raises(SystemExit):
        build_release.make_edition('EDITION = "full"\n# >>> full-edition\n# >>> full-edition\n', "cloud")


@pytest.fixture
def cloud(tmp_path, cloud_source):
    path = tmp_path / "filament_standard_any.py"
    path.write_text(cloud_source, encoding="utf-8")
    storage = tmp_path / "orca_plugins" / "plugin_data" / "_subscribed" / "u" / "key"
    storage.mkdir(parents=True)
    host = FakeHost(str(storage))
    sys.modules["orca"] = make_fake_orca(host)
    try:
        spec = importlib.util.spec_from_file_location("filament_standard_cloud", str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop("orca", None)
    page = module.FilamentStandardPage()
    return module, page, host


def test_cloud_translations_match_the_page(cloud):
    module, page, host = cloud
    assert set(module.STRINGS["en"]) == set(module.STRINGS["pt"])
    keys = set(re.findall(r'data-i18n(?:-title)?="(\w+)"', module.PAGE)) | set(re.findall(r"\bt\('(\w+)'", module.PAGE))
    assert keys <= set(module.STRINGS["en"]), keys - set(module.STRINGS["en"])
    assert 'id="b-full"' not in module.PAGE and 'id="confedit"' not in module.PAGE  # no full-restore controls


def test_cloud_edition_works(cloud, monkeypatch):
    module, page, host = cloud
    module.FilamentStandardPlugin().register_capabilities()
    page.on_message({"cmd": "ready"})
    assert not page.messages[-1]["error"]
    host.slots = ["PLA A", "PLA B"]
    page.on_message({"cmd": "capture"})
    assert len(page.messages[-1]["std"]["slots"]) == 2
    host.slots = ["Generic PLA", "Generic PLA"]
    page.on_message({"cmd": "restore_live"})
    page.worker.join(5)
    assert host.slots == ["PLA A", "PLA B"]
    page.on_message({"cmd": "restore_full"})
    assert page.messages[-1]["error"] == "unknown command: restore_full"
    # settings save on a fresh install too (the 3.0.1 bug: an empty list blocked them)
    page.on_message({"cmd": "reset"})
    page.on_message({"cmd": "save_settings", "settings": {"language": "pt", "spoolman_url": "http://spoolman.local:7912"}})
    assert page.messages[-1]["lang"] == "pt" and not page.messages[-1]["error"]
    # Spoolman: asks before the first connection
    monkeypatch.setattr(module, "fetch_spools", lambda url: [spool(1, "Acme", "PLA Basic", "PLA", "FFFFFF", 100)])
    page.on_message({"cmd": "sync_preview"})
    assert page.messages[-1]["proposal"] is None and "Spoolman" in page.messages[-1]["error"]
    page.on_message({"cmd": "sync_preview", "consent": True})
    assert page.messages[-1]["proposal"] is not None
    assert module.main(["x", "--apply", "job.json"]) == 1  # no helper in the cloud edition
