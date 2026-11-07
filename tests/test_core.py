import os
import re

import pytest


@pytest.mark.parametrize("value, expected", [
    ("#ffffff", "#FFFFFF"), ("000000", "#000000"), ("#12ab34FF", "#12AB34"), ("#abc", "#AABBCC"),
    ("", "#FFFFFF"), (None, "#FFFFFF"), ("zzzzzz", "#FFFFFF"),
])
def test_norm_color(fs, value, expected):
    assert fs.norm_color(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("0.4", "0.4"), ("0.40", "0.4"), ("0.2mm", "0.2"), (["0.6", "0.6"], "0.6"), ("0.4,0.4", "0.4"),
    ("1", "1"), ("", ""), (None, ""), ("abc", ""), ("0.25", "0.25"),
])
def test_norm_nozzle(fs, value, expected):
    assert fs.norm_nozzle(value) == expected


@pytest.mark.parametrize("name, expected", [
    ("Bambu Lab A1 0.2 nozzle - A1-SL", "0.2"), ("Bambu Lab H2D 0.4 nozzle", "0.4"),
    ("Voron 0.6mm nozzle", "0.6"), ("Prusa MK4", ""), ("KLIPPER - KAMP", ""),
])
def test_nozzle_from_name(fs, name, expected):
    assert fs.nozzle_from_name(name) == expected


def test_preset_for_falls_back_to_default(fs):
    slot = {"presets": {"default": "PLA", "0.2": "PLA 0.2"}}
    assert fs.preset_for(slot, "0.2") == "PLA 0.2"
    assert fs.preset_for(slot, "0.20") == "PLA 0.2"
    assert fs.preset_for(slot, "0.4") == "PLA"
    assert fs.preset_for(slot, "") == "PLA"
    assert fs.preset_for({"presets": {}}, "0.4") == ""
    assert fs.preset_for({}, "0.4") == ""


def test_variants_of(fs, standard):
    assert fs.variants_of(standard) == ["default", "0.2", "0.4", "0.6"]
    assert fs.variants_of(fs.empty_standard()) == ["default"]


def test_clean_standard_normalises(fs):
    std = fs.clean_standard({
        "slots": [
            {"presets": {"default": " PLA ", "0.2": ""}, "color": "fff", "spool": "7"},
            {"presets": {"0.2": "Only 0.2"}, "color": "#000000", "spool": "x"},
            {"presets": {}, "color": "#123456"},
            "garbage",
        ],
        "printers": ["Bambu Lab A1 0.2 nozzle", "Custom"],
        "language": "klingon", "auto_new_project": 1,
        "spool_map": {"A|B": {"0.2": "no default"}, "C|D": {"default": "X"}},
        "prices": {"X": "12.345", "Y": "abc"},
    })
    assert std["slots"] == [
        {"presets": {"default": "PLA"}, "color": "#FFFFFF", "spool": 7},
        {"presets": {"0.2": "Only 0.2", "default": "Only 0.2"}, "color": "#000000", "spool": None},
    ]
    assert std["printers"] == {"Bambu Lab A1 0.2 nozzle": "0.2", "Custom": ""}
    assert std["language"] == "auto"
    assert std["auto_new_project"] is True
    assert std["spool_map"] == {"C|D": {"default": "X"}}
    assert std["prices"] == {"X": 12.35}
    with pytest.raises(ValueError):
        fs.clean_standard([])


def test_clean_standard_is_idempotent(fs, standard):
    assert fs.clean_standard(standard) == standard


def test_migrate_legacy(fs):
    old = {
        "slots": [{"p04": "MULTFILA PLA", "p02": "Multfila PLA 0.2", "color": "#FFFFFF", "spool": 13},
                  {"p04": "ELEGOO PLA", "p02": "ELEGOO PLA", "color": "#09CE82", "spool": 7}],
        "spool_map": {"Multfila|PLA Basic": {"p04": "MULTFILA PLA", "p02": "Multfila PLA 0.2"}},
        "prices": {"MULTFILA PLA": 120.0},
        "spoolman_url": "http://spoolman:7912",
        "machine_regex": r"^(Bambu Lab )?A1 0\.\d",
        "auto_new_project": False, "relaunch": True,
    }
    printers = ["Bambu Lab A1 0.2 nozzle", "Bambu Lab A1 0.4 nozzle - A1-SL", "Bambu Lab A1 mini 0.4 nozzle",
                "Bambu Lab X1 Carbon 0.4 nozzle"]
    std = fs.migrate_legacy(old, printers)
    assert std["slots"][0]["presets"] == {"default": "MULTFILA PLA", "0.2": "Multfila PLA 0.2"}
    assert std["slots"][1]["presets"] == {"default": "ELEGOO PLA"}
    assert std["spool_map"]["Multfila|PLA Basic"] == {"default": "MULTFILA PLA", "0.2": "Multfila PLA 0.2"}
    assert std["printers"] == {"Bambu Lab A1 0.2 nozzle": "0.2", "Bambu Lab A1 0.4 nozzle - A1-SL": "0.4"}
    assert std["language"] == "pt"
    assert std["spoolman_url"] == "http://spoolman:7912"


