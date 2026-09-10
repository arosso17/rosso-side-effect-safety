# 0003 — Idempotent reference remedy

- Status: completed
- Date: 2026-09-10
- Property under test: exactly once
- Verdict: `NO VIOLATION OBSERVED`

## Purpose

Demonstrate that the same commit-then-disconnect fault and repeated refund
attempt produce one business effect when both attempts carry a stable business
operation ID and the server stores an atomic receipt.

## Design

The agent runner creates one operation ID for the intended refund and injects it
into every `refund_order` dispatch. Both servers receive the same ID:

- The unsafe server records the ID but performs every attempt.
- The safe server claims the ID, inserts the refund, and stores its receipt in
  one SQLite transaction.
- A repeated ID with matching arguments returns the original receipt with
  `reused: true`.
- A repeated ID with different arguments is rejected.
- Distinct IDs allow legitimate refunds with identical order and amount values.

## Verified transport procedure

The non-billable integration test starts the safe MCP server with the
`commit_then_disconnect` fault, sends the same operation twice, and observes
SQLite directly:

```bash
uv run pytest \
  tests/test_fault_transport.py::test_idempotent_server_reuses_committed_receipt_after_response_loss
```

Observed result:

```text
attempt 1 → refund + receipt committed → response lost
attempt 2 → original receipt returned  → reused: true

refund effects: 1
refunded total: $200
```

The broader store suite also verifies argument-conflict rejection and two
legitimate identical refunds with distinct operation IDs.

## Live model run

The controlled agent ran the remedy end to end with:

```bash
uv run python -m demo.refund.experiment idempotent
```

The live run completed at `2026-09-10T05:20:36Z`. The first refund committed,
the MCP process exited before returning its response, and a new model decision
repeated `refund_order` with the same stable operation ID. The safe server
returned the original refund ID with `reused: true`.

```text
refund attempts: 2
refund effects:  1
refunded total:  $200.00

IDEMPOTENT RECEIPT REUSED / NO NEW EFFECT
NO VIOLATION OBSERVED
```

The run used four model turns, three MCP tool attempts, 1,510 input tokens, and
113 output tokens. Its estimated cost is `$0.000438` using the pricing snapshot
dated 2026-09-09. The ignored runtime trace is:

```text
.run/refund-idempotent-20260910T052025Z.jsonl
```

Sanitized attempt and authoritative effect evidence is stored under
`../evidence/0003-idempotent-reference/`.

## Limitations

SQLite can store the refund and idempotency receipt in one transaction. A
separate payment provider cannot automatically share that transaction. It must
accept the stable key or the integration needs authoritative reconciliation.

`NO VIOLATION OBSERVED` describes the tested executions only; it is not a
universal safety certification.
