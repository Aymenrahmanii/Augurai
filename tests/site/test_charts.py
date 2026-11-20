import itertools
import re

from augurai.site.charts import line_chart_svg


def legend_ys(svg: str) -> list[float]:
    return [float(y) for y in re.findall(r'class="legend s\d" x="[\d.]+" y="([\d.]+)"', svg)]


def test_close_series_get_separated_legend_labels():
    svg = line_chart_svg(
        {"LLM": [10.0, 21.0], "MCP": [10.0, 20.0], "RAG": [10.0, 20.5]}, ["a", "b"], "t"
    )
    ys = sorted(legend_ys(svg))
    assert len(ys) == 3 and all(b - a >= 16 for a, b in itertools.pairwise(ys))


def test_single_month_draws_dots_without_lines():
    svg = line_chart_svg({"LLM": [5.0]}, ["2026-11"], "t")
    assert "<circle" in svg and "<polyline" not in svg


def test_labels_are_escaped():
    assert "&lt;b&gt;" in line_chart_svg({"<b>": [1.0, 2.0]}, ["a", "b"], "t")


def test_empty_input_returns_nothing():
    assert line_chart_svg({}, [], "t") == ""
