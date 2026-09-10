from decimal import Decimal

from demo.refund.cost import estimate_cost, format_cost
from demo.refund.experiment import (
    SCENARIO_DOUBLE_REFUND,
    SCENARIO_IDEMPOTENT,
    SCENARIO_NORMAL,
    evaluate,
)
from demo.refund.trace import format_trace


def test_evaluator_detects_double_refund_violation() -> None:
    before = {"refund_count": 0, "refunded_cents": 0}
    after = {"refund_count": 2, "refunded_cents": 40_000}

    report, violation = evaluate(SCENARIO_DOUBLE_REFUND, before, after)

    assert violation is True
    assert "VIOLATION FOUND" in report
    assert "$400.00" in report


def test_evaluator_reports_normal_observation_without_claiming_safety() -> None:
    before = {"refund_count": 0, "refunded_cents": 0}
    after = {"refund_count": 1, "refunded_cents": 20_000}

    report, violation = evaluate(SCENARIO_NORMAL, before, after)

    assert violation is False
    assert report.startswith("NO VIOLATION OBSERVED")


def test_evaluator_accepts_one_idempotent_effect_without_claiming_safety() -> None:
    before = {"refund_count": 0, "refunded_cents": 0}
    after = {"refund_count": 1, "refunded_cents": 20_000}

    report, violation = evaluate(SCENARIO_IDEMPOTENT, before, after)

    assert violation is False
    assert report.startswith("NO VIOLATION OBSERVED")
    assert "exactly 1 refund effect totaling $200" in report


def test_pretty_trace_highlights_lost_response_and_retry() -> None:
    events = [
        {
            "event": "run_started",
            "run_id": "run_1",
            "model": "test-model",
            "operation_id": "operation_1",
            "retry_policy": "neutral",
            "server_mode": "safe",
        },
        {
            "event": "model_turn",
            "turn_number": 1,
            "model_turn_id": "turn_1",
            "usage": {"input_tokens": 10, "output_tokens": 4},
        },
        {
            "event": "tool_attempt_started",
            "tool": "refund_order",
            "arguments": {"order_id": "1234", "amount": 200},
            "model_turn_id": "turn_1",
            "decision_id": "decision_1",
            "tool_attempt_id": "attempt_1",
        },
        {
            "event": "tool_attempt_finished",
            "tool_attempt_id": "attempt_1",
            "outcome": "response_lost",
            "output": '{"ambiguous":true}',
        },
        {
            "event": "model_turn",
            "turn_number": 2,
            "model_turn_id": "turn_2",
            "usage": {"input_tokens": 12, "output_tokens": 3},
        },
        {
            "event": "tool_attempt_started",
            "tool": "refund_order",
            "arguments": {"order_id": "1234", "amount": 200},
            "model_turn_id": "turn_2",
            "decision_id": "decision_2",
            "tool_attempt_id": "attempt_2",
        },
        {
            "event": "tool_attempt_finished",
            "tool_attempt_id": "attempt_2",
            "outcome": "response_received",
            "output": '{"result":{"reused":true}}',
        },
        {
            "event": "run_completed",
            "final_text": "done",
        },
    ]

    rendered = format_trace(events)

    assert "RESPONSE LOST / OUTCOME AMBIGUOUS" in rendered
    assert "refund_order" in rendered
    assert "retry:     neutral" in rendered
    assert "server:    safe" in rendered
    assert "IDEMPOTENT RECEIPT REUSED / NO NEW EFFECT" in rendered
    assert "22 input / 7 output" in rendered
    assert "origin: MODEL" in rendered


def test_cost_estimate_uses_recorded_usage_and_luna_pricing() -> None:
    events = [
        {"event": "run_started", "model": "gpt-5.6-luna"},
        {
            "event": "model_turn",
            "usage": {
                "input_tokens": 1_000,
                "input_tokens_details": {
                    "cached_tokens": 100,
                    "cache_write_tokens": 200,
                },
                "output_tokens": 100,
            },
        },
    ]

    estimate = estimate_cost(events)

    assert estimate.input_tokens == 700
    assert estimate.cached_input_tokens == 100
    assert estimate.cache_write_tokens == 200
    assert estimate.output_tokens == 100
    assert estimate.total_cost_usd == Decimal("0.000312")
    assert "estimated total:                $0.000312" in format_cost(estimate)


def test_cost_estimate_rejects_unknown_model() -> None:
    events = [{"event": "run_started", "model": "unpriced-model"}]

    try:
        estimate_cost(events)
    except ValueError as error:
        assert "no pricing snapshot" in str(error)
    else:
        raise AssertionError("unknown pricing should fail explicitly")
