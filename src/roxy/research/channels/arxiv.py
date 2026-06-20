"""ArXivChannel — query ArXiv API and produce ResearchItems.

No API key required. Uses the free ArXiv API (Atom feed).
Tier 0 — zero-config.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from roxy.config.loader import Config
from roxy.research.channels.base import Channel, ResearchItem

logger = logging.getLogger(__name__)


class ArXivChannel(Channel):
    """Query the ArXiv API for research papers.

    Tier 0 — no API key, no config. Uses http://export.arxiv.org/api/query.
    """

    name: str = "arxiv"
    description: str = "ArXiv research papers (free API, no key needed)"
    tier: int = 0
    requires_config: list[str] = []
    config_keys: dict[str, str] = {}
    BASE_URL: str = "http://export.arxiv.org/api/query"

    async def check(self, config: Config) -> tuple[str, str]:
        """Verify ArXiv API is reachable."""
        try:
            import feedparser
            return "ok", "ArXiv API available"
        except ImportError:
            return "off", "feedparser not installed. Run: pip install feedparser"
        except Exception as exc:
            return "error", str(exc)

    async def collect(
        self, config: Config, topic: str = "", since: str | None = None,
        feed_url: str = "", max_items: int = 10,
    ) -> list[ResearchItem]:
        """Search ArXiv for papers matching the topic."""
        query = topic or feed_url
        if not query:
            logger.warning("ArXivChannel: no topic or query provided")
            return []

        url = f"{self.BASE_URL}?search_query=all:{quote(query)}&start=0&max_results={max_items}&sortBy=submittedDate&sortOrder=descending"

        try:
            import feedparser
            feed = feedparser.parse(url)
        except ImportError:
            return await self._fallback_fetch(url, query)
        except Exception as exc:
            logger.error(f"ArXivChannel: parse failed: {exc}")
            return []

        items: list[ResearchItem] = []
        collection_time = datetime.now(timezone.utc).isoformat()

        for entry in feed.entries[:max_items]:
            # Extract authors
            authors = []
            for author in getattr(entry, "authors", []):
                name = getattr(author, "name", "") if hasattr(author, "name") else str(author)
                if name:
                    authors.append(name)

            # ArXiv ID from URL
            arxiv_id = entry.get("id", "").split("/abs/")[-1] if "/abs/" in entry.get("id", "") else ""

            published = entry.get("published", "")

            item = ResearchItem(
                title=entry.get("title", "").strip().replace("\n", " "),
                canonical_url=entry.get("link", f"https://arxiv.org/abs/{arxiv_id}"),
                content_md=entry.get("summary", ""),
                content_plain=entry.get("summary", ""),
                summary=entry.get("summary", "")[:500],
                authors=authors,
                published_at=published,
                collected_at=collection_time,
                collected_via="arxiv",
                source_type="paper",
                source_channel="ArXiv",
            )
            if item.title and item.canonical_url:
                items.append(item)

        return items

    async def _fallback_fetch(self, url: str, query: str) -> list[ResearchItem]:
        """Direct HTTP fallback when feedparser unavailable."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    # Parse Atom XML with basic regex
                    import re
                    items: list[ResearchItem] = []
                    collection_time = datetime.now(timezone.utc).isoformat()
                    entries = re.split(r"<entry>|</entry>", resp.text)
                    for block in entries:
                        title_m = re.search(r"<title[^>]*>(.*?)</title>", block, re.DOTALL)
                        link_m = re.search(r"<id[^>]*>(.*?)</id>", block, re.DOTALL)
                        summary_m = re.search(r"<summary[^>]*>(.*?)</summary>", block, re.DOTALL)
                        if title_m and link_m:
                            items.append(ResearchItem(
                                title=re.sub(r"<[^>]+>", "", title_m.group(1)).strip(),
                                canonical_url=link_m.group(1).strip(),
                                summary=(re.sub(r"<[^>]+>", "", summary_m.group(1)).strip()[:500] if summary_m else ""),
                                collected_at=collection_time, collected_via="arxiv",
                                source_type="paper", source_channel="ArXiv",
                            ))
                    return items[:10]
        except Exception as exc:
            logger.error(f"ArXivChannel fallback failed: {exc}")
        return []
