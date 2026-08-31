from __future__ import annotations


def render_notes_description(notes: str) -> str:
    return "\n".join(
        (
            "[Steps to reproduce]:",
            "",
            "[Actual results]:",
            "",
            "[Expected results]:",
            "",
            "[Reproducibility rate]:",
            "",
            "[Comparision]:",
            "",
            "[Notes]:",
            str(notes or ""),
            "HW info:",
            "SW info:",
        )
    ).strip()
