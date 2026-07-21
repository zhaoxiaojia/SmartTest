from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[3]


def test_shared_modules_are_owned_by_support_package():
    import support.logging
    import support.param_conversion
    import support.report

    assert support.logging.__file__
    assert support.param_conversion.__file__
    assert support.report.__file__
    assert importlib.util.find_spec("tools") is None


def test_packaging_owns_support_paths_only():
    package_spec = ROOT / "support/packaging/pyinstaller/main.spec"
    source = package_spec.read_text(encoding="utf-8")

    assert 'os.path.join(repo_root, "support")' in source
    assert 'support_root,\n            "support"' in source
    assert 'os.path.join(repo_root, "tools")' not in source
    assert 'support_root,\n            "tools"' not in source
    assert (ROOT / "support/scripts/script-build-manifest.py").is_file()
    assert (ROOT / "support/packaging/version.json").is_file()


def test_personnel_config_is_packaged_at_runtime_config_path(tmp_path):
    package_spec = ROOT / "support/packaging/pyinstaller/main.spec"
    module = ast.parse(package_spec.read_text(encoding="utf-8"))
    assignments = {
        target.id: node.value
        for node in module.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert ast.unparse(assignments["personnel_config"]) == (
        "os.path.join(repo_root, 'config', 'personnel.json')"
    )

    analysis = assignments["a"]
    datas = next(keyword.value for keyword in analysis.keywords if keyword.arg == "datas")
    personnel_mapping = next(
        item
        for item in datas.elts
        if isinstance(item, ast.Tuple)
        and isinstance(item.elts[0], ast.Name)
        and item.elts[0].id == "personnel_config"
    )
    assert ast.literal_eval(personnel_mapping.elts[1]) == "config"

    source = ROOT / "config/personnel.json"
    packaged_runtime_file = tmp_path / "SmartTest/config" / source.name
    packaged_runtime_file.parent.mkdir(parents=True)
    shutil.copy2(source, packaged_runtime_file)
    assert packaged_runtime_file.is_file()


def test_support_build_owners_have_no_removed_repository_paths():
    owners = [
        path
        for owner in (ROOT / "support/scripts", ROOT / "support/packaging")
        for path in owner.rglob("*")
        if path.is_file() and path.suffix.lower() in {".py", ".ps1", ".spec", ".iss", ".md"}
    ]
    stale_pattern = re.compile(r"tools[\\/]?(?:scripts|packaging)|[\"']tools[\"']\s*/\s*[\"'](?:scripts|packaging)[\"']")
    stale = {
        str(path.relative_to(ROOT)): [
            (line_number, line.strip())
            for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1)
            if stale_pattern.search(line)
        ]
        for path in owners
    }

    assert {path: rows for path, rows in stale.items() if rows} == {}
