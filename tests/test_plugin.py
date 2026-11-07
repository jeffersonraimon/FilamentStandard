"""The OrcaSlicer tab, driven through a fake ``orca`` host."""
import json
import os

from conftest import spool


def test_registration(plugin):
    module, page, host = plugin
    module.FilamentStandardPlugin().register_capabilities()
    orca = module.orca
    assert orca.registered == [module.FilamentStandardPage]
    assert orca.permissions[-1]["threading"] is True
    assert page.get_name() == "FilamentStandard"
    assert "orca.postMessage" in page.get_ui()


def test_first_run_state(plugin):
    module, page, host = plugin
    page.on_message({"cmd": "ready"})
    state = page.state()
    assert state["type"] == "state"
    assert state["std"]["slots"] == []
    assert state["current"] == {"machine": "Bambu Lab A1 0.4 nozzle", "nozzle": "0.4",
                                "names": ["Generic PLA", "Generic PLA"], "colors": ["#FFFFFF", "#000000"]}
    assert "Bambu Lab A1 0.2 nozzle" in state["printers"]
    assert "PLA A" in state["presets"]
    assert state["lang"] == "en" and state["i18n"]["title"] == "Filament standard"
    assert not state["error"]


def test_language_follows_orca_and_can_be_forced(plugin):
    module, page, host = plugin
    host.language = "pt_BR"
    page.on_message({"cmd": "ready"})
    assert page.state()["lang"] == "pt"
    page.std["language"] = "en"
    page.on_message({"cmd": "ready"})
    assert page.state()["i18n"]["save"] == "Save standard"


def test_capture_and_save(plugin):
    module, page, host = plugin
    host.slots = ["PLA A", "PLA B", "PLA A"]
    host.colors = ["#FFFFFF", "#000000", "#FF0000"]
    page.on_message({"cmd": "capture"})
    std = page.state()["std"]
    # only a 0.4 printer so far: no 0.2 column to fill yet
    assert [s["presets"] for s in std["slots"]] == [{"default": "PLA A"}, {"default": "PLA B"}, {"default": "PLA A"}]
    assert [s["color"] for s in std["slots"]] == ["#FFFFFF", "#000000", "#FF0000"]
    assert std["printers"] == {"Bambu Lab A1 0.4 nozzle": "0.4"}
    saved = json.load(open(os.path.join(host.storage_dir, module.STD_FILE), encoding="utf-8"))
    assert saved["slots"] == std["slots"]

    # the page edits the 0.2 column and adds a printer with an unknown nozzle
    edited = dict(std)
    edited["slots"] = [dict(s) for s in std["slots"]]
    edited["slots"][0]["presets"] = {"default": "PLA A", "0.2": "PLA A 0.2"}
    edited["slots"][0]["spool"] = 11
    edited["printers"] = {"Bambu Lab A1 0.4 nozzle": "0.4", "Bambu Lab A1 0.2 nozzle": ""}
    page.on_message({"cmd": "save_std", "std": edited})
    state = page.state()
    assert not state["error"]
    assert state["std"]["printers"]["Bambu Lab A1 0.2 nozzle"] == "0.2"  # read from the printer preset
    assert state["variants"] == ["default", "0.2", "0.4"]


def test_capture_keeps_spools_by_preset_and_colour(plugin):
    module, page, host = plugin
    page.std = module.clean_standard({"slots": [
        {"presets": {"default": "PLA A", "0.2": "PLA A 0.2"}, "color": "#FFFFFF", "spool": 1},
        {"presets": {"default": "PLA A", "0.2": "PLA A 0.2"}, "color": "#00FF00", "spool": 2},
    ]})
    host.slots = ["PLA A", "PLA A"]
    host.colors = ["#00FF00", "#FFFFFF"]
    page.on_message({"cmd": "capture"})
    slots = page.state()["std"]["slots"]
    assert [(s["color"], s["spool"]) for s in slots] == [("#00FF00", 2), ("#FFFFFF", 1)]
    assert slots[0]["presets"]["0.2"] == "PLA A 0.2"  # other columns survive


def test_capture_on_a_nozzle_column(plugin):
    module, page, host = plugin
    page.std = module.clean_standard({"slots": [{"presets": {"default": "PLA A", "0.2": "PLA A 0.2"}}]})
    host.machine = "Bambu Lab A1 0.2 nozzle"
    host.slots = ["PLA B 0.2"]
    host.colors = ["#000000"]
    page.on_message({"cmd": "capture"})
    assert page.state()["std"]["slots"][0]["presets"] == {"0.2": "PLA B 0.2", "default": "PLA B 0.2"}
    assert '"0.2"' in page.state()["status"]


