"""Provider USD quotes, never Noris points or an assertion of final billing."""

from decimal import Decimal

from noris_ai.llm.provider_models import ProviderModel
from noris_ai.llm.schemas import ModelCost

MILLION = Decimal(1_000_000)


def model_cost(facts: ProviderModel, fetched_at: str) -> ModelCost:
    def rate(kind: str) -> Decimal | None:
        modalities = facts.output_modalities if kind == "completion" else facts.input_modalities
        entries = [
            price
            for item in (modalities or [])
            if item.type == "text"
            for price in item.pricing
            if price.type == kind
        ]
        if not entries or any(price.unit != "token" for price in entries):
            return None
        prices = {price.cost_usd for price in entries}
        # Conflicting quotes have no unambiguous unit price.
        return prices.pop() * MILLION if len(prices) == 1 else None

    prompt, cached, completion = rate("prompt"), rate("cached_prompt"), rate("completion")
    return ModelCost(
        currency="USD"
        if any(value is not None for value in (prompt, cached, completion))
        else None,
        evidence="DOCUMENTED"
        if any(value is not None for value in (prompt, cached, completion))
        else "UNKNOWN",
        as_of=fetched_at,
        input_usd_per_million=prompt,
        cached_input_usd_per_million=cached,
        output_usd_per_million=completion,
        is_free=facts.is_free,
        discount_to_user=facts.discount_to_user,
    )


def estimate_cost(cost: ModelCost, input_tokens: int, output_tokens: int) -> Decimal | None:
    if cost.is_free is True:
        return Decimal(0)
    if cost.input_usd_per_million is None or cost.output_usd_per_million is None:
        return None
    # No assumption of cache hits or an undocumented discount interpretation.
    return (
        cost.input_usd_per_million * input_tokens + cost.output_usd_per_million * output_tokens
    ) / MILLION
