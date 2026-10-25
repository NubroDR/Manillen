from pathlib import Path

import pytest

from prepare_legacy_pages import SAFE_STARTUP, prepare_legacy_pages


LEGACY_INDEX = """<!doctype html>
<html>
  <head>
    <script type="module">
      import { runExportedApp } from "./shinylive/shinylive.js";
      runExportedApp({
        id: "root",
        appEngine: "python",
        relPath: "",
      });
    </script>
  </head>
</html>
"""


def test_prepare_legacy_pages_waits_for_controller_before_startup(tmp_path):
    site_dir = tmp_path / "legacy"
    site_dir.mkdir()
    (site_dir / "shinylive-sw.js").write_text("", encoding="utf-8")
    index_path = site_dir / "index.html"
    index_path.write_text(LEGACY_INDEX, encoding="utf-8")

    assert prepare_legacy_pages(site_dir) is True
    updated = index_path.read_text(encoding="utf-8")
    assert SAFE_STARTUP in updated
    assert updated.index("if (!(await waitForServiceWorkerController())) return;") < updated.index(
        'await import("./shinylive/shinylive.js")'
    )
    assert 'serviceWorker.register(new URL("./shinylive-sw.js", location.href)' in updated
    assert "window.location.reload();" in updated
    assert "sessionStorage.removeItem" in updated
    assert "async function startLegacyApp()" in updated
    assert "startLegacyApp();" in updated
    assert prepare_legacy_pages(site_dir) is False


def test_prepare_legacy_pages_leaves_static_site_unchanged(tmp_path):
    site_dir = tmp_path / "static"
    site_dir.mkdir()
    index_path = site_dir / "index.html"
    index_path.write_text("<html>static</html>", encoding="utf-8")

    assert prepare_legacy_pages(site_dir) is False
    assert index_path.read_text(encoding="utf-8") == "<html>static</html>"


def test_prepare_legacy_pages_rejects_unexpected_legacy_template(tmp_path):
    site_dir = tmp_path / "legacy"
    site_dir.mkdir()
    (site_dir / "shinylive-sw.js").write_text("", encoding="utf-8")
    (site_dir / "index.html").write_text("<html>unexpected</html>", encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected startup block"):
        prepare_legacy_pages(site_dir)
