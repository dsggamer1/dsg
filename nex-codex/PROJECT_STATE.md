# NEX CODEX project state

Updated 2026-10-28. Version **1.3.0**. Focused community and template/source store. This replaces the earlier broad all-in-one command surface at the user's request.

## Active command contract

- Members: help, shop/product browsing, confirmed buy/free claim, orders, entitled delivery, support/purchase/appeal tickets, receipt submission.
- Staff/admin: say, broadcast, giveaways/rerolls, ticket operations/transcripts, manual order cancellation/refund records.
- Payment reviewers/admin: independent payment decisions; self-payment review is always denied.
- **Configured owner or server administrator:** welcome/leave setup and previews, configure, prefix, setup, diagnostics and installemojis.
- **Only bot owners listed in OWNER_IDS:** addproduct, productedit/publish, createshop and sync.
- Administrator status grants server configuration access; configured staff roles alone do not. Neither grants product/shop ownership. This is enforced in bot checks, services and dashboard routes. Discord guild owners have administrator privileges for their server; they do not become configured bot owners.
- Removed active moderation, general utility/fun, XP/role selection, reminders, premium, reviews/referrals/rewards and AI commands. Hosting remains excluded. Legacy service/model files and records are retained; unrelated moderation/security/XP event processors are inactive. Saved reminders still recover without exposing new reminder creation.

## Implemented in this revision

- Welcome/leave configuration commands with saved channel/templates, previews and disable option; themed join/leave embeds.
- Staff say/plain and broadcast/embed sends with input/channel checks, suppressed mentions, rate limits and successful-send audits.
- Owner-only persistent shop panels restored at startup. Each customer gets a new private paginated storefront, product select and confirmation checkout.
- Focused dynamic help with management controls shown according to owner/administrator access; runtime authorization independent of help visibility.
- Configurable Unicode/custom Discord emoji slots for welcome/leave, ticket, giveaway, announcements, products, shop and help. Supplied cyan artwork split into 49 uploadable PNGs. /installemojis uploads/reuses 14 theme icons and persists actual IDs, with permission, capacity and partial-failure handling. Invalid input rejected; actual custom-emoji availability requires Discord verification.
- Preserved SQL persistence, source/template CRUD, free-claim limits, immutable order snapshots, manual QR/UPI payment review, private ticket overwrites, protected files/links/instructions, duplicate approval protection and refund revocation.
- Dashboard matching the focused scope, owner-only product writes and owner/administrator settings writes, staff/reviewer payment queue, customer order history and public catalogue. OAuth sessions/state/CSRF/live membership checks retained.

## Validation

**141 tests passed on Python3.11.18 and Python3.14.4**, run from the complete extracted v1.3 ZIP in independent dependency environments. Tests cover owner/admin configuration, strict product ownership, prefix/slash permission checks, permission-aware help, emoji upload/reuse/partial failures, all 49 bundled PNGs, packaging and preserved payment/ticket/delivery checks. Live Discord API operations are mocked. compileall, pip check, all-module imports, 27-command serialization, SQLite initialization and controlled missing-token startup passed. Upstream dependency deprecation warnings remain (2 on Python3.11;1203 on Python3.14).

SQLite schema initialization, all-module imports, controlled missing-token startup, archive/source/credential checks and responsive public dashboard checks are recorded in the accompanying audit. The earlier PostgreSQL17 schema/payment/concurrent-approval smoke is reused for unchanged SQL/model/payment behavior; this revision has no fresh PostgreSQL run.

No real bot token, live OAuth consent or Wispbyte access supplied. Live command visibility, welcome/leave events, tickets, DMs, receipts and provider deployment have not been verified. No actual payments processed. Optional AI/hosting are outside active scope. Previously inspected Emulate v0.0.1 does not provide Discord gateway/OAuth support.

## Known limits

- No schema upgrade migration chain, durable outbound queue, shared limiter, multi-bot worker leasing or automated data retention/export UI. Use one bot and one dashboard worker with persistent database/files.
- Discord sends/channel creation and SQL commits are not atomic. Interrupted sends can be retried twice; missing ticket channels need staff repair. Tickets are read-only to customers when closed; transcripts contain latest500 messages only.
- External download links can be copied; local files recheck authorization/path containment. Screenshot URLs can expire. No malware scanning/encrypted file store/web upload UI.
- Dashboard advanced settings use validated JSON; it does not provide separate operational ticket/giveaway pages. Those commands run in Discord. Historical settings fields remain but removed processors do not execute them.
- Discord controls installation permissions; server setup authorization does not enforce who may originally invite the application.
- Custom emoji codes need access to their source emoji; no claim of live verification. Repost existing public panels to refresh their appearance after styling changes.
- No payment gateways, bank verification, automated approval/refund, hosting deployment or perfect abuse/alternate-account detection.

## Startup and recovery

- `.env` and `main.py` are included. Set DISCORD_TOKEN and OWNER_IDS, enable Members/Message Content intents, invite with bot+applications.commands and run `python main.py` from the project directory. Automatic sync is enabled; COMMAND_GUILD_IDS optionally publishes directly to specified servers.
- `/setup` → `/installemojis` → `/welcome` and `/leave` → configure staff/payment roles and QR details → `/addproduct` → edit terms → publish → `/createshop`.
- Keep populated .env, database and private files when updating. Release ZIP always contains a blank starter generated from .env.example, never local secrets/private products.
- Failed purchase-ticket creation: resume the existing order with /ticket. Failed delivery: fix permissions/DMs/files and retry the same order. Do not create a second payment simply because a Discord operation failed.
- Optional dashboard: set SESSION_SECRET and OAuth credentials, then run the documented Uvicorn factory as a separate service. Wispbyte panel deployment itself is unverified.
