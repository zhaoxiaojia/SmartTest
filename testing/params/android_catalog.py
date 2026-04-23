from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "android_client"
    / "app"
    / "src"
    / "main"
    / "java"
    / "com"
    / "smarttest"
    / "mobile"
    / "runner"
    / "SmartTestCatalog.kt"
)


@dataclass(frozen=True)
class AndroidCatalogParam:
    case_id: str
    param_id: str
    label: str
    hint: str
    default_value: str


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


@lru_cache(maxsize=1)
def load_android_catalog_params() -> dict[str, AndroidCatalogParam]:
    text = CATALOG_PATH.read_text(encoding="utf-8")
    params: dict[str, AndroidCatalogParam] = {}
    search_from = 0
    while True:
        idx = text.find("TestCaseDefinition(", search_from)
        if idx < 0:
            break
        block_start = text.find("(", idx)
        case_block, block_end = _extract_balanced_block(text, block_start)
        search_from = block_end
        case_id = _extract_string_argument(case_block, 'id = "')
        if not case_id:
            continue
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


def android_catalog_param(key: str) -> AndroidCatalogParam:
    try:
        return load_android_catalog_params()[key]
    except KeyError as exc:
        raise KeyError(f"Parameter '{key}' was not found in Android SmartTestCatalog.kt") from exc
