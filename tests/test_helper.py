"""The detached helper (--apply) and the manual --restore command."""
import json
import os

from conftest import sample_conf


def write_job(fs, folder, data_dir, std, **extra):
    job = os.path.join(str(folder), fs.JOB_FILE)
    fs.write_json_atomic(job, dict({"data_dir": str(data_dir), "standard": std, "relaunch": False}, **extra))
    return job


def test_run_job_applies_and_removes_job(fs, tmp_path, data_dir, standard):
    job = write_job(fs, tmp_path, data_dir, standard)
    assert fs.run_job(job, wait=False) == 0
    assert not os.path.exists(job)
    conf = fs.read_conf(str(data_dir / "OrcaSlicer.conf"))
    assert fs.entry_filaments(conf["orca_presets"][0]) == ["PLA A", "PLA B", "PETG C"]
    log = (tmp_path / fs.LOG_FILE).read_text(encoding="utf-8")
    assert "written to 3 printer profile(s)" in log


def test_run_job_prefers_latest_saved_standard(fs, tmp_path, data_dir, standard):
    job = write_job(fs, tmp_path, data_dir, standard)
    newer = json.loads(json.dumps(standard))
    newer["slots"] = newer["slots"][:1]
    fs.write_json_atomic(str(tmp_path / fs.STD_FILE), newer)
    assert fs.run_job(job, wait=False) == 0
    conf = fs.read_conf(str(data_dir / "OrcaSlicer.conf"))
    assert fs.entry_filaments(conf["orca_presets"][0]) == ["PLA A"]


def test_run_job_waits_and_honours_cancel(fs, tmp_path, data_dir, standard, monkeypatch):
    job = write_job(fs, tmp_path, data_dir, standard)
    calls = []

    def running():
        calls.append(1)
        if len(calls) == 2:
            os.remove(job)  # the user pressed "cancel" while OrcaSlicer was open
        return True

    monkeypatch.setattr(fs, "orca_running", running)
    assert fs.run_job(job, wait=True, poll=0) == 1
    assert fs.read_conf(str(data_dir / "OrcaSlicer.conf")) == sample_conf()  # nothing changed


def test_run_job_waits_until_closed(fs, tmp_path, data_dir, standard, monkeypatch):
    job = write_job(fs, tmp_path, data_dir, standard)
    states = iter([True, True, False])
    monkeypatch.setattr(fs, "orca_running", lambda: next(states))
    assert fs.run_job(job, wait=True, poll=0) == 0
    assert not os.path.exists(job)


def test_run_job_relaunches(fs, tmp_path, data_dir, standard, monkeypatch):
    job = write_job(fs, tmp_path, data_dir, standard, relaunch=True, orca_exe="/opt/orca/orca-slicer")
    launched = []
    monkeypatch.setattr(fs.subprocess, "Popen", lambda args, **kw: launched.append(args))
    assert fs.run_job(job, wait=False) == 0
    assert launched == [["/opt/orca/orca-slicer"]]
    assert "OrcaSlicer reopened" in (tmp_path / fs.LOG_FILE).read_text(encoding="utf-8")


def test_run_job_reports_errors(fs, tmp_path, standard):
    job = write_job(fs, tmp_path, tmp_path / "missing", standard)
    assert fs.run_job(job, wait=False) == 3
    assert "ERROR" in (tmp_path / fs.LOG_FILE).read_text(encoding="utf-8")
    assert not os.path.exists(job)


def test_main_restore(fs, tmp_path, data_dir, standard, monkeypatch, capsys):
    path = tmp_path / "standard.json"
    path.write_text(json.dumps(standard), encoding="utf-8")
    monkeypatch.setattr(fs, "orca_running", lambda: False)
    assert fs.main(["x", "--restore", str(data_dir), str(path)]) == 0
    assert "written to 3 printer profile(s)" in capsys.readouterr().out
    monkeypatch.setattr(fs, "orca_running", lambda: True)
    assert fs.main(["x", "--restore", str(data_dir), str(path)]) == 2
    assert fs.main(["x"]) == 1


def test_find_python_returns_a_path_or_empty(fs):
    found = fs.find_python()
    assert found == "" or os.path.exists(found)
