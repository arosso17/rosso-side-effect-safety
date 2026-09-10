# Side-effect safety agent instructions

These instructions apply to everything under this directory.

## Required context

Before changing behavior, read:

1. `README.md`
2. `SAFETY_MODEL.md`
3. `docs/REPRODUCE.md` when changing experiment behavior

Read the relevant experiment record before changing an experiment that has
already been run.

## Product invariants

- The authoritative effect for the first scenario is a committed SQLite refund
  row, not a tool result or trace event.
- Keep attempt data outside the fake ecommerce business tables.
- Monetary values are integer cents internally and whole dollars at the first
  MCP tool boundary.
- A retry of one intended action must reuse its `operation_id`; two legitimate
  actions may have identical arguments but must have distinct operation IDs.
- Never report `SAFE` after finite testing.
- Default tests stop after the first violation; repeated characterization is an
  explicit mode added later.
- Live model calls must be opt-in and excluded from the default test suite.

## Implementation boundaries

- Use MCP Python SDK v2 APIs only.
- Prefer standard-library components until extraction into the CLI is earned.
- Do not add provider abstractions, generic observer interfaces, YAML config, or
  proxy infrastructure during the baseline demo.
- Never point the refund demo at a real ecommerce or payment system.

## Validation

From this directory:

```bash
uv run pytest
uv run ruff check .
```

Update durable user-facing documentation after verified behavior changes. If a
parent repository provides additional agent instructions, follow its
documentation protocol too.
