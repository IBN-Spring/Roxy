"""AgentReachWebChannel — read web pages via external Agent-Reach CLI.

This is a MINIMAL adapter that calls the `agent-reach` CLI tool as an external
command. Roxy does NOT import or depend on Agent-Reach source code.

If Agent-Reach is not installed, the channel gracefully degrades and shows
a doctor repair hint. The collect() method falls back to direct web_fetch
when the external command is unavailable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from roxy.config.loader import Config
from roxy.research.channels.base import ResearchItem
from roxy.research.channels.external_command import ExternalCommandChannel

logger = logging.getLogger(__name__)


class AgentReachWebChannel(ExternalCommandChannel):
    """Read web pages via Agent-Reach CLI (external tool).

    Tier 1 — requires `agent-reach` on PATH.
    Falls back to direct HTTP fetch if Agent-Reach is not available.
    """

    name: str = "agent_reach_web"
    description: str = "Read web pages via Agent-Reach CLI (external)"
    command_name: str = "agent-reach"
    install_hint_cmd: str = "pip install agent-reach"
    requires_config: list[str] = []
    config_keys: dict[str, str] = {}

    async def check(self, config: Config) -> tuple[str, str]:
        if self.command_available():
            return "ok", "agent-reach CLI available"
        return "off", (
            "agent-reach not found on PATH. "
            "Install: pip install agent-reach, or the channel will fall back to direct web_fetch."
        )

    async def collect(
        self,
        config: Config,
        topic: str = "",
        since: str | None = None,
        feed_url: str = "",
        max_items: int = 10,
    ) -> list[ResearchItem]:
        """Read a web page. Uses Agent-Reach if available, else direct fallback."""
        if not feed_url:
            logger.warning("AgentReachWebChannel: no URL provided")
            return []

        if self.command_available():
            return await self._collect_via_agent_reach(feed_url)
        else:
            return await self._collect_via_fallback(feed_url)

    # ── Agent-Reach path ─────────────────────────────────────────

    async def _collect_via_agent_reach(self, url: str) -> list[ResearchItem]:
        """Use agent-reach CLI to read a URL."""
        # Try: agent-reach read <url>  (hypothetical subcommand)
        # If that fails, try: agent-reach web <url>
        for subcmd in (["read", url], ["web", url]):
            rc, stdout, stderr = await self.run_command(subcmd)
            if rc == 0 and stdout.strip():
                item = ResearchItem(
                    title=url,
                    canonical_url=url,
                    content_md=stdout,
                    content_plain=stdout[:1000],
                    summary=stdout[:300],
                    collected_at=datetime.now(timezone.utc).isoformat(),
                    collected_via="agent_reach_web",
                    source_type="web_page",
                    source_channel="Agent-Reach",
                )
                return [item]

        logger.warning(f"AgentReachWebChannel: agent-reach command failed for {url}")
        return await self._collect_via_fallback(url)

    # ── Direct fallback ──────────────────────────────────────────

    async def _collect_via_fallback(self, url: str) -> list[ResearchItem]:
        """Fall back to direct HTTP fetch (same as web_fetch tool)."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "Roxy/0.4 (agent-reach-fallback)"},
                )
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    text = response.text
                    if "text/html" in content_type:
                        text = self._strip_html(text)
                    item = ResearchItem(
                        title=url,
                        canonical_url=url,
                        content_md=text,
                        content_plain=text[:1000],
                        summary=text[:300],
                        collected_at=datetime.now(timezone.utc).isoformat(),
                        collected_via="agent_reach_web",
                        source_type="web_page",
                        source_channel="Direct HTTP (agent-reach fallback)",
                    )
                    return [item]
        except Exception as exc:
            logger.error(f"AgentReachWebChannel fallback failed for {url}: {exc}")

        return []

    @staticmethod
    def _strip_html(html: str) -> str:
        import re
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()[:10000]
