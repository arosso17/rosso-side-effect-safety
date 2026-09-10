# Security policy

## Scope

This repository is intentionally unsafe demonstration software. It is designed
only for the included fake SQLite store and does not provide production payment
or agent-execution security.

## Reporting a vulnerability

Until a private reporting address is published, do not open an issue containing
credentials, customer data, exploit secrets, or private infrastructure details.
Contact the repository owner privately through the hosting platform instead.

## Credential hygiene

- Keep `OPENAI_API_KEY` only in the ignored `.env` file or a secret manager.
- Never attach `.run/`, databases, billing pages, or account screenshots to an
  issue.
- Revoke and rotate any credential that may have been exposed.
- Use only fake data and disposable local state with this project.