def test_capture_on_a_small_nozzle_finds_the_base_preset(plugin):
    module, page, host = plugin
    host.machine = "Bambu Lab A1 0.2 nozzle"
    host.slots = ["PLA A 0.2", "Generic PLA"]
    host.colors = ["#FFFFFF", "#000000"]
    page.on_message({"cmd": "capture"})
    slots = page.state()["std"]["slots"]
    assert slots[0]["presets"] == {"default": "PLA A", "0.2": "PLA A 0.2"}
    assert slots[1]["presets"] == {"default": "Generic PLA"}


def test_variants_fill_when_a_printer_is_added(plugin):
    module, page, host = plugin
    host.slots = ["PLA A", "PETG C", "Generic PLA"]
    page.on_message({"cmd": "capture"})
    page.on_message({"cmd": "save_settings", "settings": {"printers": {"Bambu Lab A1 0.4 nozzle": "0.4",
                                                                       "Bambu Lab A1 0.2 nozzle": "0.2"}}})
    state = page.state()
    assert [s["presets"].get("0.2") for s in state["std"]["slots"]] == ["PLA A 0.2", "PETG C 0.2", None]
    assert state["slots_changed"] is True


def test_save_rejects_empty_list(plugin):
    module, page, host = plugin
    page.on_message({"cmd": "save_std", "std": {"slots": []}})
    assert page.state()["error"] == "The list needs at least one slot"


def test_restore_live(plugin):
    module, page, host = plugin
    host.machine = "Bambu Lab A1 0.2 nozzle"
    host.slots = ["Generic PLA", "PLA B 0.2", "Generic PLA"]
    page.std = module.clean_standard({"slots": [
        {"presets": {"default": "PLA A", "0.2": "PLA A 0.2"}},
        {"presets": {"default": "PLA B", "0.2": "PLA B 0.2"}},
        {"presets": {"default": "No such preset"}},
        {"presets": {"default": "PETG C"}},
    ]})
    page.on_message({"cmd": "restore_live"})
    page.wait()
    assert host.commits == [(1, "PLA A 0.2")]  # slot 2 already right, slot 3 fails, slot 4 does not exist
    assert host.slots[:2] == ["PLA A 0.2", "PLA B 0.2"]
    assert "slot 3 (No such preset)" in page.error
    assert "1 slot(s) updated" in page.status and "3 slots" in page.status
    assert page.messages[-1] == {"type": "refresh_request"}
    assert page.busy is False


def test_restore_live_nothing_to_do(plugin):
    module, page, host = plugin
    page.std = module.clean_standard({"slots": [{"presets": {"default": "Generic PLA"}}] * 2})
    page.on_message({"cmd": "restore_live"})
    assert page.worker is None
    assert page.state()["status"] == "The 2 slots already use the standard presets."


def test_restore_full_schedules_helper(plugin, monkeypatch):
    module, page, host = plugin
    page.std = module.clean_standard({"slots": [{"presets": {"default": "PLA A"}}],
                                      "printers": {"Bambu Lab A1 0.4 nozzle": "0.4"}, "allow_conf_edit": True})
    launched = []
    monkeypatch.setattr(module, "find_python", lambda: "/usr/bin/python3")
    monkeypatch.setattr(module.subprocess, "Popen", lambda args, **kw: launched.append(args))
    page.on_message({"cmd": "restore_full", "relaunch": False})
    state = page.state()
    assert not state["error"], state["error"]
    assert state["pending_job"] is True
    job_path = os.path.join(host.storage_dir, module.JOB_FILE)
    job = json.load(open(job_path, encoding="utf-8"))
    assert job["relaunch"] is False and job["standard"]["slots"]
    assert launched[0][0] == "/usr/bin/python3" and launched[0][2:] == ["--apply", job_path]
    page.on_message({"cmd": "cancel_full"})
    assert not os.path.exists(job_path) and page.state()["pending_job"] is False


