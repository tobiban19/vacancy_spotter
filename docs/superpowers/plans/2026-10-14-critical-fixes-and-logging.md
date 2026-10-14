# Critical Fixes and Logging Implementation Plan

> **For agentic workers:** Use subagent-driven-development, task-by-task with independent spec and quality reviews. Read the matching task brief; do not implement unrelated tasks.

**Goal:** Fix audited release blockers and add safe correlated diagnostics without deploying.
**Architecture:** Existing modular monolith, shared application services, SQLite transactions and durable delivery outbox. Keep public DTO compatibility where safe; intentionally reject insecure/ambiguous legacy payment callbacks.
**Tech Stack:** Python 3.11, FastAPI, aiogram, Telethon, SQLite/aiosqlite, React/TypeScript/Vite.

## Global Constraints

- Work in D:\Vacancy spotter, branch codex/critical-fixes-and-logging.
- Do not deploy, run live services, send real Telegram messages, rotate credentials, rewrite history or mutate private runtime files.
- TDD: add behavior regression tests, observe failure, implement, run covering tests and full suite before committing.
- Update README.md and docs/TECHNICAL_DOCS.md whenever contracts change.
- Only fake credentials/disposable databases; outbound network blocked in test runner, numeric loopback allowed for Windows asyncio.
- Python executable D:\Vacancy spotter\.venv\Scripts\python.exe. Existing full suite: 55 tests passed on base dd8b7f8.

## Task 1: Security and observability foundation

Files: backend/observability.py, backend/config.py, backend/auth.py, backend/api.py middleware/auth/webhook guards, backend/tests/conftest.py and focused tests, docs.
Interfaces produced: JSON logging setup, redaction, context manager for correlation, event logging; settings.validate_runtime(); fresh initData check; HTTP X-Request-ID/error envelope.

- [ ] Write regressions for missing/stale auth_date, missing/incorrect webhook secret, unsafe production config and secret redaction/traceback/request ID.
- [ ] Run focused tests and capture the red result.
- [ ] Implement strict guards and correlated JSON logs with rotating file+console handlers; bounded safe frontend telemetry endpoint if needed for task 4. Do not log request bodies or credentials.
- [ ] Establish an isolated test runner/conftest: copy test source to disposable root or override all runtime paths before imports, fake credentials, no external sockets. Existing auth tests sign current timestamps.
- [ ] Run focused tests and full backend suite; update docs, commit.

## Task 2: Transactional payments, eligibility and channel consistency

Files: backend/database.py, backend/models.py, backend/payment_service.py, backend/api.py subscription handlers, backend/bot_service.py payment callbacks, focused regression tests, docs.
Interfaces produced: persisted payment requests/decisions, atomic grant transaction; eligible subscriber selection; correct scoped channels; durable card/outbox repository methods for task 3.

- [ ] Reproduce nonadmin approval/replay, concurrent +7/+30 grant loss, false submission success, ban/expiry and channel UPSERT/tenant-choice errors in tests.
- [ ] Implement additive migrations, transaction ownership using independent write connections or equivalent safe isolation; pending payment IDs, one grant per request and bounded receipt validation. Legacy unbound callbacks cannot grant days.
- [ ] Persist request plus queued admin notification, return saved/queued state even before send; no false delivered claim. Central eligibility applies to generation/delivery, not merely API login.
- [ ] Add source/job unique identity, unique user-job cards and outbox schema/APIs (enqueue, atomic lease claim, mark delivery/retry/failed). Preserve existing cards; do not destructively deduplicate them.
- [ ] Correct UPSERT lookup and separate recommended catalog from user-selected custom sources. Startup does not silently enable custom sources or erase selections.
- [ ] Run covering concurrency/replay/migration tests and full suite; update docs, commit.

## Task 3: Unified durable ingestion and supervised runtime

Files: backend/ingestion_service.py, backend/delivery_worker.py, backend/telethon_parser.py, backend/matching_service.py, backend/api.py incoming handler, backend/server.py, app.py, health/readiness tests, docs.
Interfaces consumed: task 1 observability/config and task 2 transactional repository/outbox/payment APIs.

- [ ] Tests for duplicate/concurrent inputs, failed sends, retry after reopening DB, permanent errors, AI fallback correlation and accurate running/readiness/shutdown state.
- [ ] Parser and webhook use one ingestion service with classification, eligibility, idempotency and safe stable source identity. Persist delivery before send; worker processes card and admin-payment notifications with retry/backoff/leases and bounded concurrency.
- [ ] Correlate AI success/failure/fallback and all persisted job/delivery steps. Persist draft source/fallback context or otherwise expose that state accurately. Capture unexpected exceptions with redacted traceback.
- [ ] Remove import-time live client/thread startup. One validated supervised entrypoint controls API, polling, parser and outbox; reset health on failure and close all resources. Keep singleton requirements documented.
- [ ] Add liveness/readiness endpoints and component state. Do not report ready before Telegram connection success. Document catch-up/source activation limitations precisely if not covered by critical fixes.
- [ ] Run focused durable delivery/runtime tests and full suite; update docs, commit.

## Task 4: Frontend diagnostics, honest UI and safe deployment packaging

Files: frontend/src/api.ts, App.tsx, AdminPanel.tsx, main.tsx, frontend observability/ErrorBoundary, deployment scripts/configs, example env, tests/docs.

- [ ] Regressions for manual application label/status, bounded safe source upload allowlist/SSH/remote exit handling; validate frontend auth/correlation/telemetry with focused tests or runtime stub.
- [ ] Frontend obtains a short JWT from valid Telegram initData, propagates request IDs, displays correlated errors, captures unexpected errors with ErrorBoundary/global listeners and sends only bounded sanitized diagnostics. No hidden null/[] masking of unexpected initial-load errors.
- [ ] Payment UI reports stored/queued request and real server status. Manual application button never says an employer message was sent.
- [ ] Deploy packages only allowlisted source/build files, never .env/data/SQLite/WAL/sessions/backups; verifies SSH host key, propagates failure, and uses configured HTTPS upstream. Correct conflicting entrypoints. Do not run deploy scripts.
- [ ] Add reproducible dependency/test declarations and security scan gate where feasible; no unsolicited major-stack migration.
- [ ] Run backend suite, frontend build and contract probes; verify runtime hashes and no secrets staged. Update audit-resolution matrix/docs, commit and push.

## Final Gate

- [ ] Independent whole-branch review; fix all critical/important findings with covering tests and re-review.
- [ ] Full isolated backend tests, frontend build, redaction/correlation/durable-state probes; runtime hashes unchanged.
- [ ] Clean working tree and commit/push verified. State manual token rotation and live/deployment verification limits explicitly.
