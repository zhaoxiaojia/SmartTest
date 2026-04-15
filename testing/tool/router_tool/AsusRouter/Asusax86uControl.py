"""Asusax86u telnet control
This module is part of the AsusRouter package."""

from __future__ import annotations
from .AsusTelnetNvramControl import AsusTelnetNvramControl


class Asusax86uControl(AsusTelnetNvramControl):
    """
    ASUS RT-AX86U Telnet NVRAM controller.

    This class enables fast and reliable configuration of the ASUS RT-AX86U
    router via Telnet using NVRAM commands, assuming compatibility with
    the AX88U/AX88U Pro command structure.

    Parameters
    ----------
    address : str | None
        The router's IP address. If None, defaults to '192.168.50.1'.

    Returns
    -------
    None
        This function does not return a value.
    """

    def __init__(self, address: str | None = None) -> None:
        """
        Initialize the ASUS RT-AX86U Telnet controller.

        Uses the generic 'asus_86u' identifier. Since we assume full NVRAM
        compatibility with AX88U, no special bandwidth or channel mappings
        are required beyond the base class.
        """
        super().__init__('asus_86u', display=False, address=address)
