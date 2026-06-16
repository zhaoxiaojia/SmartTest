"""Wi-Fi lab related tools.

Submodules are loaded lazily because some controllers depend on optional lab
software that is not installed on every SmartTest runtime.
"""

__all__ = ["LabDeviceController", "ix"]


def __getattr__(name):
    if name == "LabDeviceController":
        from .lab_device_controller import LabDeviceController

        return LabDeviceController
    if name == "ix":
        from .ixchariot import ix

        return ix
    raise AttributeError(name)
