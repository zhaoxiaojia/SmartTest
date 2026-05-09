from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import sys


CATALOG_RELATIVE_PATH = Path(
    "android_client",
    "app",
    "src",
    "main",
    "java",
    "com",
    "smarttest",
    "mobile",
    "runner",
    "SmartTestCatalog.kt",
)


def _catalog_path() -> Path:
    packaged_root = getattr(sys, "_MEIPASS", None)
    if packaged_root:
        packaged_path = Path(packaged_root) / CATALOG_RELATIVE_PATH
        if packaged_path.exists():
            return packaged_path
    return Path(__file__).resolve().parents[2] / CATALOG_RELATIVE_PATH


@dataclass(frozen=True)
class AndroidCatalogParam:
    case_id: str
    param_id: str
    label: str
    hint: str
    default_value: str


@dataclass(frozen=True)
class AndroidStepTemplate:
    case_id: str
    template_id: str
    title: str
    kind: str
    definition_id: str
    repeat_param: str
    when_param: str


def _extract_balanced_block(text: str, start_index: int) -> tuple[str, int]:
    depth = 0
    index = start_index
    while index < len(text):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1], index + 1
        index += 1
    raise ValueError("Unbalanced Kotlin block while parsing SmartTestCatalog.kt")


def _extract_string_argument(block: str, marker: str) -> str:
    start = block.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = block.find('"', start)
    if end < 0:
        return ""
    return block[start:end]


def _extract_parameter_blocks(case_block: str) -> list[str]:
    parameters_marker = "parameters = listOf("
    start = case_block.find(parameters_marker)
    if start < 0:
        return []
    start = case_block.find("(", start)
    if start < 0:
        return []
    params_block, _ = _extract_balanced_block(case_block, start)
    blocks: list[str] = []
    search_from = 0
    while True:
        idx = params_block.find("TestParameterDefinition(", search_from)
        if idx < 0:
            break
        block_start = params_block.find("(", idx)
        param_block, block_end = _extract_balanced_block(params_block, block_start)
        blocks.append(param_block)
        search_from = block_end
    return blocks


def _extract_step_template_blocks(case_block: str) -> list[str]:
    marker = "stepTemplates = listOf("
    start = case_block.find(marker)
    if start < 0:
        return []
    start = case_block.find("(", start)
    if start < 0:
        return []
    templates_block, _ = _extract_balanced_block(case_block, start)
    blocks: list[str] = []
    search_from = 0
    while True:
        idx = templates_block.find("TestStepTemplate(", search_from)
        if idx < 0:
            break
        block_start = templates_block.find("(", idx)
        template_block, block_end = _extract_balanced_block(templates_block, block_start)
        blocks.append(template_block)
        search_from = block_end
    return blocks


def _extract_template_value(block: str, name: str, position: int, default: str = "") -> str:
    named = _extract_string_argument(block, f'{name} = "')
    if named:
        return named
    has_named_arguments = any(
        f"{candidate} =" in block
        for candidate in ("id", "title", "kind", "definitionId", "repeatParam", "whenParam")
    )
    if has_named_arguments:
        return default
    values: list[str] = []
    cursor = 0
    while True:
        quote_start = block.find('"', cursor)
        if quote_start < 0:
            break
        quote_end = block.find('"', quote_start + 1)
        if quote_end < 0:
            break
        values.append(block[quote_start + 1 : quote_end])
        cursor = quote_end + 1
    if len(values) > position:
        return values[position]
    return default


def _iter_case_blocks() -> list[tuple[str, str]]:
    text = _catalog_path().read_text(encoding="utf-8")
    cases: list[tuple[str, str]] = []
    search_from = 0
    while True:
        idx = text.find("TestCaseDefinition(", search_from)
        if idx < 0:
            break
        block_start = text.find("(", idx)
        case_block, block_end = _extract_balanced_block(text, block_start)
        search_from = block_end
        case_id = _extract_string_argument(case_block, 'id = "')
        if case_id:
            cases.append((case_id, case_block))
    return cases


@lru_cache(maxsize=1)
def load_android_catalog_params() -> dict[str, AndroidCatalogParam]:
    params: dict[str, AndroidCatalogParam] = {}
    for case_id, case_block in _iter_case_blocks():
        for param_block in _extract_parameter_blocks(case_block):
            values: list[str] = []
            cursor = 0
            while True:
                quote_start = param_block.find('"', cursor)
                if quote_start < 0:
                    break
                quote_end = param_block.find('"', quote_start + 1)
                if quote_end < 0:
                    break
                values.append(param_block[quote_start + 1 : quote_end])
                cursor = quote_end + 1
            if len(values) < 4:
                continue
            param_id, label, hint, default_value = values[:4]
            params[f"{case_id}:{param_id}"] = AndroidCatalogParam(
                case_id=case_id,
                param_id=param_id,
                label=label,
                hint=hint,
                default_value=default_value,
            )
    return params


@lru_cache(maxsize=1)
def load_android_step_templates() -> dict[str, list[AndroidStepTemplate]]:
    templates: dict[str, list[AndroidStepTemplate]] = {}
    for case_id, case_block in _iter_case_blocks():
        case_templates: list[AndroidStepTemplate] = []
        for block in _extract_step_template_blocks(case_block):
            template_id = _extract_template_value(block, "id", 0)
            title = _extract_template_value(block, "title", 1)
            if not template_id or not title:
                continue
            case_templates.append(
                AndroidStepTemplate(
                    case_id=case_id,
                    template_id=template_id,
                    title=title,
                    kind=_extract_template_value(block, "kind", 2, "step") or "step",
                    definition_id=_extract_template_value(block, "definitionId", 3, template_id) or template_id,
                    repeat_param=_extract_template_value(block, "repeatParam", 4),
                    when_param=_extract_template_value(block, "whenParam", 5),
                )
            )
        templates[case_id] = case_templates
    return templates


def android_catalog_param(key: str) -> AndroidCatalogParam:
    try:
        return load_android_catalog_params()[key]
    except KeyError as exc:
        raise KeyError(f"Parameter '{key}' was not found in Android SmartTestCatalog.kt") from exc
