"""Repository-level SmartTest check and packaging orchestrator."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = ("client", "web", "mobile")


def _python() -> str:
    candidate = ROOT / ".venv" / (
        "Scripts/python.exe" if sys.platform.startswith("win") else "bin/python"
    )
    return str(candidate) if candidate.exists() else sys.executable


def _product_script(action: str, product: str) -> Path:
    return ROOT / product / "scripts" / f"{action}.py"


def _run(command, *, runner=subprocess.run):
    runner([str(part) for part in command], cwd=str(ROOT), check=True)


def run_for_products(action: str, target: str, *, runner=subprocess.run) -> None:
    products = PRODUCTS if target == "all" else (target,)
    if action == "check":
        _run(
            [_python(), str(ROOT / "core/devtools/ci/check_product_boundaries.py")],
            runner=runner,
        )
    for product in products:
        print(f"[{action}] {product}")
        _run([_python(), str(_product_script(action, product))], runner=runner)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "package"):
        command_parser = commands.add_parser(command)
        command_parser.add_argument("target", choices=(*PRODUCTS, "all"))
    return parser


def main(argv=None, runner=subprocess.run) -> int:
    args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    run_for_products(args.command, args.target, runner=runner)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
