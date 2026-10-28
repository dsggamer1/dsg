# NEX CODEX project state

Updated: 2026-10-28. Version: 1.1.0. Status: **runnable foundation; not every item in the master specification is finished**.

## Implemented

- Python modular bot, automatically published hybrid slash/prefix commands, four-category command center, consistent cyan embeds, confirmations, paginated storefront/product dropdowns, customer-bound checkout buttons, safe role dropdowns and persistent giveaway buttons. Slash acknowledgment precedes slow operations; environment prefix works until a server override is saved. `/setup` and `/diagnostics` guide administrators.
- SQLAlchemy persistent schema v1, SQLite WAL/foreign keys and PostgreSQL compatibility; serialized transactions, audit records, UUID orders and immutable purchase snapshots.
- Ban/unban/kick/timeout/untimeout/warn/purge/history with permission/hierarchy checks, confirmations for destructive operations, reasons and actor identity.
- Configurable spam/repetition/mention/invite/caps/blocked-domain automod with exemptions; log/delete actions, no heuristic autobans.
- Supported Discord audit-event burst detection persisted across restarts, deduplication, exemptions, incident records and alerts.
- Welcome/leave templates and embeds, safe auto-role, message edit/delete logging where events/cache permit, safe self-role selection and staff role tools.
- Server/member/avatar/role/channel info, ping/about, polls, prefix/configuration, respectful dice utility, XP cooldowns/levels/reward roles/leaderboards, saved reminders.
- Giveaways with saved entries, secure random winners, reroll history and restart recovery.
- Product CRUD/publish/archive, category/search/page browsing, availability, terms, minor-unit prices, delivery type; Discord staff product creation/editing/publication.
- Free claims, claim limits/cooldowns, duplicate prevention, entitlements, staff restrictions and appeal tickets.
- Paid confirmation → order → private ticket → Discord receipt submission → independent authorized approval/rejection → entitlement → private delivery.
- Ticket reservation/recovery, private overwrites, staff claiming, close/reopen, duplicates prevented and bounded transcript export.
- Payment config/role checks, self-review prohibition, duplicate approval protection, rejection/resubmission, manual cancellation/refund recording. No automated financial transfers.
- Protected local files, HTTPS links and instructions; download authorization, traversal/symlink checks, private DM delivery and recorded initial delivery success.
- Named premium grants, temporary/lifetime expiry, grant/revoke/extend/inspect and server-side entitlement checks.
- Product reviews/rating averages/moderation, optional referral points, unique reward ledger, current-member referrer checks and no self-referrals.
- Branded responsive dashboard: public homepage/catalogue/product pages/guide, server chooser, staff overview/product editor/payment queue/premium/configuration, customer orders/delivery.
- OAuth state, opaque server-side sessions, CSRF, current Discord guild role checks, request size limits, secure headers/cookies configuration, process-local sensitive-action limits.
- Read JSON APIs for health/public products/customer orders/admin settings; delivery secrets omitted from public output.
- Optional configurable chat-completions adapter with cooldowns and safe failures, disabled without credentials and guild opt-in.

## Verified locally

- **101 pytest tests passed on Python 3.11.18 and 3.14.4**, run from the extracted ZIP using independently installed requirements. SQLite uses synthetic fixtures and mocked Discord/OAuth responses. Includes concurrent approvals/claims, prefix invocation, automatic sync, interaction deferral, storefront buttons, protected downloads and offline command serialization.
- Upstream deprecation warnings on Python 3.14: discord.py uses asyncio.iscoroutinefunction; Starlette warns about httpx TestClient. No failed tests from those warnings.
- PostgreSQL **17**: real local database initialization and paid flow, four concurrent approval attempts with one success, entitlement and delivery; PostgreSQL DDL compilation for every table. Full pytest suite not run against PostgreSQL.
- `compileall`, dependency consistency, schema initialization and safe missing-token exit checked.
- Shared Chromium desktop (1440×1100) and mobile (390×844) public dashboard checks, marketplace navigation, no mobile horizontal overflow and working menu toggle.
- No live Discord, OAuth consent, actual payment, external file delivery, AI or Wispbyte panel deployment has been tested. No real credentials were supplied. Available Emulate v0.0.1 catalog inspected; no matching Discord/chat-completions emulator is available.

## Incomplete features and known limits

