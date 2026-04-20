from __future__ import annotations

DEFAULT_AMLOGIC_BASE_URL = "https://llm.amlogic.com/8d1b5b4c"
DEFAULT_AMLOGIC_MODEL = "DeepSeek-V3-2"
_DEFAULT_KEY_MASK = "SmartTestAISeed"
_DEFAULT_KEY_XOR = (
    106,
    89,
    4,
    17,
    22,
    103,
    84,
    22,
    89,
    39,
    45,
    107,
    84,
    72,
    80,
    98,
    92,
    84,
    95,
    22,
    96,
    83,
    65,
    89,
    120,
    121,
    50,
    87,
    86,
    2,
    48,
    95,
    86,
    74,
    69,
    48,
)


def decode_default_amlogic_api_key() -> str:
    return "".join(
        chr(value ^ ord(_DEFAULT_KEY_MASK[index % len(_DEFAULT_KEY_MASK)]))
        for index, value in enumerate(_DEFAULT_KEY_XOR)
    )
