"""Shared fixtures: a fake ``orca`` host module and a sample OrcaSlicer data folder."""
import importlib.util
import json
import os
import sys
import threading
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "filament_standard.py")


def load_module(name="filament_standard_under_test"):
    spec = importlib.util.spec_from_file_location(name, PLUGIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def fs():
    """The plugin imported without OrcaSlicer (pure functions only)."""
    sys.modules.pop("orca", None)
    return load_module("filament_standard_pure")


# ---------------------------------------------------------------- fake host
class FakePreset:
    def __init__(self, name, config=None):
        self.name = name
        self._config = config or {}

    def config_value(self, key):
        return self._config.get(key)


class FakeCollection:
    def __init__(self, presets):
        self.presets = {p.name: p for p in presets}

    def preset_names(self):
        return list(self.presets)

    def find_preset(self, name):
        return self.presets.get(name)


class FakeBundle:
    def __init__(self, host):
        self.host = host

    @property
    def printers(self):
        return FakeCollection([FakePreset(n, {"nozzle_diameter": z}) for n, z in self.host.printers.items()])

    @property
    def filaments(self):
        return FakeCollection([FakePreset(n) for n in self.host.filament_presets])

    def current_printer_preset(self):
        return FakePreset(self.host.machine)

    def current_filament_preset_names(self):
        return list(self.host.slots)

    def full_config_value(self, key):
        if key == "filament_colour":
            return ";".join(self.host.colors)
        if key == "nozzle_diameter":
            return self.host.printers.get(self.host.machine, "0.4")
        raise KeyError(key)


class FakeTransaction:
    def __init__(self, host, slot, name):
        self.host, self.slot, self.name = host, slot, name or host.slots[slot - 1]
        self.staged = {}

    def set(self, key, value):
        if key in self.staged:
            raise ValueError("already staged")
        self.staged[key] = value

    def commit(self):
        if self.staged:
            self.host.edits.append((self.name, dict(self.staged)))
        if self.name not in self.host.filament_presets:
            raise RuntimeError("No filament preset named %r" % self.name)
        self.host.slots[self.slot - 1] = self.name
        self.host.commits.append((self.slot, self.name))
        return types.SimpleNamespace(target_name=self.name, slot_number=self.slot)


class FakeHost:
    def __init__(self, storage):
        self.storage_dir = storage
        self.machine = "Bambu Lab A1 0.4 nozzle"
        self.printers = {"Bambu Lab A1 0.4 nozzle": "0.4", "Bambu Lab A1 0.2 nozzle": "0.2",
                         "Bambu Lab X1 Carbon 0.4 nozzle": "0.4"}
        self.filament_presets = ["PLA A", "PLA A 0.2", "PLA B", "PLA B 0.2", "PETG C", "PETG C 0.2", "Generic PLA"]
        self.slots = ["Generic PLA", "Generic PLA"]
        self.colors = ["#FFFFFF", "#000000"]
        self.language = "en_US"
        self.commits = []
        self.edits = []
        host = self

        class _Editor:
            def begin_update(self, slot, name=""):
                return FakeTransaction(host, slot, name)

        self.preset = types.SimpleNamespace(filament=_Editor())
        self.plugin = types.SimpleNamespace(storage=lambda: host.storage_dir)

    def preset_bundle(self):
        return FakeBundle(self)

    def app_info(self):
        return {"language": self.language}


def make_fake_orca(host):
    orca = types.ModuleType("orca")

    class PagesPluginCapabilityBase:
        def __init__(self, *args, **kwargs):
            self.messages = []

        def post_message(self, message):
            self.messages.append(message)

    orca.pages = types.SimpleNamespace(PagesPluginCapabilityBase=PagesPluginCapabilityBase)
    orca.base = type("base", (), {})
    orca.plugin = lambda cls: cls
    orca.registered = []
    orca.permissions = []
    orca.register_capability = orca.registered.append
    orca.request_permissions = lambda **kw: orca.permissions.append(kw)
    orca.LifecycleEvent = types.SimpleNamespace(NewProject="NewProject", ProjectOpened="ProjectOpened")
    orca.host = host
    return orca


@pytest.fixture
def plugin(tmp_path):
    """(module, page, host) with the plugin loaded against a fake OrcaSlicer host."""
    storage = tmp_path / "orca_plugins" / "plugin_data" / "filament_standard"
    storage.mkdir(parents=True)
    host = FakeHost(str(storage))
    sys.modules["orca"] = make_fake_orca(host)
    try:
        module = load_module("filament_standard_with_host")
    finally:
        sys.modules.pop("orca", None)
    page = module.FilamentStandardPage()

    def state():
        return page.messages[-1]

    page.state = state
    page.wait = lambda: page.worker and page.worker.join(5)
    assert threading.current_thread() is threading.main_thread()
    return module, page, host


# ---------------------------------------------------------------- sample data folder
def sample_conf():
    return {
        "app": {"preset_folder": "uid123", "version": "2.5.0"},
        "access_code": {"PRINTER-SERIAL": "SECRET-ACCESS-CODE"},
        "user_access_code": {"PRINTER-SERIAL": "SECRET-USER-CODE"},
        "orca_presets": [
            {"machine": "Bambu Lab A1 0.4 nozzle", "filament": "Generic PLA", "filament_01": "Generic PLA",
             "filament_colors": "#FFFFFF,#000000", "filament_multi_colors": "#FFFFFF,#000000",
             "filament_color_types": "1,1", "flush_multiplier": "1.000000",
             "flush_volumes_matrix": "0|128|608|0", "flush_volumes_vector": "140|140|140|140",
             "filament_is_mixed": "0,0", "filament_mixed_components": "|", "filament_self_index": "1,2",
             "process": "0.20mm Standard @BBL A1"},
            {"machine": "Bambu Lab A1 0.2 nozzle", "filament": "Generic PLA",
             "filament_colors": "#FFFFFF", "flush_volumes_matrix": "0", "flush_volumes_vector": "140|140"},
            {"machine": "Bambu Lab H2D 0.4 nozzle", "filament": "Generic PLA", "filament_01": "Generic PLA",
             "filament_colors": "#FFFFFF,#000000", "flush_volumes_matrix": "0|1|2|0|0|1|2|0",
             "flush_volumes_vector": "140|140|140|140"},
            {"machine": "Bambu Lab X1 Carbon 0.4 nozzle", "filament": "Generic PETG", "filament_colors": "#123456"},
        ],
    }


@pytest.fixture
def data_dir(tmp_path, fs):
    root = tmp_path / "OrcaSlicer"
    fdir = root / "user" / "uid123" / "filament"
    fdir.mkdir(parents=True)
    fs.write_conf(str(root / "OrcaSlicer.conf"), sample_conf())
    for name, cost in (("PLA A", "100"), ("PLA A 0.2", None), ("PETG C", "80.00")):
        data = {"name": name, "inherits": "Generic PLA @BBL A1", "from": "User"}
        if cost:
            data["filament_cost"] = [cost]
        (fdir / (name + ".json")).write_text(json.dumps(data), encoding="utf-8")
    (fdir / "PLA A.info").write_text("sync_info = \nuser_id = uid123\nsetting_id = abc\nbase_id = GFSL\nupdated_time = 1\n",
                                     encoding="utf-8")
    return root


@pytest.fixture
def standard(fs):
    return fs.clean_standard({
        "slots": [
            {"presets": {"default": "PLA A", "0.2": "PLA A 0.2"}, "color": "#FFFFFF", "spool": 1},
            {"presets": {"default": "PLA B", "0.2": "PLA B 0.2"}, "color": "#000000", "spool": 2},
            {"presets": {"default": "PETG C"}, "color": "#ff0000", "spool": 3},
        ],
        "printers": {"Bambu Lab A1 0.4 nozzle": "0.4", "Bambu Lab A1 0.2 nozzle": "0.2",
                     "Bambu Lab H2D 0.4 nozzle": "0.4", "Never Used Printer 0.6 nozzle": "0.6"},
        "spool_map": {"Acme|PLA Basic": {"default": "PLA A", "0.2": "PLA A 0.2"},
                      "Beta|PLA Basic": {"default": "PLA B", "0.2": "PLA B 0.2"},
                      "Gamma|PETG Basic": {"default": "PETG C"}},
        "prices": {"PLA A": 120, "PLA A 0.2": 120, "PETG C": 80},
    })


def spool(sid, vendor, name, material, color, price=None, weight=1000):
    return {"id": sid, "price": price, "initial_weight": weight, "remaining_weight": 500,
            "filament": {"name": name, "material": material, "color_hex": color, "weight": weight,
                         "vendor": {"name": vendor}}}
