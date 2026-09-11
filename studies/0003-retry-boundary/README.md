# Can one retry policy survive both sides of an uncertain outcome?

This folder is the public preregistration for a 240-trial study of recovery
policy at the side-effect boundary.

The agent will receive the same lost-result message after two different events:

- the fault layer disconnects before sending the refund upstream, so no refund
  exists; or
- the refund commits upstream and the fault layer disconnects before returning
  the result, so one refund already exists.

Four prompt policies will be tested 30 times under each fault. The primary
outcome is whether authoritative SQLite state contains exactly one $200 refund.

- [Full preregistration](PREREGISTRATION.md)
- [Machine-readable plan](data/plan.json)
- [Frozen trial order](data/order.json)

The preregistration commit precedes all live model trials. Results and sanitized
trial records will be added in a later commit without rewriting this file or the
registered plan.
