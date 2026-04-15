"""Utilities for interacting with Ixia chassis via Tcl scripts.

This module defines a simple wrapper around the execution of a Tcl script used
to measure receiver sensitivity or throughput between pairs of endpoints.  It
encapsulates the details of constructing command lines, launching the script,
and parsing the output for summary statistics.  Consumers of this module can
instantiate the :class:`ix` class to run the script with different parameters
and to modify the underlying Tcl script as needed.
"""

import logging
import os
import re
from testing.tool.dut_tool import command_batch as subprocess
import time


class ix:
    """Represents a thin wrapper around an RVR Tcl script invocation.

    The ix class provides methods to execute a Tcl script that measures the
    average throughput between two endpoints and to modify the script on disk.
    It stores endpoint information and the path to the script as instance
    attributes.

    Parameters:
        ep1 (str, optional): The first endpoint identifier used by the script.
            Defaults to an empty string.
        ep2 (str, optional): The second endpoint identifier used by the script.
            Defaults to an empty string.
        pair (str, optional): The pairing name or identifier used by the script.
            Defaults to an empty string.
    """

    def __init__(self, ep1: str = "", ep2: str = "", pair: str = "") -> None:
        """Initialize a new ix instance.

        Parameters:
            ep1 (str, optional): The first endpoint identifier. If omitted,
                the instance will start with an empty value.
            ep2 (str, optional): The second endpoint identifier. If omitted,
                the instance will start with an empty value.
            pair (str, optional): An optional pairing identifier used by the
                Tcl script. Defaults to an empty string.
        """
        self.ep1 = ep1
        self.ep2 = ep2
        self.pair = pair
        # Default path to the Tcl script within the project tree.
        self.script_path = os.getcwd() + '/script/rvr.tcl'

    def run_rvr(self, ep1: str = "", ep2: str = "", pair: str = "") -> str | bool:
        """Execute the RVR Tcl script and return the measured average throughput.

        This method updates the instance attributes if new endpoint or pairing
        values are provided.  It then constructs a command line using the
        stored script path and endpoint identifiers and launches it in a
        subprocess.  After a fixed wait period the output is read and a
        regular expression is used to extract a floating-point "avg" value
        reported by the script.

        Parameters:
            ep1 (str, optional): Overrides the stored first endpoint identifier
                for this invocation. Defaults to the existing value.
            ep2 (str, optional): Overrides the stored second endpoint identifier
                for this invocation. Defaults to the existing value.
            pair (str, optional): Overrides the stored pairing identifier for
                this invocation. Defaults to the existing value.

        Returns:
            str | bool: The extracted average throughput as a string if found,
            otherwise ``False`` indicating that the script did not produce a
            parseable result.
        """
        if ep1:
            self.ep1 = ep1
        if ep2:
            self.ep2 = ep2
        if pair:
            self.pair = pair

        res = subprocess.Popen(
            f"tclsh {self.script_path} {self.ep1} {self.ep2} {self.pair}",
            shell=True,
            stdout=subprocess.PIPE,
            encoding='utf-8'
        )
        # Wait for the script to produce its output.
        time.sleep(40)
        info = res.stdout.read()
        logging.info(info)
        # Extract the first average value reported by the script, if any.
        date = re.findall(r'avg \d+\.\d+', info, re.S)
        return date[0] if date else False

    def modify_tcl_script(self, old_str: str, new_str: str) -> None:
        """Replace occurrences of a string within the Tcl script on disk.

        A backup of the original script is created with a ``.bak`` suffix
        before the modifications are written.  The backup is then removed
        once the replacement is complete.

        Parameters:
            old_str (str): The substring to search for within the script.
            new_str (str): The replacement string to write in its place.

        Returns:
            None
        """
        file = './script/rvr.tcl'
        with open(file, "r", encoding="utf-8") as f1, open(f"{file}.bak", "w", encoding="utf-8") as f2:
            for line in f1:
                if old_str in line:
                    line = new_str
                f2.write(line)
        os.remove(file)
        os.rename(f"{file}.bak", file)

