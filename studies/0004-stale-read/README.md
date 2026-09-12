# Study 0004: stale-read recovery

This folder freezes a 300-trial protocol before any confirmatory model call.
It asks whether a stale reconciliation read can make a state-aware AI agent
repeat a refund that already committed, and whether an idempotent tool boundary
keeps that same retry from creating a second effect.

- [Human-readable preregistration](PREREGISTRATION.md)
- [Machine-readable plan](plan.json)
- [Exact trial order](order.json)
- [Checksums](SHA256SUMS)

Verify the preregistration without an API key or third-party package:

```bash
python studies/0004-stale-read/verify_preregistration.py
```

The result verifier is deliberately included before data collection:

```bash
python studies/0004-stale-read/verify_results.py
```

Before result files exist, the second command verifies the preregistration and
reports that it is in preregistration-only mode. A later commit may add the
registered result data and a results document. The preregistration, plan, order,
and verifier code must remain unchanged after live execution begins.

This package contains study evidence only. It does not publish the private
runner or later private product source.
