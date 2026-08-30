"""
Standalone proof of correct AI-token pricing totals, worked by hand
alongside the code output, for EVIDENCE.md.
"""

from app.services.pricing import calculate_token_cost, PRICE_PER_TOKEN_MICROCENTS

print("Pinned rates (micro-cents per token):")
for k, v in PRICE_PER_TOKEN_MICROCENTS.items():
    print(f"  {k}: {v}")
print()

# Case 1: fresh input + output only, no cache, no reasoning.
r1 = calculate_token_cost(input_tokens=1000, output_tokens=500)
expected_1 = 1000 * PRICE_PER_TOKEN_MICROCENTS["input"] + 500 * PRICE_PER_TOKEN_MICROCENTS["output"]
print("Case 1: 1000 input, 500 output")
print(f"  calculated total_microcents = {r1['total_microcents']}")
print(f"  hand-calculated expected    = {expected_1}")
print(f"  match: {r1['total_microcents'] == expected_1}")
print()

# Case 2: cached input should cost LESS than the same amount of fresh input.
r2_fresh = calculate_token_cost(input_tokens=1000)
r2_cached = calculate_token_cost(cached_input_tokens=1000)
print("Case 2: 1000 fresh input vs 1000 cached input")
print(f"  fresh input cost microcents  = {r2_fresh['total_microcents']}")
print(f"  cached input cost microcents = {r2_cached['total_microcents']}")
print(f"  cached is cheaper: {r2_cached['total_microcents'] < r2_fresh['total_microcents']}")
print()

# Case 3: reasoning tokens must be billed at the OUTPUT rate, added to output.
r3 = calculate_token_cost(output_tokens=200, reasoning_tokens=300)
expected_3 = (200 + 300) * PRICE_PER_TOKEN_MICROCENTS["output"]
print("Case 3: 200 output + 300 reasoning tokens")
print(f"  billable_output_tokens      = {r3['billable_output_tokens']} (expected 500)")
print(f"  calculated total_microcents = {r3['total_microcents']}")
print(f"  hand-calculated expected    = {expected_3}")
print(f"  match: {r3['total_microcents'] == expected_3}")
print()

# Case 4: all four categories combined -- the realistic case.
r4 = calculate_token_cost(input_tokens=1000, cached_input_tokens=2000, output_tokens=300, reasoning_tokens=150)
expected_4 = (
    1000 * PRICE_PER_TOKEN_MICROCENTS["input"]
    + 2000 * PRICE_PER_TOKEN_MICROCENTS["cached_input"]
    + (300 + 150) * PRICE_PER_TOKEN_MICROCENTS["output"]
)
print("Case 4: 1000 input, 2000 cached input, 300 output, 150 reasoning")
print(f"  calculated total_microcents = {r4['total_microcents']}")
print(f"  hand-calculated expected    = {expected_4}")
print(f"  match: {r4['total_microcents'] == expected_4}")
print(f"  total_dollars = {r4['total_dollars']}")