1. **Antinuke containment/recovery:** alerts only; no automatic role stripping, quarantine, channel/role recreation or perfect detection. Audit access/events depend on Discord permissions and intents. Offline events are not backfilled.
2. **Dashboard breadth:** settings use one validated JSON editor; separate visual pages for every moderation/welcome/leveling/giveaway setting, ticket operations, moderation case browsing, giveaway creation and detailed sales analytics are unfinished. Those operational commands run in Discord. Management lists/queues are bounded, not a full analytics suite.
3. **Premium plans/features:** named entitlements work; priced plan catalogue, payment-linked premium purchase, expiration notifications and actual premium-exclusive feature gates are unfinished. No premium-exclusive benefits are advertised.
4. **Hosting deliberately excluded:** the user narrowed scope to server templates and bot source code. Hosting commands/routes/new product categories/provider interfaces are removed. Legacy hosting rows/columns remain for database compatibility; historical hosting orders cannot be newly approved or delivered. No existing schema data is deleted.
5. **Rewards/referrals:** fixed configurable referral earning rule only; referral-code issuance, invite attribution, richer earning policies and redemption are unfinished. No reliable alternate-account detection.
6. **Freebie protection:** duplicate detection, limits, membership logs, manual restrictions and appeal tickets work. Automated abuse scoring, dedicated staff flag queue and formal appeal workflow are unfinished. Leaving never causes an automatic ban.
7. **Delivery reliability:** initial DB processing is idempotent, re-downloads intentional. Sending to Discord and committing to SQL cannot be exactly-once; crashes may duplicate notifications/files. Link recipients can copy links; use local protected files for per-request authorization. Receipt URLs may expire. No encrypted file store, malware scanner or upload UI.
8. **Tickets:** one bot process expected; individual Discord channel changes and DB commits are not atomic. Missing/deleted channels require staff repair. Closed tickets remain visible but read-only to their customer. Transcripts export only the most recent 500 messages; no permanent transcript archive/retention automation.
9. **Operations:** schema initialization only, no upgrade migration chain yet. No Redis/shared limiter or multi-worker task leasing. Sensitive writes serialize globally for integrity; load testing and multi-instance scale work remain. Expired web sessions/states are purged by the running bot worker.
10. **Notifications and logging:** some failures persist for retry (reminders/giveaway announcements); no backoff/dead-letter admin UI. Message logs depend on cache/event availability. No scheduled backup or customer data export/deletion UI.
11. **Provider integration:** real Discord/OAuth/intents/permissions, AI models must be configured and verified in staging. The project contains no real payment setup, products, private files, customers or tokens.
12. **Testing/deployment:** tests run on Python 3.11.18 and 3.14.4 on Ubuntu 26.04. Python 3.12–3.13 and other platforms have not been exercised. Production TLS, DNS, reverse proxy and systemd examples require operator configuration. Security review/load testing should continue before public sales.

## Configuration file follow-up

A `main.py` hosting entry point is included; run `python main.py` from the project directory. Hosting-panel upload guidance is in README; the Wispbyte panel itself has not been tested.

A starter `.env` is now included with empty credential fields. Fill it locally before starting Discord or the dashboard. Because the starter is tracked, do not commit your populated credentials. ZIP packaging uses only the example configuration for its starter `.env` and excludes the local `.env`.

## Recovery notes

- Run both processes from the project directory with the same database/environment.
- `python -m nex.db` safely initializes v1; it is not an upgrade migration.
- Start the web app with `uvicorn nex.dashboard.app:create_app --factory --port 8000 --no-access-log`.
- Start the bot with `python main.py`; slash commands sync automatically. Optional COMMAND_GUILD_IDS publishes directly to specified servers; owner-only `!sync` retries publication.
- Failed ticket creation: keep the order; retry `/ticket order_id:<ID>`. Never generate a replacement payment simply because Discord failed.
- Failed delivery: retry `/deliver` or authenticated dashboard access after fixing DM/file permissions. Entitlement remains recorded.
- Retry giveaway/reminder worker runs every 30 seconds; it processes overdue work after a restart.
- Preserve DB, private product directory, environment and backups. Do not store backups or environment files in public assets.

## Next work

Prioritize live staging Discord/OAuth verification, individual configuration UI forms, ticket/moderation dashboard pages, durable outbound delivery queue with bounded retry/backoff, versioned migrations and retention tooling; then actual premium benefits.

## ZIP audit repairs (v1.1)

- Automatic slash publication, optional immediate guild sync, initial slash deferral and correct configurable prefix; controlled token/intents errors.
- Stylish dynamic help and server setup, product cards, paginated select storefront and confirmation checkout; staff can run the store entirely through Discord.
- Protected staff/payment roles from self-service/automatic assignment, repaired existing-ticket private overwrites, bounded API pagination and malformed-link handling.
- Distribution allowlist excludes local environment overrides/logs/private products/backups; `.env` always generated from the blank example. Populated example secrets or database passwords stop packaging.
- Scope change intentionally removes active hosting while preserving historical database compatibility. Normal moderation/community features and manual QR payment review remain.
