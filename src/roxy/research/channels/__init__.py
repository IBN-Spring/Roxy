"""Research channels — RSS, web, search, etc."""

from roxy.research.channels.base import Channel, ResearchItem
from roxy.research.channels.rss import RSSChannel

ALL_CHANNELS: list[Channel] = [RSSChannel()]


def get_channel(name: str) -> Channel | None:
    """Get a channel by name."""
    for ch in ALL_CHANNELS:
        if ch.name == name:
            return ch
    return None


__all__ = ["Channel", "ResearchItem", "RSSChannel", "ALL_CHANNELS", "get_channel"]
