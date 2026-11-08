# Codex / Copilot continuation brief

Owner request: build an almost fully automated SPYBOT dashboard. **Execution explicitly means sending a qualifying-signal notification to the owner's phone/computer. No brokerage connection or orders.** Continue from branch `feature/spybot-alert-platform`, not from a fresh mockup.

## Read first

1. Repository `AGENTS.md` and `.github/copilot-instructions.md`.
2. `platform/README.md`.
3. `platform/docs/ARCHITECTURE.md` for boundaries/milestones.
4. `platform/docs/API_RESEARCH.md` for official routes, authentication, caveats and sources.
5. `platform/deploy/README.md` for production prerequisites.

## Implemented and checked

- FastAPI private API and responsive graphite/lime dashboard with SPY/QQQ, overview, signal inbox, strategy lab, connections and explicitly synthetic demo.
- Candidate envelope validation: strict evidence, coherent finite levels, aware timestamps, source IDs, stale/future/non-live rejection, pending strategy default.
- Local SQLite outbox with atomic enqueue/claim, deduplication, expiry, bounded retries and uncertain-delivery state.
- Pushover adapter and worker; disabled by default. API acceptance is not device delivery.
- Read-only Unusual Whales REST adapters, SPY/QQQ `gex_strike` channel allowlist, capped REST concurrency, bounded reconnect/backoff, heartbeat timeout, injected gap-reconciliation hook, raw-event archive and a synthetic offline replay fixture. No live provider connection or historical backfill has been tested.
- PostgreSQL store and initial migration use transactional outbox writes and `FOR UPDATE SKIP LOCKED` claims. No PostgreSQL server integration, parallel-worker, or restart-recovery test has run.
- Per-source live/freshness/completeness/entitlement gates, XNYS holiday/early-close calendar, and version-hash readiness gate are implemented. No strategy rules are configured; evaluation therefore remains blocked and does not produce a candidate.
- Twenty-two unittest checks pass, JavaScript syntax passes, Python compilation passes; independent agent reviewed API/outbox/UI and requested fixes which were applied.
- Browser visual testing was attempted with Playwright default and system Chromium. Default binary was absent; system Chromium aborted before page load with `socket() failed: Operation not permitted` in ProcessSingleton. No browser screenshots or visual-pass claim.
- No live feeds connected, cloud resources provisioned, backtests run, or real push notifications sent. Existing dashboard and legacy skill remain untouched.

Run checks from `platform/`:

```bash
python -m unittest discover -s tests -v
node --check web/app.js
python -m compileall -q server tests
```

## Next implementation slice

Validate the new Unusual Whales adapter against current official response schemas and a real, authorized Advanced account before use. Replace/augment the synthetic replay fixture with safely captured provider fixtures. Implement source-specific normalization and actual bounded REST gap reconciliation; the current recovery hook has no default provider backfill and must not be described as recovered data. Keep raw events separate from normalized observations. Do not treat configured credentials as verified health.

Run PostgreSQL migration, concurrent claim, crash/restart, idempotency, backup and restore integration tests against a real test database. SQLite remains development/single-host only and must not be deployed to Cloud Run as persistent state.

Follow with deterministic strategy-rule execution, source conflict handling, source-specific verified entitlements, no-chop/event gates, and version-bound owner approval. Current candidate booleans are trusted-producer assertions, not independent evidence verification. All strategy parameters in the owner's sign-off remain proposed/unapproved; do not invent thresholds to activate signals. If approved rules are unavailable, leave strategy activation and real notifications disabled.

After those pieces work, add bounded OpenAI Responses/Exa research asynchronously, identity-aware cloud deployment (recommended Cloud Run + worker pool + Cloud SQL + Secret Manager), monitoring and labeled device tests. Use separate credentials for the background app; chat connector access is not a deployment credential.

## Acceptance criteria

- Missing/stale/delayed/conflicting data cannot create a real signal.
- A signal includes strategy version, sources, observation/expiry, reason and invalidation.
- Exit is separate from reversal; no automatic direction flip on a small pullback.
- No duplicate logical outbox entries on source replay; no expired push after recovery.
- Uncertain provider delivery is visible; never claim exactly-once device push.
- Demonstrate fresh data, recovery and delivery with real evidence before describing automation as live.
- Keep secrets out of source/browser/logs; no broker/order API dependencies.
- Preserve existing repository work and make focused, reviewable commits/PRs.

This brief is a handoff, not a production-readiness certification. An assigned issue or opened draft PR does not by itself prove a remote agent started running.
