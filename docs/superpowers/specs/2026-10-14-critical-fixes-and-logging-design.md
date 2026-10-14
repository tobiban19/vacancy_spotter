# Critical fixes and end-to-end logging

Approved scope: implement the architecture recommendations accepted by the user on 2026-10-14. Preserve FastAPI, aiogram, Telethon, SQLite and React. Work in `D:\Vacancy spotter`, commit and push reviewed changes, never deploy or run the live bot during implementation.

## Invariants

- Real `.env`, databases, Telegram session and their backups are never edited by tests, committed or uploaded. Tests use disposable databases, fake credentials and blocked external networking.
- No full rewrite, microservices or new paid monitoring service. Use a modular monolith, database-backed queues and JSON logging with rotation.
- Authentication checks fresh signed initData with required auth_date; regular UI exchanges it for a short JWT session. Missing webhook credentials disable ingestion. Production startup rejects placeholder secrets, insecure origins and an unconfirmed credential rotation.
- A payment request is persisted before notification. Administrator decisions require an authorized administrator and a persisted pending request; each request grants days once, atomically, with an audit record. Concurrent grants never overwrite one another.
- Banned/expired users are excluded consistently from delivery and generation. Existing records survive additive migrations; opening a database never overwrites user channel choices.
- Source ingestion is idempotent; card creation and delivery intent commit together. Delivery has persisted attempts, leases, retry/backoff and outcome. A transient failure remains recoverable after restart. External send/DB acknowledgement ambiguity is documented as at-least-once, never called exactly-once.
- The existing application button is a manual record of an application; it must not claim that the bot sent to the employer.
- API, bot, parser, AI, database/outbox and frontend diagnostics share request/trace/job/card/payment/delivery identifiers. Logs have timestamps, component, event, level, duration/outcome where applicable and redacted exception traceback. Tokens, initData, Authorization, resume/receipt/post bodies never enter logs.
- Logging failures do not prevent successful business operations; durable business state is the source of truth. Health/readiness reflects actual component state. Service shutdown closes resources and resets status.
- Source deployment excludes all runtime data, requires verified SSH host identity and checks command exits. Proxy upstream must use a configured HTTPS URL. No deployment command is executed for this request.

## Shape

Keep handlers thin around shared services: `observability.py` provides correlation/redaction/JSON handlers; repository extensions provide isolated transaction ownership, payment ledger and delivery outbox; `ingestion_service.py` unifies parser/webhook; `delivery_worker.py` performs bounded durable delivery. A single supervised entrypoint starts API and singleton workers. Frontend sends request IDs, uses a short session and reports bounded sanitized diagnostics through an authenticated endpoint.

## Release boundaries

The exposed bot token must be revoked via BotFather; code cannot prove that an external credential was revoked. Add a production credential-rotation gate and document the outstanding manual action. Do not remove Git history or change external credentials without an explicit operation. Production host/log availability is outside local verification, so no claim of a healthy deployed service is made.

## Verification

Regression tests must first fail for each audited behavior: stale auth, missing webhook secret, nonadmin/repeated approvals, concurrent grants, false payment success, banned/expired receivers, custom-channel UPSERT, duplicate ingestion, send failures/restart and secret leakage. Test HTTP errors and AI fallback correlation plus frontend build. Run the full suite on isolated data, check source/runtime hashes, inspect the complete branch through independent review, and verify push completion.
