from __future__ import annotations


class FeatureBase:
    def __init__(self, dut) -> None:
        self.dut = dut

    def __getattr__(self, name: str):
        return getattr(self.dut, name)
