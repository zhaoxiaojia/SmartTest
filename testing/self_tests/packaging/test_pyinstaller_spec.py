from pathlib import Path
import runpy


class _AnalysisStub:
    def __init__(self, scripts, pathex=None, binaries=None, datas=None, **kwargs):
        self.scripts = scripts
        self.pathex = pathex or []
        self.binaries = list(binaries or [])
        self.datas = list(datas or [])
        self.pure = []


def _identity_stub(*args, **kwargs):
    return {"args": args, "kwargs": kwargs}


def test_pyinstaller_datas_include_project_runtime_packages(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    monkeypatch.setenv("SMARTTEST_REPO_ROOT", str(repo_root))

    namespace = runpy.run_path(
        str(repo_root / "tools" / "packaging" / "pyinstaller" / "main.spec"),
        init_globals={
            "Analysis": _AnalysisStub,
            "PYZ": _identity_stub,
            "EXE": _identity_stub,
            "COLLECT": _identity_stub,
            "BUNDLE": _identity_stub,
        },
    )

    datas = {
        (Path(source).resolve(), Path(destination).as_posix())
        for source, destination in namespace["a"].datas
    }
    expected = {
        repo_root / "ui": "ui",
        repo_root / "testing": "testing",
        repo_root / "AI": "AI",
        repo_root / "jira_tool": "jira_tool",
    }

    missing = [
        f"{source} -> {destination}"
        for source, destination in expected.items()
        if (source.resolve(), destination) not in datas
    ]
    assert not missing
