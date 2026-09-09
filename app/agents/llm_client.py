"""Provider-agnostic LLM client with multi-provider support.

Supports: Anthropic, OpenAI, Azure OpenAI, Bedrock, Ollama, and a deterministic
Mock provider (for offline testing when MOCK_MODE=true).

Design decision: A unified interface (`complete` and `complete_structured`) with
provider-specific adapters allows the bank to switch LLM providers without
changing agent code. The mock provider enables fully offline demos.

When MOCK_MODE=false and the provider is not configured (e.g., no API key),
an LLMProviderError is raised — no silent fallback to mock.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Raised when an LLM provider cannot be initialised or a call fails."""


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    raw_response: Any = None


@dataclass
class StructuredLLMResponse:
    """Response from structured/tool-calling mode."""
    data: Dict[str, Any]
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def complete(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        """Generate a text completion."""
        ...

    @abstractmethod
    def complete_structured(
        self, prompt: str, schema: Dict[str, Any], system: str = "", **kwargs
    ) -> StructuredLLMResponse:
        """Generate a structured (JSON) completion matching the given schema."""
        ...


# =============================================================================
# Anthropic Provider
# =============================================================================

class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = model
        except ImportError:
            raise LLMProviderError(
                "anthropic package not installed. Install with: pip install anthropic"
            )

    def complete(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        messages = [{"role": "user", "content": prompt}]
        response = self.client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", 4096),
            system=system or "You are a professional banking analyst.",
            messages=messages,
        )
        content = response.content[0].text if response.content else ""
        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            raw_response=response,
        )

    def complete_structured(
        self, prompt: str, schema: Dict[str, Any], system: str = "", **kwargs
    ) -> StructuredLLMResponse:
        system_prompt = (
            (system or "You are a professional banking analyst.")
            + " Respond ONLY with valid JSON matching the provided schema."
        )
        full_prompt = f"{prompt}\n\nJSON Schema:\n```json\n{json.dumps(schema, indent=2)}\n```"
        response = self.complete(full_prompt, system=system_prompt, **kwargs)

        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse structured response, retrying")
            response = self.complete(full_prompt, system=system_prompt, **kwargs)
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(content)

        return StructuredLLMResponse(
            data=data,
            content=response.content,
            model=response.model,
            usage=response.usage,
        )


# =============================================================================
# OpenAI Provider
# =============================================================================

