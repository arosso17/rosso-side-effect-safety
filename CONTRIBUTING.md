# Contributing

Thank you for helping make side-effect failures easier to reproduce.

## Before changing code

Read `AGENTS.md`, `README.md`, and `SAFETY_MODEL.md`. Keep the experiment narrow
and preserve the distinction between agent attempts and authoritative business
effects.

## Development

```bash
uv sync --frozen
uv run pytest
uv run ruff check .
```

The default test suite must not make OpenAI API calls. Live runs are explicit,
local actions performed only after configuring an ignored `.env`.

## Pull requests

- Explain the tested property and authoritative effect observer.
- Add or update the smallest relevant test.
- Update durable documentation when behavior changes.
- Never label finite test results `SAFE`.
- Do not include `.env`, API keys, databases, `.run/` output, customer data, or
  large recordings.

Bug reports are most useful when they include the side-effecting operation,
fault, retry origin if known, effect observer, reset procedure, and sanitized
trace.
