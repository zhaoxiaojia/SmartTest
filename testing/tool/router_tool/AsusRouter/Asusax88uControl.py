"""
Asusax88u control

This module is part of the AsusRouter package.
"""

from __future__ import annotations

from .AsusTelnetNvramControl import AsusTelnetNvramControl


class Asusax88uControl(AsusTelnetNvramControl):
    """
        Asusax88u control
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """

    def __init__(self, address: str | None = None):
        """
            Init
                Parameters
                ----------
                address : object
                    The router's login address or IP address; if None, a default is used.
                Returns
                -------
                None
                    This function does not return a value.
        """
        super().__init__('asus_88u', display=True, address=address)
