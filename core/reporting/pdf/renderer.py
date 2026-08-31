from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QUrl


class PdfRenderError(RuntimeError):
    pass


class _PagePdfAdapter:
    def __init__(self, output_path: Path):
        self.output_path = Path(output_path)
        self._done = False
        self._error = ""

    def load_finished(self, success: bool):
        if not success:
            self._finish("Failed to load report HTML.")

    def print_finished(self, path: str, success: bool):
        self._finish("" if success else f"Qt failed to write PDF: {path}")

    def timeout(self):
        self._finish("Timed out exporting PDF.")

    def _finish(self, error: str):
        if not self._done:
            self._done = True
            self._error = error

    def result(self) -> Path:
        if not self._done:
            raise PdfRenderError("PDF rendering did not finish.")
        if self._error:
            raise PdfRenderError(self._error)
        return self.output_path


def render_html_to_pdf(
    html: str,
    output_path: Path,
    *,
    base_url: QUrl | None = None,
    timeout_ms: int = 30_000,
) -> Path:
    try:
        from PySide6.QtCore import QEventLoop, QTimer, QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWebEngineCore import QWebEnginePage
        from PySide6.QtWebEngineQuick import QtWebEngineQuick
    except ImportError as exc:
        raise PdfRenderError(
            "PDF export requires PySide6 QtWebEngine in the SmartTest runtime.",
        ) from exc

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    app = QGuiApplication.instance()
    owns_app = app is None
    if owns_app:
        QtWebEngineQuick.initialize()
        app = QGuiApplication([])

    page = QWebEnginePage()
    loop = QEventLoop()
    try:
        return _render_page_to_pdf(
            page, loop, html, base_url or QUrl(), path, timeout_ms,
            QTimer.singleShot,
        )
    finally:
        page.deleteLater()
        if owns_app:
            app.quit()


def _render_page_to_pdf(
    page,
    loop,
    html: str,
    base_url,
    output_path: Path,
    timeout_ms: int,
    schedule_timeout,
) -> Path:
    adapter = _PagePdfAdapter(output_path)
    def finish():
        if loop.isRunning():
            loop.quit()

    def printed(pdf_path: str, success: bool):
        adapter.print_finished(pdf_path, success)
        finish()

    def loaded(success: bool):
        adapter.load_finished(success)
        if not success:
            finish()
            return
        page.pdfPrintingFinished.connect(printed)
        page.printToPdf(str(output_path))

    def timed_out():
        adapter.timeout()
        finish()

    page.loadFinished.connect(loaded)
    schedule_timeout(int(timeout_ms), timed_out)
    page.setHtml(str(html), base_url)
    loop.exec()
    return adapter.result()
