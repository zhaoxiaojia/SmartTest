from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from subprocess import run

import pytest
from PySide6.QtCore import QTranslator

from support.scripts import env


ROOT = Path(__file__).resolve().parents[3]
OWNED_CONTEXTS = {
    "AISettingsBridge",
    "JiraAuditBridge",
    "JiraAuditWorkspace",
    "T_Settings",
    "ToolBridge",
}


def _catalog(path: Path) -> dict[str, dict[str, ET.Element]]:
    return {
        context.findtext("name") or "": {
            message.findtext("source") or "": message.find("translation")
            for message in context.findall("message")
        }
        for context in ET.parse(path).getroot().findall("context")
    }


@pytest.fixture(scope="module")
def owned_sources(tmp_path_factory):
    generated = tmp_path_factory.mktemp("translations") / "owned.ts"
    run(
        [
            env.pyside6_lupdate(),
            str(ROOT / "ui/example/imports/resource.qrc"),
            str(ROOT / "ui/example/bridge/AISettingsBridge.py"),
            str(ROOT / "ui/example/bridge/JiraAuditBridge.py"),
            str(ROOT / "ui/example/bridge/ToolBridge.py"),
            "-ts",
            str(generated),
        ],
        check=True,
        cwd=ROOT,
    )
    catalog = _catalog(generated)
    return {
        context: set(catalog[context])
        for context in OWNED_CONTEXTS
    }


def _readable(text: str) -> bool:
    return bool(text and "\ufffd" not in text and text not in {"?", "??", "???"})


def test_owned_fixed_text_is_active_and_translated_in_both_catalogs(owned_sources):
    for filename in ("example_en_US.ts", "example_zh_CN.ts"):
        catalog = _catalog(ROOT / "ui/example" / filename)
        for context, sources in owned_sources.items():
            for source in sources:
                translation = catalog.get(context, {}).get(source)
                assert translation is not None, f"{filename}: missing {context}/{source}"
                assert translation.get("type") not in {
                    "unfinished",
                    "vanished",
                    "obsolete",
                }
                assert _readable((translation.text or "").strip())


def test_owned_runtime_qm_translations_are_active_and_readable(owned_sources):
    for locale in ("en_US", "zh_CN"):
        translator = QTranslator()
        qm_path = ROOT / "ui/example/imports/example/i18n" / f"example_{locale}.qm"
        assert translator.load(str(qm_path)), f"failed to load {qm_path}"
        for context, sources in owned_sources.items():
            for source in sources:
                assert _readable(translator.translate(context, source).strip())
