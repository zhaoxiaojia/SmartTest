from __future__ import annotations

import os
from pathlib import Path
import tempfile

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE


def clean_excel_value(value):
    return ILLEGAL_CHARACTERS_RE.sub("", value) if isinstance(value, str) else value


def write_excel_workbook(output_path, populate) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    populate(workbook)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{target.stem}-", suffix=".tmp", dir=target.parent,
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        workbook.save(temporary)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target.resolve()
