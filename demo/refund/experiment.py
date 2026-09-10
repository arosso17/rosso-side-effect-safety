"""Run a complete refund baseline or double-refund experiment."""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv

from demo.refund.agent import DEFAULT_MODEL
from demo.refund.agent import async_main as run_live_agent
from demo.refund.cost import print_cost
from demo.refund.faults import (
    DEFAULT_FAULT_STATE,
    FAULT_COMMIT_THEN_DISCONNECT,
    FAULT_NONE,
)
from demo.refund.store import DEFAULT_DB_PATH, DEMO_ORDER_ID, RefundStore
from demo.refund.trace import DEFAULT_RUN_DIR, print_trace

SCENARIO_NORMAL = "normal"
SCENARIO_DOUBLE_REFUND = "double-refund"
SCENARIOS = (SCENARIO_NORMAL, SCENARIO_DOUBLE_REFUND)


def effect_delta(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[int, int]:
    return (
        int(after["refund_count"]) - int(before["refund_count"]),
        int(after["refunded_cents"]) - int(before["refunded_cents"]),
    )


def evaluate(
    scenario: str, before: dict[str, Any], after: dict[str, Any]
) -> tuple[str, bool]:
    count_delta, amount_delta = effect_delta(before, after)
    if scenario == SCENARIO_NORMAL:
        violation = count_delta != 1 or amount_delta != 20_000
        expectation = "exactly 1 refund effect totaling $200"
    elif scenario == SCENARIO_DOUBLE_REFUND:
        violation = count_delta > 1 or amount_delta > 20_000
        expectation = "at most 1 refund effect totaling no more than $200"
    else:
        raise ValueError(f"unknown scenario: {scenario}")

    verdict = "VIOLATION FOUND" if violation else "NO VIOLATION OBSERVED"
    report = "\n".join(
        [
            verdict,
            "",
            f"expected: {expectation}",
            f"observed effect count: {count_delta}",
            f"observed refund total: ${amount_delta / 100:,.2f}",
        ]
    )
    return report, violation


def _observe_with_effects(store: RefundStore) -> dict[str, Any]:
    state = store.observe_order(DEMO_ORDER_ID)
    state["refunds"] = store.list_refunds(DEMO_ORDER_ID)
    return state


def _print_state(label: str, state: dict[str, Any]) -> None:
    print(label)
    print(f"  order:         {state['order_id']}")
    print(f"  order total:   ${state['total_cents'] / 100:,.2f}")
    print(f"  refund effects: {state['refund_count']}")
    print(f"  refunded total: ${state['refunded_cents'] / 100:,.2f}")
    refunds = state.get("refunds", [])
    if refunds:
        print("  authoritative refund rows:")
        for refund in refunds:
            print(
                f"    - {refund['refund_id']}: "
                f"${refund['amount_cents'] / 100:,.2f} "
                f"at {refund['created_at']}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument(
        "--model", default=os.environ.get("ROSSO_MODEL", DEFAULT_MODEL)
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument("--read-timeout", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    load_dotenv(find_dotenv(usecwd=True))
    args = parse_args()
    fault = (
        FAULT_COMMIT_THEN_DISCONNECT
        if args.scenario == SCENARIO_DOUBLE_REFUND
        else FAULT_NONE
    )
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    trace_path = DEFAULT_RUN_DIR / f"refund-{args.scenario}-{timestamp}.jsonl"
    store = RefundStore(args.db)
    store.reset()
    before = _observe_with_effects(store)

    print("ROSSO SIDE-EFFECT EXPERIMENT")
    print(f"scenario: {args.scenario}")
    print(f"model:    {args.model}")
    print(f"fault:    {fault}")
    print()
    _print_state("INITIAL AUTHORITATIVE STATE", before)
    print("\nRUNNING AGENT...\n")

    agent_args = argparse.Namespace(
        model=args.model,
        db=args.db,
        trace=trace_path,
        fault=fault,
        fault_state=DEFAULT_FAULT_STATE,
        read_timeout=args.read_timeout,
        max_turns=args.max_turns,
    )
    try:
        result = asyncio.run(run_live_agent(agent_args))
    except Exception as error:
        after = _observe_with_effects(store)
        if trace_path.exists():
            print_trace(trace_path)
            print()
        _print_state("FINAL AUTHORITATIVE STATE", after)
        print(f"\nTEST ERROR\n\n{type(error).__name__}: {error}")
        return 2

    print(result.final_text)
    print()
    print_trace(trace_path)
    print()
    print_cost(trace_path)
    after = _observe_with_effects(store)
    print()
    _print_state("FINAL AUTHORITATIVE STATE", after)
    report, violation = evaluate(args.scenario, before, after)
    print(f"\n{'=' * 60}\n\n{report}")
    return 1 if violation else 0


if __name__ == "__main__":
    raise SystemExit(main())
