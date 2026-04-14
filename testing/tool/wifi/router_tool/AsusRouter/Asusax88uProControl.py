"""
Asusax88u pro control

This module is part of the AsusRouter package.
"""

from __future__ import annotations

from .AsusTelnetNvramControl import AsusTelnetNvramControl


class Asusax88uProControl(AsusTelnetNvramControl):
    """
        Asusax88u pro control
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """
    CHANNEL_5 = ['auto', '36', '40', '44', '48', '52', '56', '60', '64', '100', '104', '108', '112', '116',
                 '120', '124', '128', '132', '136', '140', '144', '149', '153', '157', '161', '165', '169',
                 '173', '177']

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
        super().__init__('asus_88u_pro', display=True, address=address)
