from __future__ import annotations

import asyncio
from pathlib import Path

from support.browser_automation import BrowserRuntime


async def _render(source: Path, output: Path) -> None:
    runtime = BrowserRuntime(headless=True)
    try:
        session = await runtime.context("report-render", "local-html")
        page = await session.new_page()
        try:
            await page.goto(source.resolve().as_uri(), wait_until="networkidle")
            await page.evaluate("document.fonts.ready")
            await page.screenshot(path=str(output), full_page=True)
        finally:
            await page.close()
    finally:
        await runtime.close()


def render_html_page_image(source: str | Path, output: str | Path) -> Path:
    source, output = Path(source), Path(output)
    if not source.is_file(): raise FileNotFoundError(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_render(source, output))
    return output