def test_restore_full_needs_printers_and_python(plugin, monkeypatch):
    module, page, host = plugin
    page.std = module.clean_standard({"slots": [{"presets": {"default": "PLA A"}}]})
    page.on_message({"cmd": "restore_full"})
    assert page.state()["error"].startswith("The full restore is off")  # opt-in, off by default
    assert not os.path.exists(os.path.join(host.storage_dir, module.JOB_FILE))
    page.std["allow_conf_edit"] = True
    page.on_message({"cmd": "restore_full"})
    assert page.state()["error"] == "Select at least one printer profile first"
    page.on_message({"cmd": "add_current_printer"})
    assert page.state()["std"]["printers"] == {"Bambu Lab A1 0.4 nozzle": "0.4"}
    monkeypatch.setattr(module, "find_python", lambda: "")
    page.on_message({"cmd": "restore_full"})
    assert "Python was not found" in page.state()["error"]


def test_sync_preview_and_apply(plugin, monkeypatch):
    module, page, host = plugin
    page.std = module.clean_standard({
        "slots": [{"presets": {"default": "PLA A"}, "color": "#FFFFFF", "spool": 1}],
        "spool_map": {"Acme|PLA Basic": {"default": "PLA A"}},
        "spoolman_url": "http://spoolman.local:7912",
    })
    spools = [spool(1, "Acme", "PLA Basic", "PLA", "FFFFFF", 100),
              spool(2, "Delta", "PETG Basic", "PETG", "000000", 90)]
    monkeypatch.setattr(module, "fetch_spools", lambda url: spools)
    page.on_message({"cmd": "sync_apply"})
    assert page.state()["error"] == "Create the sync preview first"
    page.on_message({"cmd": "sync_preview"})
    assert page.state()["error"].startswith("Allow the connection to Spoolman")  # asks first
    assert page.state()["proposal"] is None
    page.on_message({"cmd": "sync_preview", "consent": True})
    assert page.state()["std"]["spoolman_consent"] == "http://spoolman.local:7912"
    assert module.orca.permissions[-1] == {"network": ["http://spoolman.local:7912"]}
    proposal = page.state()["proposal"]
    assert [u["id"] for u in proposal["unmapped"]] == [2]
    page.on_message({"cmd": "sync_apply", "map": {"Delta|PETG Basic": {"default": "PETG C", "0.2": "PETG C 0.2"}}})
    std = page.state()["std"]
    assert page.state()["proposal"] is None
    assert [(s["presets"]["default"], s["spool"]) for s in std["slots"]] == [("PLA A", 1), ("PETG C", 2)]
    assert std["spool_map"]["Delta|PETG Basic"] == {"default": "PETG C", "0.2": "PETG C 0.2"}
    assert std["prices"] == {"PLA A": 100.0, "PETG C": 90.0, "PETG C 0.2": 90.0}


def test_sync_needs_url(plugin):
    module, page, host = plugin
    page.on_message({"cmd": "sync_preview"})
    assert page.state()["error"] == "Set the Spoolman URL in Settings first"


def test_legacy_storage_is_migrated(plugin):
    module, page, host = plugin
    legacy_dir = os.path.join(os.path.dirname(host.storage_dir), "filamentos_padrao")
    os.makedirs(legacy_dir)
    with open(os.path.join(legacy_dir, "padrao.json"), "w", encoding="utf-8") as stream:
        json.dump({"slots": [{"p04": "PLA A", "p02": "PLA A 0.2", "color": "#FFFFFF", "spool": 5}],
                   "machine_regex": "A1 0\\.\\d", "spoolman_url": "http://s:7912"}, stream)
    page.on_message({"cmd": "ready"})
    state = page.state()
    assert state["std"]["slots"][0]["presets"] == {"default": "PLA A", "0.2": "PLA A 0.2"}
    assert set(state["std"]["printers"]) == {"Bambu Lab A1 0.4 nozzle", "Bambu Lab A1 0.2 nozzle"}
    assert state["lang"] == "pt"  # the old plugin was Portuguese-only
    assert "instalação anterior" in state["status"]
    assert state["std"]["spoolman_url"] == ""  # not carried over
    assert os.path.exists(os.path.join(host.storage_dir, module.STD_FILE))


def test_import_export_json(plugin):
    module, page, host = plugin
    page.on_message({"cmd": "import_json", "text": "{not json"})
    assert page.state()["error"].startswith("Invalid JSON")
    text = json.dumps({"slots": [{"presets": {"default": "PLA B"}, "color": "#000000"}],
                       "printers": {"Bambu Lab A1 0.4 nozzle": "0.4"}})
    page.on_message({"cmd": "import_json", "text": text})
    assert page.state()["std"]["slots"] == [{"presets": {"default": "PLA B"}, "color": "#000000", "spool": None}]
    legacy = json.dumps({"slots": [{"p04": "X", "p02": "X 0.2", "color": "#FFFFFF"}]})
    page.on_message({"cmd": "import_json", "text": legacy})
    assert page.state()["std"]["slots"][0]["presets"] == {"default": "X", "0.2": "X 0.2"}


