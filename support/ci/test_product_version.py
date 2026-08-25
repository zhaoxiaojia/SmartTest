import json
import importlib.util
from pathlib import Path
import runpy

import pytest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SCRIPT = ROOT / "support/scripts/script-build-manifest.py"


def _manifest_module(tmp_path, version="2.3.4"):
    spec = importlib.util.spec_from_file_location("isolated_build_manifest", MANIFEST_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    version_path = tmp_path / "support/packaging/version.json"
    version_path.parent.mkdir(parents=True)
    version_path.write_text(json.dumps({"version": version}), encoding="utf-8")
    module.ROOT = tmp_path
    module.VERSION_PATH = version_path
    module.INSTALLER_VERSION_INCLUDE = tmp_path / "build/generated/installer_version.iss"
    module._git_commit = lambda: "deadbeef"
    return module, version_path


def test_repeated_manifest_generation_keeps_product_version_stable(tmp_path):
    module, version_path = _manifest_module(tmp_path)
    original = version_path.read_bytes()

    module.main()
    first_manifest = json.loads((tmp_path / "build/generated/build_manifest.json").read_text())
    module.main()
    second_manifest = json.loads((tmp_path / "build/generated/build_manifest.json").read_text())

    assert version_path.read_bytes() == original
    assert first_manifest["version"] == second_manifest["version"] == "2.3.4"
    assert 'SmartTestAppVersion "2.3.4"' in (
        tmp_path / "build/generated/installer_version.iss"
    ).read_text()


@pytest.mark.parametrize("version", ["1.2", "v1.2.3", "1.2.3.4", "1.2.x", ""])
def test_product_version_requires_exact_semver_triplet(tmp_path, version):
    module, _ = _manifest_module(tmp_path, version)
    with pytest.raises(ValueError, match="MAJOR.MINOR.PATCH"):
        module._load_version()


def test_release_tag_must_exactly_match_product_version(tmp_path):
    module, _ = _manifest_module(tmp_path)
    assert module.validate_release_tag("v2.3.4") == "2.3.4"
    with pytest.raises(ValueError, match="does not match"):
        module.validate_release_tag("v2.3.5")


def test_three_package_consumers_use_the_shared_version(tmp_path):
    tool = runpy.run_path(str(ROOT / "support/scripts/script-build-tool-portable.py"))
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    assert tool["create_portable_zip"](
        runtime, "2.3.4", tmp_path
    ).name == "SmartTestTool-2.3.4-windows-x64.zip"

    gradle = (ROOT / "mobile/android/app/build.gradle.kts").read_text(encoding="utf-8")
    assert "support/packaging/version.json" in gradle
    assert "versionName = productVersion" in gradle


def test_release_workflow_validates_tag_before_environment_and_packaging():
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    validation = "script-build-manifest.py --check-tag"
    assert validation in workflow
    assert workflow.index(validation) < workflow.index("script-init-venv.py")
    assert workflow.index(validation) < workflow.index("package all")
