from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.devtools.ci.check_product_boundaries import (
    ANDROID_RULES,
    CORE_RULES,
    DESKTOP_RULES,
    LOGGING_RULES,
    _check_active_android_rules,
    _check_active_desktop_rules,
    _check_android_location,
    _check_core,
    _check_core_location,
    _check_active_core_rules,
    _check_desktop_location,
    _check_web_frontend,
    _check_root_legacy_locations,
    _check_logging_boundaries,
    _check_active_logging_rules,
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

    def test_root_location_rejects_retired_owners_and_outputs(self) -> None:
        for relative in ("AI", "debug", "tools", "dist_installer", "dist_tool", ".superpowers"):
            (self.root / relative).mkdir()
        self._write("demo_outlook.py", "")

        self.assertEqual(len(_check_root_legacy_locations(self.root)), 7)

    def test_core_rejects_absolute_and_escaping_relative_imports(self) -> None:
        self._write("core/absolute.py", "from client.app import main\nimport mobile.runner\n")
        self._write("core/pkg/relative.py", "from ...web.backend import api\n")
        self._write("core/direct_relative.py", "from .. import client\n")

        failures = _check_core(self.root)

        self.assertEqual(len(failures), 3)
        self.assertEqual(sum("client" in failure for failure in failures), 2)
        self.assertTrue(any("mobile" in failure for failure in failures))
        self.assertTrue(any("web" in failure for failure in failures))

    def test_core_location_accepts_unique_new_owners(self) -> None:
        self._write("core/testing/__init__.py", "")
        self._write("core/tools/__init__.py", "")
        self._write("core/jira/__init__.py", "")
        self._write("core/config/personnel.json", "{}")

        self.assertEqual(_check_core_location(self.root), [])

    def test_core_location_rejects_legacy_or_incomplete_owners(self) -> None:
        (self.root / "testing").mkdir()

        failures = _check_core_location(self.root)

        self.assertEqual(len(failures), 5)
        self.assertTrue(any("legacy core owner path" in failure for failure in failures))

    def test_active_core_rules_use_new_owner_paths(self) -> None:
        for relative, required in CORE_RULES.items():
            self._write(relative, required)

        self.assertEqual(_check_active_core_rules(self.root), [])

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

    def test_desktop_product_accepts_only_client_location(self) -> None:
        self._write("client/app/main.py", "")
        self._write("client/app/ui/__init__.py", "")

        self.assertEqual(_check_desktop_location(self.root), [])

    def test_desktop_product_rejects_legacy_or_incomplete_location(self) -> None:
        self._write("main.py", "")
        (self.root / "ui").mkdir()

        self.assertEqual(len(_check_desktop_location(self.root)), 4)

    def test_active_desktop_rules_use_client_path(self) -> None:
        for relative, required in DESKTOP_RULES.items():
            self._write(relative, required)

        self.assertEqual(_check_active_desktop_rules(self.root), [])

    def test_active_desktop_rules_require_new_entrypoint(self) -> None:
        for relative, required in DESKTOP_RULES.items():
            self._write(relative, required)
        self._write(".codex/skills/smarttest-ui-workflow/SKILL.md", "client/app/main.py\npython main.py")

        failures = _check_active_desktop_rules(self.root)

        self.assertEqual(
            failures,
            [".codex/skills/smarttest-ui-workflow/SKILL.md: contains legacy desktop filesystem path"],
        )

    def test_logging_boundary_rejects_legacy_private_and_direct_android_logging(self) -> None:
        self._write("client/app/a.py", "from support.logging import smart_log\n")
        self._write("web/backend/private.py", "import logging\nlog = logging.getLogger(__name__)\n")
        self._write("core/runtime.py", "print('temporary')\n")
        self._write("mobile/android/app/src/main/java/com/smarttest/mobile/Feature.kt", "import android.util.Log\nfun x() = Log.i(\"x\", \"y\")\n")
        failures = _check_logging_boundaries(self.root)
        self.assertEqual(len(failures), 4)

    def test_logging_boundary_allows_unique_owners(self) -> None:
        self._write("core/logging/logger.py", "import logging\nlog = logging.getLogger(__name__)\n")
        self._write("client/app/a.py", "from core.logging import smart_log\n")
        self._write("mobile/android/app/src/main/java/com/smarttest/mobile/logging/SmartTestLog.kt", "import android.util.Log\nfun x() = Log.i(\"x\", \"y\")\n")
        self.assertEqual(_check_logging_boundaries(self.root), [])

    def test_active_logging_rules_reject_retired_owner(self) -> None:
        for relative, required in LOGGING_RULES.items():
            self._write(relative, required)
        self._write(
            ".codex/skills/smarttest-testing-workflow/SKILL.md",
            "core.logging\nsupport.logging\n",
        )
        self.assertEqual(
            _check_active_logging_rules(self.root),
            [
                ".codex/skills/smarttest-testing-workflow/SKILL.md: "
                "contains retired logging owner"
            ],
        )


if __name__ == "__main__":
    unittest.main()
