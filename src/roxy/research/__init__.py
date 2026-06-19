"""Vertical research engine — channels, collector, extractor."""

from roxy.research.channels.base import Channel, ResearchItem
from roxy.research.channels.rss import RSSChannel
from roxy.research.collector import ContentCollector
from roxy.research.extractor import ContentExtractor

__all__ = [
    "Channel",
    "ResearchItem",
    "RSSChannel",
    "ContentCollector",
    "ContentExtractor",
]
