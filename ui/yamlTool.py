"""YAML file loading and query helper utilities.

This module defines a :class:`yamlTool` class that resolves a YAML file
relative to the configuration base directory and provides methods for
loading and accessing its contents.  Errors during loading are logged,
and multiple encodings are attempted to support different file origins.
"""
from pathlib import Path
from typing import Union

from tools.logging import smart_log

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - depends on packaged dependencies
    yaml = None


class yamlTool:
    """Helper class for loading and querying YAML configuration files.

    An instance of this class resolves the provided path against the
    configuration base directory (if relative), loads the YAML content
    using multiple encodings and provides access to top-level keys via
    :meth:`get_note`.

    Parameters:
        path (Union[str, Path]): The filename or path to the YAML file to
            load.  Relative paths are resolved using :func:`get_config_base`.
    """

    def __init__(self, path: Union[str, Path]):
        """Initialize a :class:`yamlTool` and load the specified YAML file.

        Parameters:
            path (Union[str, Path]): A path or filename to the YAML file.  If
                the path is not absolute it will be resolved against the
                configuration base directory.

        Returns:
            None
        """
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = Path.cwd() / "config" / resolved
        self.path = resolved
        self.parsed_yaml_file = self._load_file()

    def _load_file(self) -> dict:
        """Load the YAML file from disk using multiple encodings.

        The method attempts to open the file using UTF-8 and GBK encodings.
        If decoding fails for both encodings or another exception is raised,
        an empty dictionary is returned and an error is logged.

        Returns:
            dict: The parsed YAML content as a dictionary; empty if loading fails.
        """
        for encoding in ("utf-8", "gbk"):
            try:
                with self.path.open(encoding=encoding) as stream:
                    text = stream.read()
                    if yaml is not None:
                        return yaml.safe_load(text) or {}
                    return _parse_simple_yaml_mapping(text)
            except UnicodeDecodeError:
                continue
            except Exception as exc:  # pragma: no cover - I/O depends on environment
                smart_log("Failed to load yaml %s: %s", self.path, exc, level="error", domain="ui", source="yamlTool")
                break
        return {}

    def get_note(self, note: str):
        """Retrieve a top-level key from the loaded YAML data.

        Parameters:
            note (str): The key to look up in the parsed YAML dictionary.

        Returns:
            Any: The value associated with the requested key, or ``None`` if
            the key is not present.
        """
        return self.parsed_yaml_file.get(note)


def _parse_simple_yaml_mapping(text: str) -> dict:
    result: dict[str, dict] = {}
    current_key = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not raw_line.startswith((" ", "\t")) and stripped.endswith(":"):
            current_key = stripped[:-1].strip()
            result[current_key] = {}
            continue
        if current_key and ":" in stripped:
            key, value = stripped.split(":", 1)
            result[current_key][key.strip()] = value.strip().strip('"')
    return result


