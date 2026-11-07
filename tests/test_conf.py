import json
import os

import pytest

from conftest import sample_conf


def test_flush_volume_matches_orcaslicer(fs):
    # values OrcaSlicer 2.5 writes for the A1 minus its minimum purge (48 mm³ there)
    assert fs.flush_volume("#FFFFFF", "#000000") == pytest.approx(80, abs=0.01)
    assert fs.flush_volume("#000000", "#FFFFFF") == pytest.approx(560, abs=0.01)
    assert int(fs.flush_volume("#FF0000", "#FF0000")) == 60  # floor


def test_flush_matrix_shape(fs):
    colors = ["#FFFFFF", "#000000", "#FF0000"]
    values = fs.flush_matrix(colors).split("|")
    assert len(values) == 9
    assert values[0] == values[4] == values[8] == "0.000000"
    # OrcaSlicer truncates the volume to int before adding the minimum purge
    assert float(values[1]) in (79 + fs.FLUSH_OFFSET, 80 + fs.FLUSH_OFFSET)
    assert float(values[3]) in (559 + fs.FLUSH_OFFSET, 560 + fs.FLUSH_OFFSET)
    assert all(float(v) <= fs.FLUSH_MAX for v in values)
    assert len(fs.flush_matrix(colors, extruders=2).split("|")) == 18


def test_conf_round_trip_and_checksum(fs, tmp_path):
    path = tmp_path / "OrcaSlicer.conf"
    conf = sample_conf()
    conf["app"]["name"] = "Cópia ✓"  # non-ASCII stays raw UTF-8 like OrcaSlicer writes it
    fs.write_conf(str(path), conf)
    assert fs.verify_conf(str(path))
    assert fs.read_conf(str(path)) == conf
    raw = path.read_bytes()
    assert "Cópia ✓".encode("utf-8") in raw
    text, md5 = fs.dump_conf(conf)
    assert raw.rstrip().endswith(("# MD5 checksum " + md5).encode())


def test_verify_detects_tampering(fs, tmp_path):
    path = tmp_path / "OrcaSlicer.conf"
    fs.write_conf(str(path), sample_conf())
    path.write_bytes(path.read_bytes().replace(b"Generic PETG", b"Generic PETX"))
    assert not fs.verify_conf(str(path))


def test_read_conf_without_checksum(fs, tmp_path):
    path = tmp_path / "OrcaSlicer.conf"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError):
        fs.read_conf(str(path))


def test_apply_lists(fs, standard):
    conf = sample_conf()
    changed, missing = fs.apply_lists(conf, standard)
    assert changed == ["Bambu Lab A1 0.4 nozzle", "Bambu Lab A1 0.2 nozzle", "Bambu Lab H2D 0.4 nozzle"]
    assert missing == ["Never Used Printer 0.6 nozzle"]
    a1, a1_02, h2d, x1 = conf["orca_presets"]
    assert fs.entry_filaments(a1) == ["PLA A", "PLA B", "PETG C"]
    assert fs.entry_filaments(a1_02) == ["PLA A 0.2", "PLA B 0.2", "PETG C"]  # no 0.2 variant -> default
    assert a1["filament_colors"] == a1["filament_multi_colors"] == "#FFFFFF,#000000,#FF0000"
    assert a1["filament_color_types"] == "1,1,1"
    assert len(a1["flush_volumes_matrix"].split("|")) == 9
    assert a1["flush_volumes_vector"].count("|") == 5  # 2 values per filament, as before
    assert a1["filament_is_mixed"] == "0,0,0"
    assert a1["filament_mixed_components"] == "||"
    assert a1["filament_self_index"] == "1,2,1"  # unknown per-slot list resized
    assert a1["process"] == "0.20mm Standard @BBL A1"  # unrelated keys untouched
    assert len(h2d["flush_volumes_matrix"].split("|")) == 18  # two extruders keep two matrices
    assert x1 == sample_conf()["orca_presets"][3]  # not selected -> untouched


