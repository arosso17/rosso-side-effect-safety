from pathlib import Path

import pytest

from demo.refund.store import (
    DEMO_ORDER_ID,
    DEMO_ORDER_TOTAL_CENTS,
    IdempotencyConflictError,
    RefundStore,
)


@pytest.fixture
def store(tmp_path: Path) -> RefundStore:
    result = RefundStore(tmp_path / "store.db")
    result.reset()
    return result


def test_reset_creates_one_unrefunded_order(store: RefundStore) -> None:
    assert store.observe_order(DEMO_ORDER_ID) == {
        "order_id": DEMO_ORDER_ID,
        "total_cents": DEMO_ORDER_TOTAL_CENTS,
        "refund_count": 0,
        "refunded_cents": 0,
    }


def test_one_refund_creates_one_authoritative_effect(store: RefundStore) -> None:
    receipt = store.refund_order(DEMO_ORDER_ID, 20_000)

    assert receipt["committed"] is True
    assert store.observe_order(DEMO_ORDER_ID)["refund_count"] == 1
    assert store.observe_order(DEMO_ORDER_ID)["refunded_cents"] == 20_000
    effects = store.list_refunds(DEMO_ORDER_ID)
    assert len(effects) == 1
    assert effects[0]["refund_id"] == receipt["refund_id"]
    assert effects[0]["amount_cents"] == 20_000


def test_repeating_one_operation_creates_two_effects_in_unsafe_store(
    store: RefundStore,
) -> None:
    operation_id = "refund:order_1234:request_9876"

    store.refund_order(DEMO_ORDER_ID, 20_000, operation_id=operation_id)
    store.refund_order(DEMO_ORDER_ID, 20_000, operation_id=operation_id)

    state = store.observe_order(DEMO_ORDER_ID)
    assert state["refund_count"] == 2
    assert state["refunded_cents"] == 40_000


def test_idempotent_refund_reuses_receipt_without_repeating_effect(
    store: RefundStore,
) -> None:
    operation_id = "refund:order_1234:request_9876"

    first = store.refund_order_idempotently(
        DEMO_ORDER_ID, 20_000, operation_id=operation_id
    )
    retry = store.refund_order_idempotently(
        DEMO_ORDER_ID, 20_000, operation_id=operation_id
    )

    assert first["reused"] is False
    assert retry["reused"] is True
    assert retry["refund_id"] == first["refund_id"]
    state = store.observe_order(DEMO_ORDER_ID)
    assert state["refund_count"] == 1
    assert state["refunded_cents"] == 20_000


def test_idempotency_key_cannot_be_reused_for_different_arguments(
    store: RefundStore,
) -> None:
    operation_id = "refund:order_1234:request_9876"
    store.refund_order_idempotently(
        DEMO_ORDER_ID, 20_000, operation_id=operation_id
    )

    with pytest.raises(IdempotencyConflictError, match="different arguments"):
        store.refund_order_idempotently(
            DEMO_ORDER_ID, 10_000, operation_id=operation_id
        )


def test_distinct_operation_ids_allow_legitimate_identical_refunds(
    store: RefundStore,
) -> None:
    store.refund_order_idempotently(
        DEMO_ORDER_ID,
        20_000,
        operation_id="refund:order_1234:request_one",
    )
    store.refund_order_idempotently(
        DEMO_ORDER_ID,
        20_000,
        operation_id="refund:order_1234:request_two",
    )

    state = store.observe_order(DEMO_ORDER_ID)
    assert state["refund_count"] == 2
    assert state["refunded_cents"] == 40_000


@pytest.mark.parametrize("amount", [0, -1])
def test_refund_rejects_non_positive_amounts(
    store: RefundStore, amount: int
) -> None:
    with pytest.raises(ValueError, match="positive"):
        store.refund_order(DEMO_ORDER_ID, amount)


def test_refund_rejects_unknown_order(store: RefundStore) -> None:
    with pytest.raises(LookupError, match="does not exist"):
        store.refund_order("missing", 20_000)