def test_migrate_legacy_bad_regex(fs):
    std = fs.migrate_legacy({"slots": [{"p04": "A"}], "machine_regex": "("}, ["x"])
    assert std["printers"] == {}


@pytest.mark.parametrize("code, expected", [("pt_BR", "pt"), ("pt-PT", "pt"), ("PT", "pt"), ("en_US", "en"),
                                            ("de_DE", "en"), ("", "en"), (None, "en")])
def test_language_for(fs, code, expected):
    assert fs.language_for(code) == expected


def test_translations_have_the_same_keys(fs):
    assert set(fs.STRINGS["en"]) == set(fs.STRINGS["pt"])
    for lang in fs.LANGUAGES:
        for key, text in fs.STRINGS[lang].items():
            assert text.strip(), (lang, key)
            # the same placeholders in every language
            assert set(re.findall(r"{(\w+)}", text)) == set(re.findall(r"{(\w+)}", fs.STRINGS["en"][key])), key


def test_page_uses_only_known_keys(fs):
    keys = set(re.findall(r'data-i18n(?:-title)?="(\w+)"', fs.PAGE)) | set(re.findall(r"\bt\('(\w+)'", fs.PAGE))
    assert keys, "the page should be translated"
    assert keys <= set(fs.STRINGS["en"]), keys - set(fs.STRINGS["en"])


def test_tr(fs):
    assert fs.tr("pt", "msg_saved", n=3) == "Padrão salvo (3 slots)."
    assert fs.tr("xx", "msg_saved", n=3) == "Standard saved (3 slots)."
    assert fs.tr("en", "no_such_key") == "no_such_key"


def test_header_metadata(fs):
    with open(fs.__file__, encoding="utf-8") as stream:
        head = stream.read(800)
    assert '# name = "FilamentStandard"' in head
    assert '# id = "filament-standard"' in head
    assert '# version = "%s"' % fs.VERSION in head


def test_storage_and_data_dir_paths(fs):
    base = os.path.join("C:" + os.sep, "Users", "u", "AppData", "Roaming", "OrcaSlicer")
    local = os.path.join(base, "orca_plugins", "filament_standard.py", "filament_standard.py")
    assert fs.storage_from(local) == os.path.join(base, "orca_plugins", "plugin_data", "filament_standard")
    assert fs.data_dir_from(local) == base
    cloud = os.path.join(base, "orca_plugins", "_subscribed", "user1", "key-uuid", "cloud_plugin-x.py")
    assert fs.storage_from(cloud) == os.path.join(base, "orca_plugins", "plugin_data", "_subscribed", "user1", "key-uuid")
    assert fs.storage_from(os.path.join(base, "elsewhere.py")) == ""
    assert fs.data_dir_from(os.path.join(base, "elsewhere.py")) == ""


def test_as_list(fs):
    assert fs.as_list(None) == []
    assert fs.as_list(["#FFF", 1]) == ["#FFF", "1"]
    assert fs.as_list("#FFFFFF;#000000") == ["#FFFFFF", "#000000"]
    assert fs.as_list("#FFFFFF,#000000") == ["#FFFFFF", "#000000"]


def test_guess_material(fs):
    assert fs.guess_material("MASTERPRINT PETG 0.2") == "PETG"
    assert fs.guess_material("Generic PLA+") == "PLA"
    assert fs.guess_material("eSUN PLA-Basic") == "PLA"
    assert fs.guess_material("Polymaker ABS") == "ABS"
    assert fs.guess_material("Something") == ""


def test_example_standard_is_valid(fs):
    import json
    path = os.path.join(os.path.dirname(fs.__file__), "examples", "standard.example.json")
    with open(path, encoding="utf-8") as stream:
        raw = json.load(stream)
    std = fs.clean_standard(raw)
    assert len(std["slots"]) == len(raw["slots"])
    assert fs.variants_of(std) == ["default", "0.2", "0.4", "0.6"]
