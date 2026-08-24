from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support.ci.check_product_boundaries import (
    ANDROID_RULES,
    _check_active_android_rules,
    _check_android_location,
    _check_core,
    _check_web_frontend,
)


class ProductBoundaryCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        for product in ("client", "core", "web", "mobile"):
            (self.root / product).mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_core_allows_internal_and_standard_library_imports(self) -> None:
        self._write("core/pkg/module.py", "import json\nfrom . import local\nfrom ..contracts import Event\n")

        self.assertEqual(_check_core(self.root), [])

    def test_core_rejects_absolute_and_escaping_relative_imports(self) -> None:
        self._write("core/absolute.py", "from client.app import main\nimport mobile.runner\n")
        self._write("core/pkg/relative.py", "from ...web.backend import api\n")
        self._write("core/direct_relative.py", "from .. import client\n")

        failures = _check_core(self.root)

        self.assertEqual(len(failures), 3)
        self.assertEqual(sum("client" in failure for failure in failures), 2)
        self.assertTrue(any("mobile" in failure for failure in failures))
        self.assertTrue(any("web" in failure for failure in failures))

    def test_web_frontend_allows_api_and_local_imports(self) -> None:
        self._write("web/frontend/src/page.ts", "import api from './api'\nconst view = import('./view')\n")

        self.assertEqual(_check_web_frontend(self.root), [])

    def test_web_frontend_rejects_supported_core_import_forms(self) -> None:
        self._write(
            "web/frontend/src/page.ts",
            "\n".join(
                (
                    "import value from '../../../core/value'",
                    "import '../../../core/setup'",
                    "const lazy = import('../../../core/lazy')",
                    "const legacy = require('../../../core/legacy')",
                )
            ),
        )

        failures = _check_web_frontend(self.root)

        self.assertEqual(len(failures), 4)

    def test_android_project_accepts_only_mobile_location(self) -> None:
        self._write("mobile/android/settings.gradle.kts", "")
        self._write("mobile/android/app/build.gradle.kts", "")
        self._write("mobile/android/gradlew.bat", "")

        self.assertEqual(_check_android_location(self.root), [])

    def test_android_project_rejects_legacy_or_incomplete_location(self) -> None:
        (self.root / "android_client").mkdir()

        failures = _check_android_location(self.root)

        self.assertEqual(len(failures), 4)
        self.assertTrue(any("legacy Android product path" in failure for failure in failures))

    def test_active_android_rules_use_mobile_path(self) -> None:
        for relative, required in ANDROID_RULES.items():
            self._write(relative, required)

        self.assertEqual(_check_active_android_rules(self.root), [])

    def test_active_android_rules_reject_legacy_path(self) -> None:
        for relative, required in ANDROID_RULES.items():
            self._write(relative, required)
        self._write("AGENTS.md", "mobile/android/**\nandroid_client/app\n")

        failures = _check_active_android_rules(self.root)

        self.assertEqual(failures, ["AGENTS.md: contains legacy Android filesystem path"])


if __name__ == "__main__":
    unittest.main()
