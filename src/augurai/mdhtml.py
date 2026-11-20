"""Markdown to HTML for text that may come from an LLM: raw HTML is escaped, bad links neutralised."""

import re

import markdown

_UNSAFE_HREF = re.compile(r"""href=(["'])\s*(?:javascript|vbscript|data):[^"']*\1""", re.IGNORECASE)


def render_markdown(text: str) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;")
    html = markdown.markdown(escaped, extensions=["sane_lists"])
    return _UNSAFE_HREF.sub('href="#"', html)
