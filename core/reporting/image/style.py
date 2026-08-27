from dataclasses import dataclass


@dataclass(frozen=True)
class LineChartStyle:
    palette: tuple[str, ...] = (
        "#4F8EF7",
        "#2CB67D",
        "#F59E0B",
        "#DC2626",
        "#7C3AED",
        "#0891B2",
    )
    background_color: str = "#FFFFFF"
    grid_color: str = "#D1D5DB"
    grid_alpha: float = 0.15
    line_width: float = 2.8
    highlight_line_width: float = 3.0
    marker: str = "o"
    marker_size: float = 5.0
    highlight_marker_size: float = 9.0
    highlight_marker_edge_width: float = 2.0
    fill_alpha: float = 0.12
    x_rotation: float = 20.0
    figure_size: tuple[float, float] = (11.0, 5.0)
    figure_dpi: int = 220
    save_dpi: int = 220
    font_families: tuple[str, ...] = ("Segoe UI", "DejaVu Sans", "sans-serif")


DEFAULT_LINE_CHART_STYLE = LineChartStyle()


__all__ = ["DEFAULT_LINE_CHART_STYLE", "LineChartStyle"]
