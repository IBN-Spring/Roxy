"""Research channels — RSS, WeChat, web, search, etc."""

from roxy.research.channels.base import Channel, ResearchItem
from roxy.research.channels.rss import RSSChannel

ALL_CHANNELS: list[Channel] = [RSSChannel()]

# Optional channels — fail gracefully if not importable
try:
    from roxy.research.channels.wechat import WechatChannel
    ALL_CHANNELS.append(WechatChannel())
except ImportError:
    pass


def get_channel(name: str) -> Channel | None:
    """Get a channel by name."""
    for ch in ALL_CHANNELS:
        if ch.name == name:
            return ch
    return None


__all__ = [
    "Channel", "ResearchItem",
    "RSSChannel", "WechatChannel",
    "ALL_CHANNELS", "get_channel",
]
