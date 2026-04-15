"""Utility classes for interacting with RF and turntable controllers.

This module provides a singleton :class:`rs` class that wraps command-line
executables used to control RF power levels and motorized turntables in
receiver sensitivity tests.  It exposes methods to execute commands and
parses their output to track the current RF setting, angle and distance.
"""

import logging
import re
from pathlib import Path
from testing.tool.dut_tool import command_batch as subprocess
from typing import Optional

from src.util.decorators import singleton


@singleton
class rs:
    """Singleton controller wrapper for RF power and turntable interactions.

    The :class:`rs` class encapsulates state related to the current RF power,
    turntable angle and distance.  It provides methods to send commands to
    external executables that adjust these parameters and to parse their
    output.  Because the class is decorated with :func:`singleton`, only one
    instance will ever exist within a given process.
    """

    def __init__(self) -> None:
        """Initialize the controller with default executable paths and state.

        The constructor sets default paths to the RF and turntable control
        executables and initializes the current RF value, angle and distance.
        """
        tool_dir = Path(__file__).resolve().parent
        self.rf_path = str(tool_dir / 'AmlACUControl.exe')
        self.corner_path = str(tool_dir / 'AmlSunveyController.exe')
        self.rf: int = 0
        self.current_angle: str = ''
        self.current_angle_value: Optional[float] = None
        self.current_distance: str = ''

    @staticmethod
    def _extract_final_numeric(text: str) -> Optional[float]:
        """Extract the last numeric value from a string if present.

        Parameters:
            text (str): A string potentially containing numeric substrings.

        Returns:
            Optional[float]: The last floating-point number found in the
            input string, or ``None`` if no numeric substrings are present or
            conversion fails.
        """
        if not text:
            return None
        matches = re.findall(r'-?\d+(?:\.\d+)?', text)
        if not matches:
            return None
        try:
            return float(matches[-1])
        except ValueError:
            return None

    def execute_rf_cmd(self, num: int) -> None:
        """Execute the RF control command to set the power level.

        Parameters:
            num (int): The desired RF power level or setting to pass to the
                RF control executable.

        Returns:
            None
        """
        exe_path = f'{self.rf_path} {num}'
        subprocess.run(exe_path, capture_output=True, text=True)
        # Store the last RF value set by the command.
        self.rf = num

    def get_rf_current_value(self) -> int:
        """Return the most recently set RF power level.

        Returns:
            int: The last numeric value passed to :meth:`execute_rf_cmd`.
        """
        return self.rf

    def get_turntanle_current_angle(self) -> str:
        """Return the current turntable angle as a formatted string.

        Returns:
            str: The most recently parsed angle, formatted with a degree
            symbol if available, or the raw output when parsing fails.
        """
        return self.current_angle

    def set_turntable_zero(self) -> None:
        """Reset the turntable angle to zero degrees.

        Returns:
            None
        """
        self.execute_turntable_cmd('', 0)

    def execute_turntable_cmd(self, type, angle: str | int = '') -> None:
        """Execute the turntable control command and update angle/distance state.

        This method constructs a command line to drive the turntable via an
        external executable.  The output of the command is parsed to extract
        the current angle and distance information, which are stored as
        instance attributes and logged for diagnostics.

        Parameters:
            type: Unused parameter reserved for API compatibility.
            angle (str | int, optional): Desired angle to pass to the
                turntable control executable.  An empty string will query
                the current angle without moving the turntable.

        Returns:
            None
        """
        # Invoke the AutoIt-compiled executable to drive the turntable.
        exe_path = f"{self.corner_path} -angle {angle}"
        result = subprocess.run(exe_path, capture_output=True, text=True)

        raw_output = result.stdout or ""
        output = raw_output.strip()
        cleaned = output.replace('\r\n', '\n')

        angle_segment = cleaned
        distance_segment = ''
        if '|' in cleaned:
            angle_segment, distance_segment = cleaned.split('|', 1)
            angle_segment = angle_segment.strip()
            distance_segment = distance_segment.strip()

        lines = [line.strip() for line in angle_segment.split('\n') if line.strip()]
        joined_angle_text = '\n'.join(lines) if lines else angle_segment
        numeric_angle = self._extract_final_numeric(joined_angle_text)
        if numeric_angle is None and distance_segment:
            numeric_angle = self._extract_final_numeric(cleaned)

        if numeric_angle is not None:
            normalized_angle = numeric_angle % 360.0
            if normalized_angle < 0:
                normalized_angle += 360.0
            rounded = round(normalized_angle)
            if abs(normalized_angle - rounded) < 1e-6:
                display_angle = f"{int(rounded)}掳"
            else:
                display_angle = f"{normalized_angle:.1f}掳"
            self.current_angle_value = normalized_angle
            self.current_angle = display_angle
            logging.info("Current Angle: %s", display_angle)
        else:
            self.current_angle_value = None
            self.current_angle = joined_angle_text
            logging.info("Current Angle (raw): %s", joined_angle_text)

        distance_value = self._extract_final_numeric(distance_segment)
        if distance_value is not None:
            self.current_distance = f"{distance_value}"
        else:
            self.current_distance = distance_segment
        if distance_segment:
            logging.info("Current Distance: %s", self.current_distance)
        elif distance_segment == '':
            logging.debug("Turntable distance not reported in output: %s", output)

