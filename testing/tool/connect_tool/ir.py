"""
Infrared (IR) control utilities.

This module defines a simple wrapper class around pytest's ``irsend`` fixture
for sending infrared (IR) codes.  It exposes an :class:`Ir` class that holds
a reference to the ``irsend`` fixture and provides methods to send codes with
an optional delay.
"""

import logging
import time

import pytest
from typing import Annotated


class Ir:
    """Wrapper around pytest.irsend to send IR codes to a configured device."""

    def __init__(self) -> None:
        """
        Initialize the :class:`Ir` instance.

        The constructor obtains a reference to the pytest ``irsend`` fixture and
        sets the target device name to an empty string.  Users should assign
        to :attr:`ir_name` before calling :meth:`send` to specify which
        configured device the IR codes should be sent to.
        """
        self.ir = pytest.irsend
        self.ir_name = ""

    def send(self, code: Annotated[object, "IR code to transmit"], wait_time: Annotated[float, "Delay in seconds after sending the code"] = 0) -> None:
        """
        Send an IR code through the configured device.

        Parameters
        ----------
        code : Any
            The IR code to be transmitted via the ``irsend`` fixture.
        wait_time : float, optional
            If provided and greater than zero, the method pauses execution
            for the specified number of seconds after sending the code.  This
            can be useful when chaining multiple IR transmissions that require
            a delay between them.
        """
        self.ir.send(self.ir_name, code)
        if wait_time:
            time.sleep(wait_time)
