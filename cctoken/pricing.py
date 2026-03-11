from __future__ import annotations

# Sentinel for unknown model cost
UNKNOWN_COST = object()

# Rates per 1M tokens (USD)
_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input": 3.00,
        "cache_creation": 3.75,
        "cache_read": 0.30,
        "output": 15.00,
    },
    "claude-opus-4-6": {
        "input": 15.00,
        "cache_creation": 18.75,
        "cache_read": 1.50,
        "output": 75.00,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80,
        "cache_creation": 1.00,
        "cache_read": 0.08,
        "output": 4.00,
    },
}


def calculate_cost(
    model: str,
    input_tokens: int,
    cache_creation_tokens: int,
    cache_read_tokens: int,
    output_tokens: int,
):
    """Returns cost in USD, or UNKNOWN_COST sentinel if model is unknown."""
    rates = _PRICING.get(model)
    if rates is None:
        return UNKNOWN_COST

    cost = (
        input_tokens * rates["input"]
        + cache_creation_tokens * rates["cache_creation"]
        + cache_read_tokens * rates["cache_read"]
        + output_tokens * rates["output"]
    ) / 1_000_000
    return cost


def format_cost(cost) -> str:
    """Format cost for display. Handles UNKNOWN_COST sentinel."""
    if cost is UNKNOWN_COST:
        return "~$?.??"
    return f"${cost:.4f}"
