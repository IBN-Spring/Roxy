"""ContentExtractor — HTML→markdown, title extraction, publish date parsing."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extract structured content from raw HTML."""

    @staticmethod
    def html_to_markdown(html: str, base_url: str = "") -> str:
        """Convert HTML to markdown text.

        Uses markdownify + BeautifulSoup if available, else basic tag stripping.
        """
        if not html.strip():
            return ""

        try:
            from bs4 import BeautifulSoup
            from markdownify import markdownify as md

            soup = BeautifulSoup(html, "html.parser")
            # Remove noise elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            body = soup.find("body") or soup
            return md(str(body), heading_style="ATX", strip=["img"])
        except ImportError:
            return ContentExtractor._basic_strip(html)

    @staticmethod
    def extract_title(html: str) -> str:
        """Extract the page title from HTML."""
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            title = re.sub(r"\s+", " ", title)
            return title
        return ""

    @staticmethod
    def extract_meta_description(html: str) -> str:
        """Extract meta description from HTML."""
        match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
            html,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def _basic_strip(html: str) -> str:
        """Fallback: strip HTML tags with regex."""
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()[:10000]
