"""ModelProvider — async LiteLLM wrapper with streaming support."""

import logging
import os
from typing import Any, AsyncGenerator

from roxy.config.loader import Config

logger = logging.getLogger(__name__)

# ── well-known env vars ─────────────────────────────────────────

KNOWN_ENV_KEYS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "cohere": "COHERE_API_KEY",
}


class ProviderError(Exception):
    """Raised when an LLM provider call fails.

    Carries a user-visible message, a reason code, and optionally a fix hint.
    The QueryEngine catches this and yields a TurnOutput("error", ...) WITHOUT
    saving anything to the session message history.
    """

    def __init__(self, message: str, reason: str = "provider_error", fix: str = ""):
        super().__init__(message)
        self.message = message
        self.reason = reason
        self.fix = fix  # actionable command to fix the issue


def _detect_env_key(provider: str) -> str:
    """Check well-known environment variables for a provider's API key."""
    env_var = KNOWN_ENV_KEYS.get(provider.lower(), "")
    if env_var:
        return os.environ.get(env_var, "")
    return ""


class ModelProvider:
    """Wraps LiteLLM `acompletion` for multi-provider LLM access."""

    def __init__(self, config: Config):
        self.config = config

    # ── public API ───────────────────────────────────────────────

    def resolve_model(self, model_override: str | None = None) -> str:
        if model_override:
            return model_override
        return self.config.get("models.default", "openai/gpt-4.1-mini")

    def has_api_key(self, model: str | None = None) -> bool:
        """Return True if any API key is available for the given model."""
        resolved = model or self.resolve_model()
        cfg = self._get_provider_config(resolved)
        return bool(cfg["api_key"])

    def get_key_source(self, model: str | None = None) -> str:
        """Return where the API key came from: 'config', 'env', or '' if none."""
        resolved = model or self.resolve_model()
        provider = resolved.split("/")[0] if "/" in resolved else resolved
        provider_cfg: dict = self.config.get(f"models.providers.{provider}", {}) or {}
        if provider_cfg.get("api_key", ""):
            return "config"
        if _detect_env_key(provider):
            return "env"
        return ""

    def _get_provider_config(self, model: str) -> dict[str, Any]:
        """Extract api_key / base_url from config or well-known env vars."""
        provider = model.split("/")[0] if "/" in model else model
        provider_cfg: dict = self.config.get(f"models.providers.{provider}", {}) or {}
        api_key = provider_cfg.get("api_key", "")

        # Fallback: well-known env var
        if not api_key:
            api_key = _detect_env_key(provider)

        return {
            "api_key": api_key,
            "base_url": provider_cfg.get("base_url", ""),
            "api_version": provider_cfg.get("api_version", ""),
        }

    async def stream(
        self,
        prompt: str,
        messages: list[dict[str, Any]] | None = None,
        model: str | None = None,
        system: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion from an LLM.

        Args:
            prompt: The user's message (appended to messages if provided, else sent alone).
            messages: Existing conversation history.
            model: Model override (provider/model format).
            system: System prompt.

        Yields:
            String chunks of the assistant's response as they arrive.
        """
        resolved_model = self.resolve_model(model)
        provider_cfg = self._get_provider_config(resolved_model)

        # Build message list
        msgs: list[dict[str, Any]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        if messages:
            msgs.extend(messages)
        msgs.append({"role": "user", "content": prompt})

        # LiteLLM kwargs
        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": msgs,
            "stream": True,
        }
        if provider_cfg.get("api_key"):
            kwargs["api_key"] = provider_cfg["api_key"]
        if provider_cfg.get("base_url"):
            kwargs["api_base"] = provider_cfg["base_url"]
        if provider_cfg.get("api_version"):
            kwargs["api_version"] = provider_cfg["api_version"]

        # Check for missing API key before making the call
        if not provider_cfg.get("api_key"):
            provider = resolved_model.split("/")[0] if "/" in resolved_model else resolved_model
            env_var = KNOWN_ENV_KEYS.get(provider.lower(), "")
            fix_cmd = (
                f"roxy config set models.providers.{provider}.api_key \"<your-key>\""
            )
            if env_var:
                fix_cmd += f"\n  or: export {env_var}=\"<your-key>\""
            raise ProviderError(
                f"No API key configured for provider '{provider}'.\n"
                f"Fix: {fix_cmd}",
                reason="no_api_key",
                fix=fix_cmd,
            )

        try:
            import litellm

            response = await litellm.acompletion(**kwargs)
            async for chunk in response:
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
        except ImportError:
            raise ProviderError(
                "litellm is not installed. Run: pip install litellm",
                reason="not_installed",
                fix="pip install litellm",
            )
        except Exception as exc:
            logger.error(f"LLM call failed: {exc}")
            provider = resolved_model.split("/")[0] if "/" in resolved_model else resolved_model
            raise ProviderError(
                str(exc),
                reason="api_error",
                fix=f"roxy doctor  — check provider '{provider}' status",
            ) from exc

    async def complete(
        self,
        prompt: str,
        messages: list[dict[str, Any]] | None = None,
        model: str | None = None,
        system: str | None = None,
    ) -> str:
        """Non-streaming completion. Returns the full response as a string."""
        parts: list[str] = []
        async for chunk in self.stream(prompt, messages, model, system):
            parts.append(chunk)
        return "".join(parts)