def test_reset_and_unknown_command(plugin):
    module, page, host = plugin
    page.std = module.clean_standard({"slots": [{"presets": {"default": "PLA A"}}]})
    page.on_message({"cmd": "reset"})
    assert page.state()["std"]["slots"] == []
    page.on_message({"cmd": "explode"})
    assert page.state()["error"] == "unknown command: explode"


def test_new_project_event(plugin):
    module, page, host = plugin
    page.std = module.clean_standard({"slots": [{"presets": {"default": "PLA A"}}, {"presets": {"default": "PLA B"}}]})
    page.on_lifecycle_event("NewProject", None)
    assert host.commits == []  # off by default
    page.std["auto_new_project"] = True
    page.on_lifecycle_event("ProjectOpened", None)
    assert host.commits == []
    page.on_lifecycle_event("NewProject", None)
    page.wait()
    assert host.commits == [(1, "PLA A"), (2, "PLA B")]


def test_tab_icon(plugin):
    module, page, host = plugin
    path = page.get_icon()
    assert path == os.path.join(host.storage_dir, module.ICON_FILE)
    with open(path, encoding="utf-8") as stream:
        assert stream.read() == module.TAB_ICON_SVG
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("old")
    assert open(page.get_icon(), encoding="utf-8").read() == module.TAB_ICON_SVG  # refreshed


def test_embedded_icon_matches_asset(plugin):
    module, page, host = plugin
    asset = os.path.join(os.path.dirname(module.__file__), "assets", "tab-icon.svg")
    with open(asset, encoding="utf-8") as stream:
        assert stream.read().strip() == module.TAB_ICON_SVG
    assert module.TAB_ICON_SVG.startswith("<svg") and 'width="20"' in module.TAB_ICON_SVG


def test_previous_install_is_reused(plugin, tmp_path):
    module, page, host = plugin
    # a local FilamentStandard install, then the plugin is subscribed on Orca Cloud
    local = os.path.join(os.path.dirname(host.storage_dir), "filament_standard_any")
    os.makedirs(local)
    with open(os.path.join(local, module.STD_FILE), "w", encoding="utf-8") as stream:
        json.dump({"slots": [{"presets": {"default": "PLA B"}, "color": "#000000"}]}, stream)
    page.on_message({"cmd": "ready"})
    assert page.state()["std"]["slots"][0]["presets"] == {"default": "PLA B"}


def test_find_previous_from_cloud_storage(fs, tmp_path):
    data_root = tmp_path / "orca_plugins" / "plugin_data"
    cloud = data_root / "_subscribed" / "user1" / "uuid-key"
    cloud.mkdir(parents=True)
    legacy = data_root / "filamentos_padrao"
    legacy.mkdir()
    (legacy / "padrao.json").write_text('{"slots": [{"p04": "X"}]}', encoding="utf-8")
    kind, data = fs.find_previous(str(cloud))
    assert kind == "legacy" and data["slots"] == [{"p04": "X"}]
    # other plugins' folders are never read
    other = data_root / "some_other_plugin"
    other.mkdir()
    (other / fs.STD_FILE).write_text('{"slots": [{"presets": {"default": "OTHER"}}]}', encoding="utf-8")
    assert fs.find_previous(str(cloud))[0] == "legacy"
    local = data_root / "filament_standard"
    local.mkdir()
    (local / fs.STD_FILE).write_text('{"slots": [{"presets": {"default": "Y"}}]}', encoding="utf-8")
    assert fs.find_previous(str(cloud))[0] == "current"  # a FilamentStandard install wins over 1.x
    (cloud / fs.STD_FILE).write_text('{"slots": [{"presets": {"default": "Z"}}]}', encoding="utf-8")
    assert fs.find_previous(str(cloud))[1]["slots"][0]["presets"]["default"] == "Y"  # never itself
    assert fs.find_previous(str(tmp_path / "nothing" / "here")) == ("", None)


