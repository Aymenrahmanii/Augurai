from augurai.mdhtml import render_markdown


def test_renders_basic_markdown():
    html = render_markdown("- one\n- [two](https://example.com/a?x=1&y=2)")
    assert "<li>one</li>" in html and 'href="https://example.com/a?x=1&amp;y=2"' in html


def test_raw_html_is_escaped():
    html = render_markdown("<script>alert(1)</script> and <b>bold</b>")
    assert "<script>" not in html and "<b>" not in html
    assert "&lt;script&gt;" in html


def test_javascript_links_are_neutralised():
    html = render_markdown("[x](javascript:alert(1))")
    assert "javascript:" not in html.lower()
