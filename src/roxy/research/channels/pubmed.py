"""PubMedChannel — query NCBI E-utilities and produce ResearchItems.

No API key required. Uses the free NCBI E-utilities REST API.
Tier 0 — zero-config.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree

import httpx

from roxy.config.loader import Config
from roxy.research.channels.base import Channel, ResearchItem

logger = logging.getLogger(__name__)


class PubMedChannel(Channel):
    """Search PubMed via NCBI E-utilities.

    Tier 0 — no API key needed for moderate usage.
    Uses esearch → efetch pipeline.
    """

    name: str = "pubmed"
    description: str = "PubMed / NCBI research papers (free API)"
    tier: int = 0
    requires_config: list[str] = []
    config_keys: dict[str, str] = {}
    ESEARCH_URL: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    EFETCH_URL: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    async def check(self, config: Config) -> tuple[str, str]:
        """Verify NCBI E-utilities are reachable."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.ESEARCH_URL}?db=pubmed&term=test&retmax=1")
                if resp.status_code == 200:
                    return "ok", "NCBI E-utilities available"
                return "warn", f"NCBI returned HTTP {resp.status_code}"
        except Exception as exc:
            return "error", str(exc)

    async def collect(
        self, config: Config, topic: str = "", since: str | None = None,
        feed_url: str = "", max_items: int = 10,
    ) -> list[ResearchItem]:
        """Search PubMed for papers matching the topic."""
        query = topic or feed_url
        if not query:
            logger.warning("PubMedChannel: no topic provided")
            return []

        # Step 1: esearch — get PMIDs
        pmids = await self._esearch(query, max_items)
        if not pmids:
            return []

        # Step 2: efetch — get abstracts
        return await self._efetch(pmids, query)

    # ── esearch ──────────────────────────────────────────────────

    async def _esearch(self, query: str, max_items: int) -> list[str]:
        """Search PubMed and return list of PMIDs."""
        url = (
            f"{self.ESEARCH_URL}?db=pubmed&term={quote(query)}"
            f"&retmax={max_items}&retmode=xml&sort=relevance"
        )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning(f"PubMed esearch returned {resp.status_code}")
                    return []

                root = ElementTree.fromstring(resp.text)
                pmids = [e.text for e in root.findall(".//Id") if e.text]
                return pmids
        except Exception as exc:
            logger.error(f"PubMed esearch failed: {exc}")
            return []

    # ── efetch ────────────────────────────────────────────────────

    async def _efetch(self, pmids: list[str], query: str) -> list[ResearchItem]:
        """Fetch abstracts for given PMIDs."""
        ids = ",".join(pmids)
        url = (
            f"{self.EFETCH_URL}?db=pubmed&id={ids}"
            f"&rettype=abstract&retmode=xml"
        )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning(f"PubMed efetch returned {resp.status_code}")
                    return []

                return self._parse_articles(resp.text, query)
        except Exception as exc:
            logger.error(f"PubMed efetch failed: {exc}")
            return []

    def _parse_articles(self, xml_text: str, query: str) -> list[ResearchItem]:
        """Parse PubMed efetch XML into ResearchItems."""
        root = ElementTree.fromstring(xml_text)
        items: list[ResearchItem] = []
        collection_time = datetime.now(timezone.utc).isoformat()

        for article in root.findall(".//PubmedArticle"):
            try:
                medline = article.find(".//MedlineCitation")
                article_data = article.find(".//Article")
                if medline is None or article_data is None:
                    continue

                pmid = _text(medline, ".//PMID")
                title = _text(article_data, ".//ArticleTitle")
                abstract = _text(article_data, ".//Abstract/AbstractText")

                # Authors
                authors = []
                for author in article_data.findall(".//Author"):
                    last = _text(author, ".//LastName")
                    fore = _text(author, ".//ForeName")
                    if last:
                        name = f"{fore} {last}".strip() if fore else last
                        authors.append(name)

                # Date
                pub_date = article_data.find(".//Journal/JournalIssue/PubDate")
                year = _text(pub_date, ".//Year") if pub_date else ""
                month = _text(pub_date, ".//Month") if pub_date else ""
                day = _text(pub_date, ".//Day") if pub_date else ""
                published = f"{year}-{month.zfill(2)}-{day.zfill(2)}" if year else ""

                item = ResearchItem(
                    title=title,
                    canonical_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    content_md=abstract,
                    content_plain=abstract[:1000],
                    summary=abstract[:500] if abstract else "",
                    authors=authors,
                    published_at=published,
                    collected_at=collection_time,
                    collected_via="pubmed",
                    source_type="paper",
                    source_channel="PubMed",
                )
                if item.title:
                    items.append(item)
            except Exception as exc:
                logger.warning(f"PubMed parse error: {exc}")
                continue

        return items


def _text(parent, xpath: str) -> str:
    """Extract text from an XML element safely."""
    el = parent.find(xpath) if parent is not None else None
    return (el.text or "").strip() if el is not None and el.text else ""