def test_spoolman_consent_is_per_host(plugin, monkeypatch):
    module, page, host = plugin
    calls = []
    monkeypatch.setattr(module, "fetch_spools", lambda url: calls.append(url) or [])
    page.std = module.clean_standard({"spoolman_url": "http://a.local:7912", "spoolman_consent": "http://a.local:7912"})
    page.on_message({"cmd": "sync_preview"})
    assert calls == ["http://a.local:7912"] and not page.state()["error"]
    page.std["spoolman_url"] = "http://b.local:7912"  # another host needs a new confirmation
    page.on_message({"cmd": "sync_preview"})
    assert calls == ["http://a.local:7912"] and page.state()["error"]


def test_declared_network_only_for_confirmed_host(plugin):
    module, page, host = plugin
    with open(os.path.join(host.storage_dir, module.STD_FILE), "w", encoding="utf-8") as stream:
        json.dump({"spoolman_url": "http://a.local:7912", "spoolman_consent": ""}, stream)
    module.storage_from = lambda path: host.storage_dir
    module.declare_permissions()
    assert module.orca.permissions[-1]["network"] == []
    with open(os.path.join(host.storage_dir, module.STD_FILE), "w", encoding="utf-8") as stream:
        json.dump({"spoolman_url": "http://a.local:7912", "spoolman_consent": "http://a.local:7912"}, stream)
    module.declare_permissions()
    assert module.orca.permissions[-1]["network"] == ["http://a.local:7912"]


def test_apply_prices_through_the_api(plugin):
    module, page, host = plugin
    host.slots = ["PLA A", "PLA B", "PLA A", "Generic PLA"]
    page.std = module.clean_standard({"prices": {"PLA A": 120, "PLA B": 99.5}})
    page.on_message({"cmd": "apply_prices"})
    page.wait()
    assert host.edits == [("PLA A", {"filament_cost": "120.00"}), ("PLA B", {"filament_cost": "99.50"})]
    assert host.slots == ["PLA A", "PLA B", "PLA A", "Generic PLA"]  # assignments untouched
    assert "2 preset(s)" in page.status
    host.slots = ["Generic PLA"]
    page.on_message({"cmd": "apply_prices"})
    assert page.state()["status"] == "No preset in the current project has a different price."


def test_settings_save_without_a_list(plugin, monkeypatch):
    """First run (empty list): the language and the Spoolman URL must still be saved."""
    module, page, host = plugin
    page.on_message({"cmd": "save_settings", "settings": {"language": "pt", "spoolman_url": " http://s.local:7912 ",
                                                          "slots": "ignored", "prices": "ignored"}})
    state = page.state()
    assert not state["error"]
    assert state["lang"] == "pt" and state["std"]["spoolman_url"] == "http://s.local:7912"
    assert state["std"]["slots"] == [] and state["slots_changed"] is False
    saved = json.load(open(os.path.join(host.storage_dir, module.STD_FILE), encoding="utf-8"))
    assert saved["language"] == "pt" and saved["spoolman_url"] == "http://s.local:7912"
    page.on_message({"cmd": "save_settings", "settings": {"language": "en"}})
    assert page.state()["i18n"]["save"] == "Save standard"
    monkeypatch.setattr(module, "fetch_spools", lambda url: [spool(1, "Acme", "PLA Basic", "PLA", "FFFFFF", 100)])
    page.on_message({"cmd": "sync_preview", "consent": True})
    state = page.state()
    assert not state["error"] and [u["id"] for u in state["proposal"]["unmapped"]] == [1]


def test_settings_keep_the_list_and_fill_nozzles(plugin):
    module, page, host = plugin
    page.std = module.clean_standard({"slots": [{"presets": {"default": "PLA A"}}]})
    page.on_message({"cmd": "save_settings", "settings": {"printers": {"Bambu Lab A1 0.2 nozzle": ""}, "auto_new_project": True}})
    std = page.state()["std"]
    assert std["slots"][0]["presets"] == {"default": "PLA A", "0.2": "PLA A 0.2"}  # the new 0.2 column is filled
    assert std["printers"] == {"Bambu Lab A1 0.2 nozzle": "0.2"} and std["auto_new_project"] is True


def test_slots_changed_flag(plugin):
    module, page, host = plugin
    page.on_message({"cmd": "ready"})
    host.slots = ["PLA A"]
    page.on_message({"cmd": "capture"})
    assert page.state()["slots_changed"] is True
    page.on_message({"cmd": "ready"})
    assert page.state()["slots_changed"] is False


def test_page_saves_settings_separately(plugin):
    module, page, host = plugin
    assert module.PAGE.count("cmd:'save_std'") == 1  # only the "Save standard" button
    assert "cmd:'save_settings'" in module.PAGE
