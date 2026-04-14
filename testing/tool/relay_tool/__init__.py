#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: __init__.py.py 
@time: 11/13/2025 10:57 AM 
@desc: 
'''

from abc import ABC, abstractmethod
import logging
from typing import Any, Sequence

__all__ = ["Relay", "get_relay_controller"]


class Relay(ABC):
    """Common ABC for relay controllers."""

    def __init__(self, port: Any | None = None) -> None:
        """Store optional default port metadata."""
        self.port = port

    @abstractmethod
    def pulse(self, direction: str = "power_off", *, port: Any | None = None, **kwargs) -> None:
        """Toggle a single relay contact."""
        raise NotImplementedError


def get_relay_controller(
    relay_type: str | None,
    relay_params: Sequence[Any] | None = None,
    **kwargs: Any,
) -> Relay | None:
    """Instantiate a relay controller matching the requested type.

    Parameters:
        relay_type: Identifier such as ``"usb_relay"`` or ``"GWGJ-XC3012"``.
        relay_params: Optional parameter list serialized from the UI.
        **kwargs: Extra keyword arguments like ``port`` or ``mode``.

    Returns:
        Relay | None: A ready-to-use controller instance or ``None`` when
        configuration is incomplete or the type is unknown.
    """

    relay_key = (relay_type or "").strip().lower()
    if not relay_key:
        return None

    if relay_key == "usb_relay":
        from .usb_relay_controller import UsbRelayController

        port = kwargs.get("port")
        if not port:
            return None
        mode = str(kwargs.get("mode", "NO") or "NO").strip() or "NO"
        press_seconds = kwargs.get("press_seconds")
        return UsbRelayController(str(port), mode=mode, press_seconds=press_seconds)

    if relay_key == "gwgj-xc3012":
        from .pdusnmp import power_ctrl

        params = relay_params or ()
        ip = ""
        relay_port: int | None = None
        if params:
            ip = str(params[0]).strip()
        if len(params) > 1:
            try:
                relay_port = int(str(params[1]).strip())
            except (TypeError, ValueError):
                relay_port = None
        default_port = (ip, relay_port) if ip and relay_port is not None else None
        return power_ctrl(default_port)

    logging.warning("Unknown relay type: %s", relay_type)
    return None
