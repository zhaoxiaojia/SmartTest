from __future__ import annotations

from typing import Any, Mapping

from testing.params.contracts import required_param_keys


def required_params_for_case(case: Mapping[str, Any]) -> list[str]:
    return required_param_keys(case)
