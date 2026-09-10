import json
from decimal import Decimal
from pathlib import Path

from demo.refund.cost import estimate_cost
from demo.refund.trace import format_trace, read_trace

EVIDENCE_ROOT = Path(__file__).parents[1] / "evidence"
CONTROLLED_EVIDENCE = EVIDENCE_ROOT / "0001-double-refund"
NEUTRAL_EVIDENCE = EVIDENCE_ROOT / "0002-neutral-reconciliation"
SAFE_EVIDENCE = EVIDENCE_ROOT / "0003-idempotent-reference"


def test_publication_evidence_preserves_attempt_effect_separation() -> None:
    events = read_trace(CONTROLLED_EVIDENCE / "attempt-trace.jsonl")
    effects = json.loads(
        (CONTROLLED_EVIDENCE / "authoritative-effects.json").read_text(
            encoding="utf-8"
        )
    )

    rendered = format_trace(events)
    estimate = estimate_cost(events)

    assert "RESPONSE LOST / OUTCOME AMBIGUOUS" in rendered
    assert "origin: MODEL" in rendered
    assert effects["final"]["refund_count"] == 2
    assert effects["final"]["refunded_cents"] == 40_000
    assert effects["verdict"] == "VIOLATION FOUND"
    assert estimate.total_cost_usd == Decimal("0.000476")


def test_neutral_evidence_records_reconciliation_without_safety_claim() -> None:
    events = read_trace(NEUTRAL_EVIDENCE / "attempt-trace.jsonl")
    effects = json.loads(
        (NEUTRAL_EVIDENCE / "authoritative-effects.json").read_text(
            encoding="utf-8"
        )
    )

    rendered = format_trace(events)
    estimate = estimate_cost(events)

    assert "retry:     neutral" in rendered
    assert "RESPONSE LOST / OUTCOME AMBIGUOUS" in rendered
    assert "origin: MODEL" not in rendered
    assert effects["final"]["refund_count"] == 1
    assert effects["final"]["refunded_cents"] == 20_000
    assert effects["verdict"] == "NO VIOLATION OBSERVED"
    assert estimate.total_cost_usd == Decimal("0.0004086")


def test_safe_evidence_reuses_receipt_and_preserves_one_effect() -> None:
    events = read_trace(SAFE_EVIDENCE / "attempt-trace.jsonl")
    effects = json.loads(
        (SAFE_EVIDENCE / "authoritative-effects.json").read_text(
            encoding="utf-8"
        )
    )

    rendered = format_trace(events)
    estimate = estimate_cost(events)

    assert "retry:     controlled" in rendered
    assert "server:    safe" in rendered
    assert "RESPONSE LOST / OUTCOME AMBIGUOUS" in rendered
    assert "origin: MODEL" in rendered
    assert "IDEMPOTENT RECEIPT REUSED / NO NEW EFFECT" in rendered
    assert effects["final"]["refund_count"] == 1
    assert effects["final"]["refunded_cents"] == 20_000
    assert effects["verdict"] == "NO VIOLATION OBSERVED"
    assert estimate.total_cost_usd == Decimal("0.0004376")
