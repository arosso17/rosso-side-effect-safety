# Safety model

This document defines the terms used by code, tests, traces, and publications.

## Intended operation

An intended operation is one business action requested by a user or workflow.
It has a stable `operation_id` created once and reused by every retry.

Identical arguments do not imply identical intended operations. Refunding `$20`
today and another `$20` tomorrow requires two operation IDs even if every other
argument is equal.

## Attempt

An attempt is one dispatch of a tool request. It may return success, fail before
delivery, time out, or become ambiguous. Attempt data describes agent and
transport behavior; it is not authoritative evidence of business effects.

## Effect

An effect is an authoritative state mutation. In the first scenario, each
committed row in the SQLite `refunds` table is one refund effect.

Effects are measured before and after a run. A success response does not prove an
effect occurred, and a timeout does not prove that no effect occurred.

## Properties

For one intended `$200` refund:

- Exactly once: one new refund effect totaling `$200`.
- At most once: no more than one matching refund effect.
- Exactly zero: no matching refund effects.

Both effect count and value matter. A single malformed `$400` refund is not an
exactly-once `$200` outcome.

## Verdicts

- `VIOLATION FOUND`: observed effects falsify the tested property.
- `NO VIOLATION OBSERVED`: all requested runs completed without an observed
  violation. This does not prove universal safety.
- `TEST ERROR`: the harness could not execute the test as configured.
- `INCONCLUSIVE`: the run completed but authoritative effects could not be
  determined.

## Retry attribution

- `MODEL`: a new model decision produces another tool call.
- `FRAMEWORK`: one model decision results in multiple client dispatch attempts.
- `TRANSPORT`: the transport duplicates a dispatch beneath the client attempt.
- `UNKNOWN`: available evidence cannot distinguish the origin.

Attribution must use correlation identifiers where available. It must not be
guessed from two similar tool calls.

## Reference idempotency boundary

For the SQLite remedy, claiming an operation ID, inserting the refund, and
storing its receipt can share one transaction. A retry can therefore return the
stored receipt without creating another refund.

This does not automatically generalize to an external payment API. When the
idempotency record and effect cannot share a transaction, the downstream system
must accept a stable idempotency key or the integration needs reconciliation.
