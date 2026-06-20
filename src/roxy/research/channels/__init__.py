"""Research channels — RSS, WeChat, Agent-Reach, external adapters."""

from roxy.research.channels.base import Channel, ResearchItem
from roxy.research.channels.rss import RSSChannel

ALL_CHANNELS: list[Channel] = [RSSChannel()]

# Optional channels — fail gracefully if not importable
_CHANNEL_CLASSES = [
    ("roxy.research.channels.wechat", "WechatChannel"),
    ("roxy.research.channels.agent_reach_web", "AgentReachWebChannel"),
]

for module_path, class_name in _CHANNEL_CLASSES:
    try:
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        ALL_CHANNELS.append(cls())
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
    "RSSChannel", "WechatChannel", "AgentReachWebChannel",
    "ALL_CHANNELS", "get_channel",
]