def test_apply_lists_shrinks(fs, standard):
    conf = sample_conf()
    standard["slots"] = standard["slots"][:1]
    fs.apply_lists(conf, standard)
    a1 = conf["orca_presets"][0]
    assert fs.entry_filaments(a1) == ["PLA A"]
    assert "filament_01" not in a1
    assert a1["flush_volumes_matrix"] == "0.000000"


def test_apply_lists_empty(fs):
    with pytest.raises(RuntimeError):
        fs.apply_lists(sample_conf(), fs.empty_standard())


def test_apply_prices(fs, data_dir):
    fdir = data_dir / "user" / "uid123" / "filament"
    done = fs.apply_prices(str(fdir), {"PLA A": 120, "PLA A 0.2": 120, "PETG C": 80, "Missing": 10}, "uid123")
    assert done == [("PLA A", "100", "120.00"), ("PLA A 0.2", "", "120.00")]  # PETG C unchanged, Missing skipped
    data = json.loads((fdir / "PLA A.json").read_text(encoding="utf-8"))
    assert data["filament_cost"] == ["120.00"]
    info = (fdir / "PLA A.info").read_text(encoding="utf-8")
    assert "sync_info = update" in info and "setting_id = abc" in info and "base_id = GFSL" in info
    new_info = (fdir / "PLA A 0.2.info").read_text(encoding="utf-8")
    assert "sync_info = create" in new_info and "user_id = uid123" in new_info


def test_restore_end_to_end(fs, data_dir, standard):
    logs = []
    changed, missing, backup = fs.restore(str(data_dir), standard, logs.append)
    assert len(changed) == 3 and missing
    conf_path = data_dir / "OrcaSlicer.conf"
    assert fs.verify_conf(str(conf_path))
    conf = fs.read_conf(str(conf_path))
    assert fs.entry_filaments(conf["orca_presets"][0]) == ["PLA A", "PLA B", "PETG C"]
    # everything outside the selected orca_presets entries is untouched
    original = sample_conf()
    assert {k: v for k, v in conf.items() if k != "orca_presets"} == {k: v for k, v in original.items() if k != "orca_presets"}
    # the backup holds only the entries that changed, never the whole file
    assert sorted(os.listdir(backup)) == ["filament", "orca_presets.json"]
    saved = fs.read_json(os.path.join(backup, "orca_presets.json"))
    assert [e["machine"] for e in saved["orca_presets"]] == changed
    assert saved["orca_presets"][0] == original["orca_presets"][0]
    assert sorted(os.listdir(os.path.join(backup, "filament"))) == ["PETG C.json", "PLA A 0.2.json", "PLA A.info", "PLA A.json"]
    assert any("price PLA A: 100 -> 120.00" in line for line in logs)
    assert any("skipped" in line for line in logs)


def test_restore_never_copies_or_logs_secrets(fs, data_dir, standard):
    logs = []
    _, _, backup = fs.restore(str(data_dir), standard, logs.append)
    for folder, _, files in os.walk(backup):
        for name in files:
            with open(os.path.join(folder, name), encoding="utf-8", errors="ignore") as stream:
                assert "SECRET" not in stream.read(), name
    assert not any("SECRET" in line for line in logs)
    conf = fs.read_conf(str(data_dir / "OrcaSlicer.conf"))
    assert conf["access_code"] == {"PRINTER-SERIAL": "SECRET-ACCESS-CODE"}


def test_undo(fs, data_dir, standard):
    fdir = data_dir / "user" / "uid123" / "filament"
    _, _, backup = fs.restore(str(data_dir), standard, lambda *_: None)
    assert fs.read_conf(str(data_dir / "OrcaSlicer.conf")) != sample_conf()
    fs.undo(str(data_dir), backup, lambda *_: None)
    assert fs.read_conf(str(data_dir / "OrcaSlicer.conf")) == sample_conf()
    assert json.loads((fdir / "PLA A.json").read_text(encoding="utf-8"))["filament_cost"] == ["100"]
    assert fs.verify_conf(str(data_dir / "OrcaSlicer.conf"))
    with pytest.raises(RuntimeError):
        fs.undo(str(data_dir), str(data_dir), lambda *_: None)
