"""Browser smoke test of the tab's JavaScript (run manually: python tests/page_smoke.py).

Renders the page of both editions in headless Edge/Chrome with a stub ``orca`` bridge, feeds it
a first-run state (empty list), then changes the language and presses *Sync with Spoolman*.
It prints the messages the page sent and any JavaScript error.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_release  # noqa: E402

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    shutil.which("chromium") or "", shutil.which("google-chrome") or "",
] + ["/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]

STUB = """<script>
window.sent=[];window.errors=[];
window.onerror=(m)=>{window.errors.push(String(m));};
window.confirm=()=>true;
window.orca={postMessage:m=>window.sent.push(m),onMessage:cb=>{window._cb=cb;}};
</script>"""

DRIVER = """<script>
try{
const state=%s;
window._cb(state);
const lang=document.getElementById('lang');lang.value='en';lang.dispatchEvent(new Event('change'));
const url=document.getElementById('url');url.value='http://spoolman.local:7912';
document.getElementById('b-sync').click();
}catch(e){window.errors.push('driver: '+e+' '+(e.stack||''));}
document.body.setAttribute('data-result',JSON.stringify({sent:window.sent,errors:window.errors}));
</script>"""


def run(edition):
    with open(os.path.join(ROOT, "filament_standard.py"), encoding="utf-8") as stream:
        source = build_release.make_edition(stream.read(), edition)
    namespace = {"__name__": "smoke", "__file__": "smoke.py"}
    exec(compile(source, "smoke.py", "exec"), namespace)
    std = namespace["empty_standard"]()
    state = {"type": "state", "std": std, "variants": ["default"], "proposal": None, "status": "", "error": "",
             "busy": False, "pending_job": False, "current": {"machine": "Printer 0.4 nozzle", "nozzle": "0.4",
                                                              "names": ["Generic PLA"], "colors": ["#FFFFFF"]},
             "presets": ["Generic PLA"], "printers": ["Printer 0.4 nozzle"], "version": namespace["VERSION"],
             "lang": "pt", "i18n": namespace["STRINGS"]["pt"], "slots_changed": False}
    page = namespace["PAGE"].replace("<script>", STUB + "<script>", 1).replace("</body>", DRIVER % json.dumps(state) + "</body>")
    head, _, tail = page.rpartition("send({cmd:'ready'});")  # the initial request, not the one in onMessage
    page = head + tail
    browser = next(b for b in BROWSERS if b and os.path.exists(b))
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, "page.html")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(page)
    args = [browser, "--headless=new", "--disable-gpu", "--dump-dom"]
    if os.name != "nt":
        args += ["--no-sandbox", "--disable-dev-shm-usage"]  # CI containers
    proc = subprocess.run(args + [pathlib.Path(path).as_uri()],
                          capture_output=True, text=True, encoding="utf-8", timeout=90)
    dom = proc.stdout
    if 'data-result="' not in dom:
        raise RuntimeError("the browser did not render the page: %s" % proc.stderr[-2000:])
    start = dom.index('data-result="') + len('data-result="')
    raw = dom[start:dom.index('"', start)].replace("&quot;", '"').replace("&amp;", "&")
    return json.loads(raw)


if __name__ == "__main__":
    for edition in ("full", "cloud"):
        result = run(edition)
        print(edition, json.dumps(result, ensure_ascii=False))
