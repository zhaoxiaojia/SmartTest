from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from typing import Sequence

import matplotlib
from matplotlib import pyplot as plt

from .style import DEFAULT_LINE_CHART_STYLE, LineChartStyle


@dataclass(frozen=True)
class LineSeries:
    label: str
    values: Sequence[float]
    color: str | None = None
    fill: bool = False


def render_line_chart(
    labels: Sequence[str],
    series: Sequence[LineSeries],
    output_path: str | Path,
    *,
    title: str = "",
    highlight_series: str | None = None,
    kpi_label: str | None = None,
    style: LineChartStyle = DEFAULT_LINE_CHART_STYLE,
) -> Path:
    labels = tuple(labels)
    series = tuple(series)
    _validate_chart(labels, series, highlight_series, kpi_label)

    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    rc = {
        "font.family": list(style.font_families),
        "figure.facecolor": style.background_color,
        "axes.facecolor": style.background_color,
        "savefig.facecolor": style.background_color,
    }
    figure = None
    with matplotlib.rc_context(rc):
        try:
            figure, axes = plt.subplots(figsize=style.figure_size, dpi=style.figure_dpi)
            positions = range(len(labels))
            colors = cycle(style.palette)
            for item in series:
                color = item.color or next(colors)
                highlighted = item.label == highlight_series
                axes.plot(
                    positions,
                    item.values,
                    color=color,
                    label=item.label,
                    linewidth=(
                        style.highlight_line_width if highlighted else style.line_width
                    ),
                    marker=style.marker,
                    markersize=style.marker_size,
                    zorder=3 if highlighted else 2,
                )
                if item.fill:
                    axes.fill_between(
                        positions,
                        item.values,
                        color=color,
                        alpha=style.fill_alpha,
                    )
                if highlighted:
                    axes.plot(
                        (len(labels) - 1,),
                        (item.values[-1],),
                        color=color,
                        linestyle="None",
                        marker="o",
                        markersize=style.highlight_marker_size,
                        markeredgecolor="white",
                        markeredgewidth=style.highlight_marker_edge_width,
                        label="_nolegend_",
                        zorder=4,
                    )

            axes.set_title(title, x=0, horizontalalignment="left")
            if kpi_label:
                highlighted_series = next(
                    item for item in series if item.label == highlight_series
                )
                axes.text(
                    1.0,
                    1.02,
                    f"{kpi_label}\n{highlighted_series.values[-1]}",
                    transform=axes.transAxes,
                    horizontalalignment="right",
                    verticalalignment="bottom",
                )
            axes.set_xticks(tuple(positions), labels, rotation=style.x_rotation, ha="right")
            axes.grid(axis="y", color=style.grid_color, alpha=style.grid_alpha, linestyle="--")
            axes.grid(axis="x", visible=False)
            for spine in axes.spines.values():
                spine.set_visible(False)
            axes.legend(frameon=False, ncol=max(1, len(series)), loc="upper center")
            figure.tight_layout()
            figure.savefig(output, format="png", dpi=style.save_dpi)
        finally:
            if figure is not None:
                plt.close(figure)
    return output


def _validate_chart(
    labels: tuple[str, ...],
    series: tuple[LineSeries, ...],
    highlight_series: str | None,
    kpi_label: str | None,
) -> None:
    if not labels:
        raise ValueError("labels must not be empty")
    if not series:
        raise ValueError("series must not be empty")
    if any(len(item.values) != len(labels) for item in series):
        raise ValueError("each series length must match labels")
    if highlight_series is not None and all(
        item.label != highlight_series for item in series
    ):
        raise ValueError(f"highlight series not found: {highlight_series}")
    if kpi_label and highlight_series is None:
        raise ValueError("kpi label requires highlight series")


__all__ = ["LineSeries", "render_line_chart"]
