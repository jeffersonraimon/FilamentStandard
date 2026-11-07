import http.server
import json
import threading

import pytest

from conftest import spool


def spools_matching_standard():
    return [
        spool(1, "Acme", "PLA Basic", "PLA", "FFFFFF", 120),
        spool(2, "Beta", "PLA Basic", "PLA", "000000", 100),
        spool(3, "Gamma", "PETG Basic", "PETG", "FF0000", 80),
    ]


def test_spool_info(fs):
    info = fs.spool_info(spool(9, "Acme", "PLA Basic", "pla", "#abcdef", 60, weight=500))
    assert info == {"id": 9, "key": "Acme|PLA Basic", "material": "PLA", "color": "#ABCDEF", "price_kg": 120.0}
    bare = fs.spool_info({"id": 1, "filament": {"multi_color_hexes": "112233,445566"}})
    assert bare["color"] == "#112233" and bare["price_kg"] is None and bare["key"] == "?|?"


def test_spoolman_origin(fs):
    assert fs.spoolman_origin("http://host:7912/") == "http://host:7912"
    assert fs.spoolman_origin("https://spool.example.com/x") == "https://spool.example.com"
    assert fs.spoolman_origin("ftp://x") == ""
    assert fs.spoolman_origin("") == ""


def test_plan_sync_no_changes(fs, standard):
    plan = fs.plan_sync(standard, spools_matching_standard())
    assert [s["spool"] for s in plan["slots"]] == [1, 2, 3]
    assert not (plan["added"] or plan["removed"] or plan["recolored"] or plan["unmapped"])
    assert plan["price_changes"] == [{"preset": "PLA B", "from": None, "to": 100.0},
                                     {"preset": "PLA B 0.2", "from": None, "to": 100.0}]


def test_plan_sync_changes(fs, standard):
    spools = spools_matching_standard()
    spools[1]["filament"]["color_hex"] = "111111"           # recoloured
    spools.pop(2)                                           # PETG spool archived
    spools.append(spool(4, "Acme", "PLA Basic", "PLA", "00FF00", 100))   # new colour of a known filament
    spools.append(spool(5, "Acme", "PLA Basic", "PLA", "FFFFFF", 130))   # second white spool: no new slot
    spools.append(spool(6, "Delta", "PLA Silk", "PLA", "C0C0C0", 150))   # unknown filament
    before = json.dumps(standard, sort_keys=True)
    plan = fs.plan_sync(standard, spools)
    assert json.dumps(standard, sort_keys=True) == before  # the standard itself is not modified
    assert [s["spool"] for s in plan["removed"]] == [3]
    assert plan["recolored"] == [{"spool": 2, "from": "#000000", "to": "#111111"}]
    assert [(s["spool"], s["color"]) for s in plan["added"]] == [(4, "#00FF00")]
    assert [u["id"] for u in plan["unmapped"]] == [6]
    # PLA white first, then the rest by brand (Acme before Beta keeps the current order)
    assert [s["spool"] for s in plan["slots"]] == [1, 4, 2]
    assert plan["prices"]["PLA A"] == round((120 + 100 + 130) / 3, 2)


def test_sort_slots_order(fs):
    slots = [
        {"presets": {"default": "Beta PETG"}, "color": "#000000"},
        {"presets": {"default": "Beta PLA"}, "color": "#FF0000"},
        {"presets": {"default": "Acme PETG"}, "color": "#FFFFFF"},
        {"presets": {"default": "Zeta ABS"}, "color": "#FFFFFF"},
        {"presets": {"default": "Acme PLA"}, "color": "#000000"},
        {"presets": {"default": "Beta PLA"}, "color": "#FFFFFF"},
        {"presets": {"default": "Acme PLA"}, "color": "#00FF00"},
        {"presets": {"default": "Beta PLA"}, "color": "#0000FF"},
    ]
    mats = {id(s): fs.guess_material(s["presets"]["default"]) for s in slots}
    ordered = [(s["presets"]["default"], s["color"]) for s in fs.sort_slots(slots, mats)]
    assert ordered == [
        ("Beta PLA", "#FFFFFF"), ("Acme PLA", "#000000"),
        ("Beta PLA", "#FF0000"), ("Beta PLA", "#0000FF"), ("Acme PLA", "#00FF00"),
        ("Acme PETG", "#FFFFFF"), ("Beta PETG", "#000000"),
        ("Zeta ABS", "#FFFFFF"),
    ]


def test_plan_sync_without_sorting(fs, standard):
    standard["sort_on_sync"] = False
    standard["slots"].reverse()
    plan = fs.plan_sync(standard, spools_matching_standard())
    assert [s["spool"] for s in plan["slots"]] == [3, 2, 1]


class _Handler(http.server.BaseHTTPRequestHandler):
    payload = b"[]"
    paths = []

    def do_GET(self):  # noqa: N802
        _Handler.paths.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(_Handler.payload)

    def log_message(self, *args):
        pass


@pytest.fixture
def spoolman_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d/" % server.server_address[1]
    server.shutdown()


def test_fetch_spools(fs, spoolman_server):
    _Handler.payload = json.dumps(spools_matching_standard()).encode()
    spools = fs.fetch_spools(spoolman_server)
    assert [s["id"] for s in spools] == [1, 2, 3]
    assert _Handler.paths[-1] == "/api/v1/spool?allow_archived=false"


def test_fetch_spools_rejects_bad_url(fs):
    with pytest.raises(ValueError):
        fs.fetch_spools("file:///etc/passwd")
