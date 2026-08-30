"""
AI token cost calculation.

Pricing rules (Section 6 of the brief):
  - Cached input tokens are billed at a lower rate than fresh input
    tokens, since the model provider already had them in cache.
  - Reasoning tokens are internal "thinking" tokens some models
    produce. They are billed as OUTPUT tokens, not as their own
    category and not for free.
  - Categories cannot simply be summed and priced at one flat rate --
    each category has its own price per token.

All amounts are handled as integers in MICRO-CENTS (1/1,000,000 of a
dollar) internally, to avoid floating point rounding errors on money.
The public functions return a dict with both the micro-cents figure
and a formatted dollar string for display.
"""

# Prices are pinned here in micro-cents per token. 1 dollar = 1,000,000
# micro-cents. These are illustrative rates loosely modeled on public
# frontier-model pricing tiers -- document your actual chosen numbers
# in the README.
PRICE_PER_TOKEN_MICROCENTS = {
    "input": 300,          # fresh input tokens
    "cached_input": 75,    # cached input tokens: cheaper than fresh input
    "output": 1500,        # output tokens (and reasoning tokens use this rate)
}

API_CALL_PRICE_MICROCENTS = 100_000  # flat price per API call, if metered that way


def calculate_token_cost(input_tokens=0, cached_input_tokens=0, output_tokens=0, reasoning_tokens=0):
    """
    Compute total cost in micro-cents for one usage event's AI token
    breakdown. Reasoning tokens are priced at the OUTPUT rate and
    added to output_tokens for billing purposes -- they are never a
    separate free category, and they are never priced at the (cheaper)
    input rate.
    """
    billable_output_tokens = output_tokens + reasoning_tokens

    input_cost = input_tokens * PRICE_PER_TOKEN_MICROCENTS["input"]
    cached_cost = cached_input_tokens * PRICE_PER_TOKEN_MICROCENTS["cached_input"]
    output_cost = billable_output_tokens * PRICE_PER_TOKEN_MICROCENTS["output"]

    total_microcents = input_cost + cached_cost + output_cost

    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "billable_output_tokens": billable_output_tokens,
        "input_cost_microcents": input_cost,
        "cached_cost_microcents": cached_cost,
        "output_cost_microcents": output_cost,
        "total_microcents": total_microcents,
        "total_dollars": microcents_to_dollars(total_microcents),
    }


def calculate_api_call_cost(num_calls):
    total_microcents = num_calls * API_CALL_PRICE_MICROCENTS
    return {
        "num_calls": num_calls,
        "total_microcents": total_microcents,
        "total_dollars": microcents_to_dollars(total_microcents),
    }


def microcents_to_dollars(microcents: int) -> str:
    """Format integer micro-cents as a dollar string, e.g. 1234567 -> '$1.234567'."""
    dollars = microcents / 1_000_000
    return f"${dollars:.6f}"
