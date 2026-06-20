"""RSSChannel — read RSS/Atom feeds and produce ResearchItems."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from roxy.config.loader import Config
from roxy.research.channels.base import Channel, ResearchItem

logger = logging.getLogger(__name__)


def _getattr(obj: Any, attr: str, default: Any = "") -> Any:
    """Get an attribute or dict key from feedparser objects.

    feedparser entries can be dict-like or object-like depending on the parser version.
    """
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


class RSSChannel(Channel):
    """Read RSS and Atom feeds. Tier 0 — zero-config (uses feedparser).

    Usage:
        channel = RSSChannel()
        ok, msg = await channel.check(config)
        items = await channel.collect(config, feed_url="https://example.com/rss")
    """

    name: str = "rss"
    description: str = "RSS / Atom feed reader"
    tier: int = 0
    requires_config: list[str] = []
    config_keys: dict[str, str] = {}

    async def check(self, config: Config) -> tuple[str, str]:
        """Verify feedparser is importable."""
        try:
            import feedparser
            return "ok", "feedparser available"
        except ImportError:
            return "off", "feedparser not installed. Run: pip install feedparser"

    async def collect(
        self,
        config: Config,
        topic: str = "",
        since: str | None = None,
        feed_url: str = "",
        max_items: int = 50,
    ) -> list[ResearchItem]:
        """Collect items from an RSS feed.

        Args:
            config: Roxy config.
            topic: Not used by RSS channel (feed_url is the source selector).
            since: ISO 8601 — skip items published before this date.
            feed_url: The RSS feed URL to fetch.
            max_items: Max items to return.

        Returns:
            List of ResearchItem objects.
        """
        if not feed_url:
            logger.warning("RSSChannel: no feed_url provided")
            return []

        try:
            import feedparser
        except ImportError:
            logger.error("feedparser not installed")
            return []

        try:
            feed = feedparser.parse(feed_url)
        except Exception as exc:
            logger.error(f"RSSChannel: failed to parse {feed_url}: {exc}")
            return []

        if feed.bozo:
            logger.warning(f"RSSChannel: feed {feed_url} may be malformed: {feed.bozo_exception}")

        items: list[ResearchItem] = []
        collection_time = datetime.now(timezone.utc).isoformat()
        feed_title = _getattr(feed.feed, "title", "")

        for entry in feed.entries[:max_items]:
            published = self._parse_date(entry)

            # Filter by since
            if since and published and published < since:
                continue

            item = ResearchItem(
                title=_getattr(entry, "title", "").strip(),
                canonical_url=_getattr(entry, "link", "").strip(),
                content_md=self._get_content(entry),
                content_plain=self._get_summary(entry),
                summary=self._get_summary(entry)[:500],
                authors=self._get_authors(entry),
                published_at=published or "",
                collected_at=collection_time,
                collected_via="rss",
                source_type="rss_feed",
                source_feed_url=feed_url,
                source_channel=feed_title or feed_url,
            )

            if item.title and item.canonical_url:
                items.append(item)

        return items

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _get_content(entry: Any) -> str:
        """Extract the best available content from a feed entry."""
        if hasattr(entry, "content") and entry.content:
            return _getattr(entry.content[0], "value", "")
        if hasattr(entry, "summary_detail") and entry.summary_detail:
            return _getattr(entry.summary_detail, "value", "")
        return _getattr(entry, "summary", "")

    @staticmethod
    def _get_summary(entry: Any) -> str:
        """Extract a plain-text summary."""
        text = _getattr(entry, "summary", "")
        # Strip HTML tags for plain text
        import re
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()[:1000]

    @staticmethod
    def _get_authors(entry: Any) -> list[str]:
        """Extract author names."""
        authors = []
        for author in _getattr(entry, "authors", []):
            name = _getattr(author, "name", "")
            if name:
                authors.append(name)
        if not authors:
            author_str = _getattr(entry, "author", "")
            if author_str:
                authors.append(author_str)
        return authors

    @staticmethod
    def _parse_date(entry: Any) -> str:
        """Parse the published date from a feed entry. Returns ISO 8601 string."""
        for field in ("published", "updated", "created"):
            # feedparser entries can be dict-like or object-like
            raw = _getattr(entry, f"{field}_parsed") or _getattr(entry, field, "")
            if raw:
                if isinstance(raw, str):
                    try:
                        dt = parsedate_to_datetime(raw)
                        return dt.isoformat()
                    except Exception:
                        pass
                elif isinstance(raw, tuple) and len(raw) >= 6:
                    try:
                        from time import mktime
                        dt = datetime.fromtimestamp(mktime(raw), tz=timezone.utc)
                        return dt.isoformat()
                    except Exception:
                        pass
        return ""
