"""Tiny dependency-free SVG line charts for the Jobs page."""

from html import escape

WIDTH, HEIGHT = 640, 260
PAD_LEFT, PAD_RIGHT, PAD_TOP, PAD_BOTTOM = 44, 120, 16, 32


def line_chart_svg(series: dict[str, list[float]], months: list[str], label: str) -> str:
    """`series` maps a keyword to one value per month (same order as `months`)."""
    if not months or not series:
        return ""
    top = max((max(values) for values in series.values() if values), default=0) or 1
    plot_w = WIDTH - PAD_LEFT - PAD_RIGHT
    plot_h = HEIGHT - PAD_TOP - PAD_BOTTOM

    def x(i: int) -> float:
        return PAD_LEFT + (plot_w / 2 if len(months) == 1 else plot_w * i / (len(months) - 1))

    def y(value: float) -> float:
        return PAD_TOP + plot_h * (1 - value / top)

    parts = [
        f'<svg class="chart" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{escape(label)}">',
        f"<title>{escape(label)}</title>",
        f'<line class="axis" x1="{PAD_LEFT}" y1="{y(0):.1f}" x2="{WIDTH - PAD_RIGHT}" y2="{y(0):.1f}"/>',
        f'<line class="axis" x1="{PAD_LEFT}" y1="{PAD_TOP}" x2="{PAD_LEFT}" y2="{y(0):.1f}"/>',
        f'<text class="tick" x="{PAD_LEFT - 6}" y="{PAD_TOP + 4}" text-anchor="end">{top:g}</text>',
        f'<text class="tick" x="{PAD_LEFT - 6}" y="{y(0):.1f}" text-anchor="end">0</text>',
    ]
    for i, month in enumerate(months):
        parts.append(
            f'<text class="tick" x="{x(i):.1f}" y="{HEIGHT - 10}" text-anchor="middle">{escape(month)}</text>'
        )
    for index, (keyword, values) in enumerate(series.items()):
        cls = f"s{index % 6}"
        points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
        if len(values) > 1:
            parts.append(f'<polyline class="line {cls}" points="{points}"/>')
        for i, value in enumerate(values):
            parts.append(f'<circle class="dot {cls}" cx="{x(i):.1f}" cy="{y(value):.1f}" r="3.5"/>')
        last = values[-1]
        parts.append(
            f'<text class="legend {cls}" x="{WIDTH - PAD_RIGHT + 8}" y="{y(last) + 4:.1f}">{escape(keyword)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)
