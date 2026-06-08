import re
from typing import List, Optional
from xml.etree import ElementTree as ET


def clean_markdown_text(text: str) -> str:
    """Normalize extracted text."""
    text = re.sub(r"\f", "\n", text)
    text = re.sub(r"-\s*\n\s*(\w)", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def html_to_markdown(html_content: str) -> str:
    """
    Convert an entire HTML document to Markdown.
    Used when a TOC href has no anchor (the file IS the section).
    """
    import html2text

    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.ignore_images = True
    converter.body_width = 0
    markdown = converter.handle(html_content)
    return clean_markdown_text(markdown)
