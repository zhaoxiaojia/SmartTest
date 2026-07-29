from __future__ import annotations

from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[3]
QML_ROOT = ROOT / "ui/example/imports/example/qml"
APP_QML = QML_ROOT / "App.qml"
NATIVE_EDITABLE_TYPES = (
    "FluTextBox",
    "FluMultilineTextBox",
    "FluComboBox",
    "FluCheckBox",
    "FluToggleSwitch",
    "FluSpinBox",
    "FluPasswordBox",
    "FluAutoSuggestBox",
)
NATIVE_EDITABLE = re.compile(
    rf"(?m)^[ \t]*(?:[A-Za-z_]\w*\s*:\s*)?"
    rf"(?P<type>{'|'.join(NATIVE_EDITABLE_TYPES)})\s*\{{"
)
OPT_OUT = re.compile(
    r"^\s*/\*\s*persistence-opt-out:\s*"
    r"(?:sensitive|transient|owner:[A-Za-z][A-Za-z0-9_.-]*)\s*\*/"
)
DEMO_FILE_MARKER = "persistence-scan: demo"


def _code_mask(source: str) -> str:
    masked = list(source)
    state = "code"
    quote = ""
    index = 0
    while index < len(source):
        char = source[index]
        pair = source[index : index + 2]
        if state == "code":
            if pair == "//":
                masked[index : index + 2] = "  "
                state = "line-comment"
                index += 2
                continue
            if pair == "/*":
                masked[index : index + 2] = "  "
                state = "block-comment"
                index += 2
                continue
            if char in "\"'":
                masked[index] = " "
                quote = char
                state = "string"
        elif state == "line-comment":
            if char == "\n":
                state = "code"
            else:
                masked[index] = " "
        elif state == "block-comment":
            masked[index] = " "
            if pair == "*/":
                masked[index : index + 2] = "  "
                state = "code"
                index += 2
                continue
        else:
            masked[index] = " "
            if char == "\\":
                if index + 1 < len(source):
                    masked[index + 1] = " "
                    index += 2
                    continue
            elif char == quote:
                state = "code"
        index += 1
    return "".join(masked)


def _qml_blocks(source: str, pattern: re.Pattern[str]):
    masked = _code_mask(source)
    depths = []
    depth = 0
    for char in masked:
        depths.append(depth)
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1

    for match in pattern.finditer(masked):
        opening = masked.find("{", match.start(), match.end())
        depth = 1
        closing = opening + 1
        while closing < len(masked) and depth:
            if masked[closing] == "{":
                depth += 1
            elif masked[closing] == "}":
                depth -= 1
            closing += 1
        yield (
            match,
            depths[match.start()],
            source[match.start() : closing],
            source.count("\n", 0, match.start()) + 1,
        )


def _business_qml_paths(qml_root: Path) -> tuple[Path, ...]:
    paths = set()
    app = qml_root / "App.qml"
    if app.exists():
        paths.add(app)

    component_root = qml_root / "component"
    if component_root.exists():
        paths.update(
            path
            for path in component_root.rglob("*.qml")
            if "persistence" not in path.relative_to(component_root).parts
        )

    window_root = qml_root / "window"
    if window_root.exists():
        paths.update(window_root.glob("*.qml"))

    navigation_files = (
        qml_root / "global/ItemsOriginal.qml",
        qml_root / "global/ItemsFooter.qml",
    )
    for navigation in navigation_files:
        if not navigation.exists():
            continue
        source = navigation.read_text(encoding="utf-8-sig")
        pane_item = re.compile(r"(?m)^[ \t]*FluPaneItem\s*\{")
        for _match, depth, block, _line in _qml_blocks(source, pane_item):
            if depth != 1:
                continue
            url = re.search(
                r'url:\s*"qrc:/example/qml/(?P<path>[^"]+\.qml)"',
                block,
            )
            if url:
                paths.add(qml_root / url.group("path"))

    return tuple(
        sorted(
            path
            for path in paths
            if path.exists()
            and DEMO_FILE_MARKER
            not in path.read_text(encoding="utf-8-sig")
        )
    )


def _native_editable_violations(path: Path, qml_root: Path):
    source = path.read_text(encoding="utf-8-sig")
    for match, _depth, block, line in _qml_blocks(source, NATIVE_EDITABLE):
        header_end = source.find("\n", match.end())
        if header_end < 0:
            header_end = len(source)
        header = source[match.end() : header_end]
        if not OPT_OUT.match(header):
            yield (
                f"{path.relative_to(qml_root).as_posix()}:{line}: "
                f"{match.group('type')}"
            )


def test_app_global_state_uses_the_shared_persistence_lifecycle():
    source = APP_QML.read_text(encoding="utf-8-sig")

    assert "Persistence.PersistBinding {" in source
    for forbidden in (
        "frontendStateReady",
        "restoreGlobalState",
        "FrontendStateBridge.restore(",
        "FrontendStateBridge.save(",
        "onStateContextChanged",
    ):
        assert forbidden not in source


def test_all_business_qml_uses_persistent_controls_or_explicit_opt_out():
    paths = _business_qml_paths(QML_ROOT)
    relative_paths = {path.relative_to(QML_ROOT).as_posix() for path in paths}
    assert "component/jiraaudit/JiraAuditWorkspace.qml" in relative_paths
    assert "page/T_Jira.qml" in relative_paths
    assert "page/T_TextBox.qml" not in relative_paths

    offenders = [
        offender
        for path in paths
        for offender in _native_editable_violations(path, QML_ROOT)
    ]

    assert offenders == [], "\n" + "\n".join(offenders)


@pytest.mark.parametrize("control_type", NATIVE_EDITABLE_TYPES)
def test_unlisted_native_business_input_is_rejected(
    tmp_path,
    control_type,
):
    qml_root = tmp_path / "qml"
    fixture = qml_root / "component/FutureBusinessControl.qml"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(
        f"import FluentUI 1.0\nItem {{\n    {control_type} {{}}\n}}\n",
        encoding="utf-8",
    )

    paths = _business_qml_paths(qml_root)

    assert paths == (fixture,)
    assert list(_native_editable_violations(fixture, qml_root)) == [
        f"component/FutureBusinessControl.qml:3: {control_type}"
    ]


def test_persistent_control_and_explicit_opt_out_satisfy_contract(tmp_path):
    qml_root = tmp_path / "qml"
    fixture = qml_root / "component/FutureBusinessControl.qml"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(
        """
import FluentUI 1.0
Item {
    Persistence.PersistTextBox {}
    FluTextBox { /* persistence-opt-out: transient */ }
    FluComboBox { /* persistence-opt-out: owner:RuntimeParameters */ }
    FluPasswordBox { /* persistence-opt-out: sensitive */ }
}
""",
        encoding="utf-8",
    )

    assert list(_native_editable_violations(fixture, qml_root)) == []


def test_nested_control_opt_out_does_not_exempt_parent(tmp_path):
    qml_root = tmp_path / "qml"
    fixture = qml_root / "component/FutureBusinessControl.qml"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(
        """
import FluentUI 1.0
FluTextBox {
    FluCheckBox { /* persistence-opt-out: transient */ }
}
""",
        encoding="utf-8",
    )

    assert list(_native_editable_violations(fixture, qml_root)) == [
        "component/FutureBusinessControl.qml:3: FluTextBox"
    ]
