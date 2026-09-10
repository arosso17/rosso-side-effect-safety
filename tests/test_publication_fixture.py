import json
from decimal import Decimal
from pathlib import Path

from demo.refund.cost import estimate_cost
from demo.refund.trace import format_trace, read_trace

EVIDENCE = Path(__file__).parents[1] / "evidence" / "0001-double-refund"


def test_publication_evidence_preserves_attempt_effect_separation() -> None:
    events = read_trace(EVIDENCE / "attempt-trace.jsonl")
    effects = json.loads(
        (EVIDENCE / "authoritative-effects.json").read_text(encoding="utf-8")
    )

    rendered = format_trace(events)
    estimate = estimate_cost(events)

    assert "RESPONSE LOST / OUTCOME AMBIGUOUS" in rendered
    assert "origin: MODEL" in rendered
    assert effects["final"]["refund_count"] == 2
    assert effects["final"]["refunded_cents"] == 40_000
    assert effects["verdict"] == "VIOLATION FOUND"
    assert estimate.total_cost_usd == Decimal("0.000476")
