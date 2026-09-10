# Refund demo

This directory contains the first vertical slice: a fake `$500` order, an
intentionally non-idempotent refund tool, and its idempotent reference remedy.

## Business state

`store.py` is the authoritative fake ecommerce system. `refunds` rows are
effects. MCP requests, timeouts, and tool responses are attempts and will be
recorded separately when the live agent is added.

Run a complete normal or faulted experiment:

```bash
uv run python -m demo.refund.experiment normal
uv run python -m demo.refund.experiment double-refund
uv run python -m demo.refund.experiment idempotent
```

Windows shortcut from the product directory:

```powershell
.\rosso.ps1 normal
.\rosso.ps1 double-refund
.\rosso.ps1 double-refund-neutral
.\rosso.ps1 idempotent
.\rosso.ps1 trace
.\rosso.ps1 cost
.\rosso.ps1 state
```

The wrapper resets state, runs the agent, renders the trace, lists the
authoritative refund rows, and evaluates the result. A detected violation exits
with status `1` by design.

`double-refund` uses the controlled retry policy from the recorded experiment.
`double-refund-neutral` applies the same fault without telling the model whether
to retry. `idempotent` keeps the controlled retry but routes attempts through
the safe server, which returns one durable receipt for the stable operation ID.
The selected policy and server mode are recorded in the trace.

Reprint the latest trace, estimate its token cost, and inspect effects without
another model call:

```bash
uv run python -m demo.refund.trace
uv run python -m demo.refund.cost
uv run python -m demo.refund.observe --details
```

Pass a JSONL path to `trace` or `cost` to inspect a specific run. The estimator
uses recorded usage plus a dated model-pricing snapshot; it does not query the
API or claim to reproduce an invoice.

Start the server:

```bash
uv run python -m demo.refund.server
```

The normal target is one call to `refund_order(order_id="1234", amount=200)`,
leaving `refund_count` equal to `1` and `refunded_cents` equal to `20000`.

## OpenAI agent

After configuring the ignored root `.env` as described in the product README,
run:

```bash
uv run python -m demo.refund.agent
```

The agent uses the OpenAI Responses API to choose between the two function
tools, then dispatches each selected operation through a local stdio MCP server
process. It writes model-turn and tool-attempt events to `.run/`; those attempt
events remain separate from SQLite effect state.

## Intentional defect

In `double-refund`, the first refund commits and the server exits before sending
the tool result. A one-shot marker ensures the next server instance responds
normally. The intentionally unsafe store records the stable operation ID but
does not use it for deduplication, so the model's retry creates a second effect.

## Reference remedy

`safe_server.py` receives a stable business operation ID generated once per
agent run. `refund_order_idempotently` claims that ID, inserts the refund, and
stores its receipt in one SQLite transaction. Repeating the same operation and
arguments returns the stored refund ID with `reused: true`. Reusing an operation
ID for different arguments is rejected, while two distinct operation IDs permit
two legitimate refunds with otherwise identical arguments.

## Safety

Use only the generated local database. This example is not suitable for real
money or customer data.
