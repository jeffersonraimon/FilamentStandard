"""The tab's JavaScript in a real browser (skipped when no Edge/Chrome/Chromium is installed)."""
import os

import page_smoke
import pytest

BROWSER = next((b for b in page_smoke.BROWSERS if b and os.path.exists(b)), None)


@pytest.mark.skipif(BROWSER is None, reason="no headless browser")
@pytest.mark.parametrize("edition", ["full", "cloud"])
def test_first_run_settings_and_sync(edition):
    result = page_smoke.run(edition)
    assert result["errors"] == []
    sent = result["sent"]
    # changing the language saves the settings on their own (not "save_std", which needs a list)
    assert sent[0] == {"cmd": "save_settings", "settings": dict(sent[0]["settings"], language="en")}
    assert sent[0]["settings"]["language"] == "en"
    # Sync with Spoolman: saves the URL first, then asks for the preview with consent
    assert sent[1]["cmd"] == "save_settings" and sent[1]["settings"]["spoolman_url"] == "http://spoolman.local:7912"
    assert sent[2] == {"cmd": "sync_preview", "consent": True}
    assert all(m["cmd"] != "save_std" for m in sent)
