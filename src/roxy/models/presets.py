"""Provider presets — built-in model providers with defaults."""

from dataclasses import dataclass


@dataclass
class ProviderPreset:
    """Pre-configured model provider with sensible defaults."""

    key: str            # config key e.g. "deepseek"
    label: str          # display name
    default_model: str  # "provider/model-name" format
    base_url: str = ""  # empty = use default
    env_var: str = ""   # well-known env var for API key
    recommended: bool = False
    description: str = ""


# Ordered list — first is recommended default
PROVIDER_PRESETS: list[ProviderPreset] = [
    ProviderPreset(
        key="deepseek", label="DeepSeek",
        default_model="deepseek/deepseek-chat",
        base_url="https://api.deepseek.com",
        env_var="DEEPSEEK_API_KEY",
        recommended=True,
        description="Recommended, low cost, strong code ability",
    ),
    ProviderPreset(
        key="openai", label="OpenAI",
        default_model="openai/gpt-4.1-mini",
        base_url="",
        env_var="OPENAI_API_KEY",
        description="Best general support",
    ),
    ProviderPreset(
        key="anthropic", label="Anthropic",
        default_model="anthropic/claude-sonnet-4-6",
        base_url="",
        env_var="ANTHROPIC_API_KEY",
        description="Claude models, strong reasoning",
    ),
    ProviderPreset(
        key="openrouter", label="OpenRouter",
        default_model="openrouter/openai/gpt-4.1-mini",
        base_url="https://openrouter.ai/api/v1",
        env_var="OPENROUTER_API_KEY",
        description="Many models via one API",
    ),
    ProviderPreset(
        key="moonshot", label="Kimi (Moonshot)",
        default_model="moonshot/moonshot-v1-8k",
        base_url="https://api.moonshot.cn/v1",
        env_var="MOONSHOT_API_KEY",
        description="Kimi Chinese-optimized models",
    ),
    ProviderPreset(
        key="zhipu", label="GLM (Zhipu)",
        default_model="zhipu/glm-4-flash",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        env_var="ZHIPU_API_KEY",
        description="GLM Chinese-optimized models",
    ),
    ProviderPreset(
        key="minimax", label="MiniMax",
        default_model="minimax/abab6.5s-chat",
        base_url="https://api.minimax.chat/v1",
        env_var="MINIMAX_API_KEY",
        description="Chinese + English models",
    ),
    ProviderPreset(
        key="groq", label="Groq",
        default_model="groq/llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
        env_var="GROQ_API_KEY",
        description="Fast inference, open-source models",
    ),
    ProviderPreset(
        key="together", label="Together AI",
        default_model="together/meta-llama/Llama-3.3-70B-Instruct-Turbo",
        base_url="https://api.together.xyz/v1",
        env_var="TOGETHER_API_KEY",
        description="Open-source models, good pricing",
    ),
    ProviderPreset(
        key="mistral", label="Mistral",
        default_model="mistral/mistral-small-latest",
        base_url="https://api.mistral.ai/v1",
        env_var="MISTRAL_API_KEY",
        description="European models, strong multilingual",
    ),
]


def get_preset(key: str) -> ProviderPreset | None:
    """Find a preset by key (case-insensitive)."""
    key_lower = key.lower()
    for p in PROVIDER_PRESETS:
        if p.key.lower() == key_lower:
            return p
    return None


def get_default_preset() -> ProviderPreset:
    """Return the recommended default provider."""
    for p in PROVIDER_PRESETS:
        if p.recommended:
            return p
    return PROVIDER_PRESETS[0]
