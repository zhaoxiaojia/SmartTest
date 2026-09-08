from core.confluence.project import project_stage_color


def test_project_stage_color_contract_and_unknown_fallback():
    expected = {
        "1 EVALUATION": ("#E9E6EF", "#514A63"),
        "2 IN DEVELOPMENT": ("#DFEAF5", "#35536E"),
        "4 MP MAINTENANCE": ("#E8E8E8", "#4E4E4E"),
        "5 MP CLOSE": ("#E1EEE5", "#365B43"),
        "6 POC CLOSE": ("#DCEEEE", "#315D5D"),
        "7 PENDING": ("#F3EDCF", "#665B25"),
        "8 CANCEL KICKOFF": ("#F3E3D4", "#704B2E"),
        "9 CANCEL CLOSE": ("#EEDDD8", "#713F35"),
        "": ("#ECECEE", "#49494D"),
    }
    for stage, colors in expected.items():
        resolved = project_stage_color(stage)
        assert (resolved.background, resolved.foreground) == colors
    assert project_stage_color("new stage") == project_stage_color("")
