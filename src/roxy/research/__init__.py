"""Vertical research engine — channels, collector, extractor."""

from roxy.research.channels.base import Channel, ResearchItem
from roxy.research.channels.rss import RSSChannel
from roxy.research.collector import ContentCollector
from roxy.research.extractor import ContentExtractor
from roxy.research.source_manager import SourceManager, FeedSource
from roxy.research.digest import ResearchDigest

__all__ = [
    "Channel",
    "ResearchItem",
    "RSSChannel",
    "ContentCollector",
    "ContentExtractor",
    "SourceManager",
    "FeedSource",
    "ResearchDigest",
]