class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key)
            self.model = model
        except ImportError:
            raise LLMProviderError(
                "openai package not installed. Install with: pip install openai"
            )

    def complete(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=self.model,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
            raw_response=response,
        )

    def complete_structured(
        self, prompt: str, schema: Dict[str, Any], system: str = "", **kwargs
    ) -> StructuredLLMResponse:
        messages = []
        sys_msg = system or "You are a professional banking analyst. Respond ONLY with valid JSON."
        messages.append({"role": "system", "content": sys_msg})
        full_prompt = f"{prompt}\n\nJSON Schema:\n```json\n{json.dumps(schema, indent=2)}\n```"
        messages.append({"role": "user", "content": full_prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", 4096),
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        data = json.loads(content)
        return StructuredLLMResponse(
            data=data,
            content=content,
            model=self.model,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
        )


# =============================================================================
# Azure OpenAI Provider
# =============================================================================

class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI provider."""

    def __init__(self, api_key: str, endpoint: str, deployment: str):
        try:
            import openai
            self.client = openai.AzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version="2024-06-01",
            )
            self.deployment = deployment
        except ImportError:
            raise LLMProviderError(
                "openai package not installed. Install with: pip install openai"
            )

    def complete(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=self.deployment,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
        )

    def complete_structured(
        self, prompt: str, schema: Dict[str, Any], system: str = "", **kwargs
    ) -> StructuredLLMResponse:
        sys_msg = system or "You are a professional banking analyst. Respond ONLY with valid JSON."
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": f"{prompt}\n\nJSON Schema:\n{json.dumps(schema, indent=2)}"},
        ]
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", 4096),
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        data = json.loads(content)
        return StructuredLLMResponse(data=data, content=content, model=self.deployment)


# =============================================================================
# Ollama Provider (local models)
# =============================================================================

class OllamaProvider(LLMProvider):
    """Ollama provider for local models."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        import httpx
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": full_prompt, "stream": False},
            timeout=kwargs.get("timeout", 120),
        )
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(
            content=data.get("response", ""),
            model=self.model,
            usage={"total_tokens": data.get("eval_count", 0)},
        )

    def complete_structured(
        self, prompt: str, schema: Dict[str, Any], system: str = "", **kwargs
    ) -> StructuredLLMResponse:
        sys_msg = system or "Respond ONLY with valid JSON."
        full_prompt = f"{prompt}\n\nJSON Schema:\n{json.dumps(schema, indent=2)}"
        response = self.complete(full_prompt, system=sys_msg, **kwargs)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(content)
        return StructuredLLMResponse(data=data, content=response.content, model=self.model)


# =============================================================================
# Mock Provider (for offline testing — only used when MOCK_MODE=true)
# =============================================================================

class MockProvider(LLMProvider):
    """Deterministic mock provider for testing and offline demos.

    Returns realistic-looking but synthetic data without any API calls.
    Only used when MOCK_MODE=true or provider is explicitly set to 'mock'.
    """

    def complete(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        return LLMResponse(
            content=_generate_mock_narrative(prompt),
            model="mock-v1",
            usage={"input_tokens": len(prompt.split()), "output_tokens": 200},
        )

    def complete_structured(
        self, prompt: str, schema: Dict[str, Any], system: str = "", **kwargs
    ) -> StructuredLLMResponse:
        data = _generate_mock_structured(schema)
        return StructuredLLMResponse(
            data=data,
            content=json.dumps(data, indent=2),
            model="mock-v1",
            usage={"input_tokens": len(prompt.split()), "output_tokens": 100},
        )


def _generate_mock_narrative(prompt: str) -> str:
    """Generate a realistic mock narrative based on prompt keywords."""
    prompt_lower = prompt.lower()
    if "borrower" in prompt_lower or "overview" in prompt_lower:
        return (
            "The borrower is a well-established Kuwaiti corporate entity with a diversified "
            "portfolio spanning real estate, construction, and trading activities. The company "
            "has maintained a stable operating performance over the past three fiscal years, "
            "with consistent revenue growth averaging 8-12% annually. [ref:chunk_001] "
            "Management has demonstrated prudent financial management with adequate liquidity "
            "buffers and manageable leverage levels. [ref:chunk_002]"
        )
    elif "risk" in prompt_lower or "policy" in prompt_lower or "recommendation" in prompt_lower:
        return (
            "Key risks identified include concentration in the Kuwaiti real estate sector "
            "and moderate leverage levels. However, these are mitigated by strong collateral "
            "coverage (loan-to-value of 65%) and the borrower's diversified income streams. "
            "[ref:chunk_005] The facility is structured as a Murabaha with appropriate "
            "profit rate and deferred payment terms compliant with Shariah principles. "
            "[ref:chunk_006]"
        )
    elif "financial" in prompt_lower:
        return (
            "Financial analysis indicates the borrower maintains healthy credit metrics. "
            "The Debt Service Coverage Ratio (DSCR) stands at 1.45x, well above the bank's "
            "minimum threshold of 1.2x. [ref:chunk_003] Leverage ratio of 2.1x is within "
            "acceptable limits (maximum 3.0x). Current ratio of 1.8x demonstrates adequate "
            "short-term liquidity. [ref:chunk_004]"
        )
    return (
        "Based on the available data and analysis, the facility request is assessed as "
        "presenting an acceptable risk profile. The borrower demonstrates adequate capacity "
        "to service the proposed facility under the Murabaha structure with cost-plus "
        "profit rate and deferred payment terms. [ref:chunk_001]"
    )


def _generate_mock_structured(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Generate mock structured data matching a JSON schema.

    Handles string, number, boolean, array, and object types.
    For array-type fields (e.g., key_risks, mitigants), generates
    deterministic mock entries with chunk_id references.
    """
    result = {}
    properties = schema.get("properties", {})

    for key, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")

        if key == "source_chunk_ids":
            result[key] = {
                "net_operating_income": "chunk_001",
                "total_debt_service": "chunk_002",
                "total_liabilities": "chunk_003",
                "total_equity": "chunk_004",
                "current_assets": "chunk_005",
                "current_liabilities": "chunk_006",
            }
        elif prop_type == "number":
            mock_values = {
                "net_operating_income": 2_500_000,
                "total_debt_service": 1_720_000,
                "total_liabilities": 8_500_000,
                "total_equity": 4_200_000,
                "current_assets": 6_300_000,
                "current_liabilities": 3_500_000,
            }
            result[key] = mock_values.get(key, 1_000_000)
        elif prop_type == "boolean":
            result[key] = True
        elif prop_type == "string":
            result[key] = f"Mock value for {key}"
        elif prop_type == "array":
            items_schema = prop_schema.get("items", {})
            items_type = items_schema.get("type", "string")
            if items_type == "object":
                # Generate deterministic mock objects with chunk_id references
                item_props = items_schema.get("properties", {})
                mock_items = _generate_mock_array_items(key, item_props)
                result[key] = mock_items
            elif items_type == "string":
                result[key] = _generate_mock_string_array(key)
            else:
                result[key] = []
        elif prop_type == "object":
            obj_props = prop_schema.get("properties", {})
            if obj_props:
                result[key] = _generate_mock_structured(
                    {"properties": obj_props}
                )
            else:
                result[key] = {}
        else:
            result[key] = None

    return result


def _generate_mock_array_items(
    field_name: str, item_props: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Generate deterministic mock array items with chunk_id references."""
    templates = {
        "key_risks": [
            {"description": "Sector concentration in Kuwaiti real estate", "severity": "medium", "chunk_id": "chunk_010"},
            {"description": "Moderate leverage ratio at 2.1x", "severity": "low", "chunk_id": "chunk_011"},
            {"description": "Single-borrower exposure exceeds 5% of capital", "severity": "medium", "chunk_id": "chunk_012"},
        ],
        "mitigants": [
            {"description": "Strong collateral coverage (LTV 65%)", "chunk_id": "chunk_020"},
            {"description": "Diversified income streams across three business lines", "chunk_id": "chunk_021"},
            {"description": "Personal guarantee from principal shareholder", "chunk_id": "chunk_022"},
        ],
        "policy_exceptions": [
            {"description": "Debt-to-equity ratio exceeds policy limit by 5%", "severity": "low", "chunk_id": "chunk_030"},
        ],
        "breaches": [
            {"ratio_name": "Debt to Equity", "threshold": 3.0, "actual": 2.02, "severity": "low", "chunk_id": "chunk_040"},
        ],
        "shariah_flags": [
            {"term_used": "APR", "expected": "Profit Rate", "severity": "medium", "chunk_id": "chunk_050"},
        ],
    }
    if field_name in templates:
        return templates[field_name]

    # Fallback: generate one generic item from the properties schema
    item = {}
    for prop_name, prop_def in item_props.items():
        p_type = prop_def.get("type", "string")
        if p_type == "string":
            item[prop_name] = f"Mock {prop_name}"
        elif p_type == "number":
            item[prop_name] = 0.0
        elif p_type == "boolean":
            item[prop_name] = False
        else:
            item[prop_name] = None
    return [item] if item else []


def _generate_mock_string_array(field_name: str) -> List[str]:
    """Generate deterministic mock string arrays."""
    templates = {
        "sources": ["chunk_001", "chunk_002", "chunk_003"],
        "citations": ["chunk_001", "chunk_004"],
        "section_keys": ["executive_summary", "financial_analysis", "risk_and_mitigants"],
        "tags": ["corporate", "real_estate", "murabaha"],
    }
    return templates.get(field_name, [f"mock_{field_name}_item_1"])


# =============================================================================
# Factory
# =============================================================================

def get_llm_client(provider: Optional[str] = None) -> LLMProvider:
    """Factory: create the appropriate LLM provider based on configuration.

    When MOCK_MODE=true, returns MockProvider regardless of other settings.
    When MOCK_MODE=false and the provider is not configured, raises LLMProviderError.

    Args:
        provider: Override provider name (defaults to settings).

    Returns:
        An LLMProvider instance.

    Raises:
        LLMProviderError: If MOCK_MODE is false and the provider is not configured.
    """
    settings = get_settings()
    provider_name = (provider or settings.llm_provider).lower()

    # Force mock if in mock mode
    if settings.use_mock_llm:
        if provider_name != "mock":
            logger.info("MOCK_MODE=true — using MockProvider")
        return MockProvider()

    # MOCK_MODE=false from here on — no silent fallback allowed
    if provider_name == "anthropic":
        if not settings.llm_api_key:
            raise LLMProviderError(
                "MOCK_MODE=false and provider=anthropic but LLM_API_KEY is not set. "
                "Set LLM_API_KEY or enable MOCK_MODE=true."
            )
        return AnthropicProvider(api_key=settings.llm_api_key, model=settings.llm_model)

    elif provider_name == "openai":
        if not settings.llm_api_key:
            raise LLMProviderError(
                "MOCK_MODE=false and provider=openai but LLM_API_KEY is not set. "
                "Set LLM_API_KEY or enable MOCK_MODE=true."
            )
        return OpenAIProvider(api_key=settings.llm_api_key, model=settings.llm_model)

    elif provider_name == "azure":
        if not settings.llm_api_key or not settings.azure_openai_endpoint:
            raise LLMProviderError(
                "MOCK_MODE=false and provider=azure but Azure config is incomplete. "
                "Set LLM_API_KEY and AZURE_OPENAI_ENDPOINT, or enable MOCK_MODE=true."
            )
        return AzureOpenAIProvider(
            api_key=settings.llm_api_key,
            endpoint=settings.azure_openai_endpoint,
            deployment=settings.azure_openai_deployment or settings.llm_model,
        )

    elif provider_name == "ollama":
        return OllamaProvider(base_url=settings.ollama_base_url, model=settings.llm_model)

    elif provider_name == "mock":
        return MockProvider()

    else:
        raise LLMProviderError(
            f"Unknown LLM provider '{provider_name}'. "
            f"Supported: anthropic, openai, azure, ollama, mock."
        )
