"""Estimate the OpenAI token cost recorded in a refund experiment trace."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from demo.refund.trace import latest_trace, read_trace

MILLION = Decimal(1_000_000)
PRICING_SOURCE = "https://developers.openai.com/api/docs/models/gpt-5.6-luna"


@dataclass(frozen=True)
class ModelPricing:
    model: str
    effective_date: str
    input_per_million_usd: Decimal
    cached_input_per_million_usd: Decimal
    cache_write_per_million_usd: Decimal
    output_per_million_usd: Decimal
    long_context_threshold: int
    long_input_multiplier: Decimal
    long_output_multiplier: Decimal
    source: str


@dataclass(frozen=True)
class CostEstimate:
    model: str
    input_tokens: int
    cached_input_tokens: int
    cache_write_tokens: int
    output_tokens: int
    input_cost_usd: Decimal
    cached_input_cost_usd: Decimal
    cache_write_cost_usd: Decimal
    output_cost_usd: Decimal
    total_cost_usd: Decimal
    pricing: ModelPricing


PRICING = {
    "gpt-5.6-luna": ModelPricing(
        model="gpt-5.6-luna",
        effective_date="2026-09-09",
        input_per_million_usd=Decimal("0.20"),
        cached_input_per_million_usd=Decimal("0.02"),
        cache_write_per_million_usd=Decimal("0.25"),
        output_per_million_usd=Decimal("1.20"),
        long_context_threshold=272_000,
        long_input_multiplier=Decimal(2),
        long_output_multiplier=Decimal("1.5"),
        source=PRICING_SOURCE,
    )
}


def _token_cost(tokens: int, rate: Decimal, multiplier: Decimal) -> Decimal:
    return Decimal(tokens) * rate * multiplier / MILLION


def estimate_cost(
    events: list[dict[str, Any]],
    pricing_catalog: dict[str, ModelPricing] = PRICING,
) -> CostEstimate:
    started = next(
        (event for event in events if event.get("event") == "run_started"), None
    )
    if started is None:
        raise ValueError("trace has no run_started event")
    model = str(started.get("model", ""))
    try:
        pricing = pricing_catalog[model]
    except KeyError as error:
        known = ", ".join(sorted(pricing_catalog))
        raise ValueError(
            f"no pricing snapshot for model {model!r}; known models: {known}"
        ) from error

    totals = {
        "input": 0,
        "cached": 0,
        "cache_write": 0,
        "output": 0,
    }
    costs = {
        "input": Decimal(0),
        "cached": Decimal(0),
        "cache_write": Decimal(0),
        "output": Decimal(0),
    }
    usage_observed = False

    for event in events:
        if event.get("event") != "model_turn" or not event.get("usage"):
            continue
        usage_observed = True
        usage = event["usage"]
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        details = usage.get("input_tokens_details") or {}
        cached_tokens = int(details.get("cached_tokens", 0))
        cache_write_tokens = int(details.get("cache_write_tokens", 0))
        uncached_tokens = input_tokens - cached_tokens - cache_write_tokens
        if uncached_tokens < 0:
            raise ValueError("input token detail exceeds the recorded input total")

        long_context = input_tokens > pricing.long_context_threshold
        input_multiplier = (
            pricing.long_input_multiplier if long_context else Decimal(1)
        )
        output_multiplier = (
            pricing.long_output_multiplier if long_context else Decimal(1)
        )

        totals["input"] += uncached_tokens
        totals["cached"] += cached_tokens
        totals["cache_write"] += cache_write_tokens
        totals["output"] += output_tokens
        costs["input"] += _token_cost(
            uncached_tokens, pricing.input_per_million_usd, input_multiplier
        )
        costs["cached"] += _token_cost(
            cached_tokens,
            pricing.cached_input_per_million_usd,
            input_multiplier,
        )
        costs["cache_write"] += _token_cost(
            cache_write_tokens,
            pricing.cache_write_per_million_usd,
            input_multiplier,
        )
        costs["output"] += _token_cost(
            output_tokens, pricing.output_per_million_usd, output_multiplier
        )

    if not usage_observed:
        raise ValueError("trace has no model usage data")

    total = sum(costs.values(), start=Decimal(0))
    return CostEstimate(
        model=model,
        input_tokens=totals["input"],
        cached_input_tokens=totals["cached"],
        cache_write_tokens=totals["cache_write"],
        output_tokens=totals["output"],
        input_cost_usd=costs["input"],
        cached_input_cost_usd=costs["cached"],
        cache_write_cost_usd=costs["cache_write"],
        output_cost_usd=costs["output"],
        total_cost_usd=total,
        pricing=pricing,
    )


def _money(value: Decimal) -> str:
    return f"${value:.6f}"


def _cost_line(label: str, tokens: int, cost: Decimal) -> str:
    return f"{label:<16}{tokens:>8,}  {_money(cost)}"


def format_cost(estimate: CostEstimate) -> str:
    pricing = estimate.pricing
    return "\n".join(
        [
            "ROSSO RUN COST ESTIMATE",
            "",
            f"model:          {estimate.model}",
            f"pricing as of:  {pricing.effective_date}",
            "",
            "TOKENS AND ESTIMATED COST",
            _cost_line(
                "uncached input:", estimate.input_tokens, estimate.input_cost_usd
            ),
            _cost_line(
                "cached input:",
                estimate.cached_input_tokens,
                estimate.cached_input_cost_usd,
            ),
            _cost_line(
                "cache writes:",
                estimate.cache_write_tokens,
                estimate.cache_write_cost_usd,
            ),
            _cost_line("output:", estimate.output_tokens, estimate.output_cost_usd),
            "                                ----------",
            f"estimated total:                {_money(estimate.total_cost_usd)}",
            f"estimated cents:                {estimate.total_cost_usd * 100:.4f}",
            "",
            "This is a local estimate, not an invoice. It excludes taxes, credits,",
            "service-tier adjustments, and any unrecorded or non-token charges.",
            f"pricing source: {pricing.source}",
        ]
    )


def estimate_trace(trace_path: Path) -> CostEstimate:
    return estimate_cost(read_trace(trace_path))


def print_cost(trace_path: Path) -> None:
    print(format_cost(estimate_trace(trace_path)))
    print(f"\ntrace file: {trace_path.resolve()}")


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "trace",
        nargs="?",
        type=Path,
        help="Trace file; defaults to the newest refund trace",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    trace_path = args.trace or latest_trace()
    estimate = estimate_trace(trace_path)
    if args.json:
        print(json.dumps(asdict(estimate), default=_json_default, indent=2))
    else:
        print_cost(trace_path)


if __name__ == "__main__":
    main()
