# NEX CODEX project state

Updated 2026-10-28. Version **1.4.1**. Focused community and template/source store. This replaces the earlier broad all-in-one command surface at the user's request.

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
- Configurable Unicode/custom Discord emoji slots for welcome/leave, ticket, giveaway, announcements, products, shop and help. Supplied cyan artwork split into 49 uploadable PNGs. Startup automatically uploads/reuses all 49 application-owned icons with the existing bot token, restores 14 theme defaults before cog registration and preserves per-server overrides. No manual upload or command is needed. An optional /installemojis command still supports server-owned overrides. Invalid input rejected; actual custom-emoji availability requires Discord verification.
- Preserved SQL persistence, source/template CRUD, free-claim limits, immutable order snapshots, manual QR/UPI payment review, private ticket overwrites, protected files/links/instructions, duplicate approval protection and refund revocation.
- Dashboard matching the focused scope, owner-only product writes and owner/administrator settings writes, staff/reviewer payment queue, customer order history and public catalogue. OAuth sessions/state/CSRF/live membership checks retained.

## Animated help update

- Refined orbital emblem, glass cards, cyan/teal/blue category accents and subtle looping particles. All four 900×660 GIFs contain 32 frames, loop over 3.2 seconds and remain below 270KB. No startup image rendering is required.
- Original NEX-branded cyan/blue animated help artwork inspired by the supplied reference; only active feature families shown. Four matching GIFs bundled in the ZIP, with no third-party brand copied.
- Home/category dropdown and real Previous / Home / Next buttons, synchronized selection and disabled controls on timeout; actual registered commands and owner/admin visibility preserved. Personal controls, deferred uploads and old attachment replacement; fallback to text when artwork/Attach Files is unavailable.
- `/help` works for prefix/slash forms. Optional build script uses Pillow/fonts only to regenerate assets; Wispbyte needs the shipped files and existing runtime requirements.
- Extracted polished help release:79 affected tests passed on Python3.11.18 and Python3.14.4 (2 and1591 upstream warnings), covering media, navigation, actual prefix invocation/slash deferral, owner/admin visibility, existing commerce controls, packaging and public dashboard health. Prior matching database/payment/ticket/application-emoji checks are reused; the full suite was not rerun for this help-only update. compileall/import/27-command serialization/blank-token startup checks passed on both runtimes. All four GIFs fully decoded; cloud Chromium confirmed animation playback and mobile scaling without overflow. Live Discord media rendering remains unverified without a token.

## Validation

The extracted automatic-startup ZIP passed the **151-test full suite on Python3.11.18 and Python3.14.4** (2 and1498 upstream warnings). A subsequent transport-error fix added one synthetic disconnect case; the complete **11-test application-startup module passed again on both runtimes** (1 and354 warnings). Other matching suite results were reused; that startup revision contained 152 cases. All external API calls are mocked. Checks cover default-on startup, 49 uploads/restart reuse, actual returned IDs in embeds/buttons, setup ordering, overrides, partial failure/resume, missing/invalid assets, capacity, disable, HTTP/transport denial, missing identity and bounded timeout. Both runtimes passed compileall, pip check, module imports, 27-command serialization, blank credential checks and controlled missing-token startup.

SQLite schema initialization, all-module imports, controlled missing-token startup, archive/source/credential checks and responsive public dashboard checks are recorded in the accompanying audit. The earlier PostgreSQL17 schema/payment/concurrent-approval smoke is reused for unchanged SQL/model/payment behavior; this revision has no fresh PostgreSQL run.

No real bot token, live OAuth consent or Wispbyte access supplied. Live command visibility, welcome/leave events, tickets, DMs, receipts and provider deployment have not been verified. No actual payments processed. Optional AI/hosting are outside active scope. Previously inspected Emulate v0.0.1 does not provide Discord gateway/OAuth support.

## Known limits

- No schema upgrade migration chain, durable outbound queue, shared limiter, multi-bot worker leasing or automated data retention/export UI. Use one bot and one dashboard worker with persistent database/files.
- Discord sends/channel creation and SQL commits are not atomic. Interrupted sends can be retried twice; missing ticket channels need staff repair. Tickets are read-only to customers when closed; transcripts contain latest500 messages only.
- External download links can be copied; local files recheck authorization/path containment. Screenshot URLs can expire. No malware scanning/encrypted file store/web upload UI.
- Dashboard advanced settings use validated JSON; it does not provide separate operational ticket/giveaway pages. Those commands run in Discord. Historical settings fields remain but removed processors do not execute them.
- Discord controls installation permissions; server setup authorization does not enforce who may originally invite the application.
- Application emoji loading requires a working bot token/network and space within the application's 2000-emoji limit. Missing assets/API failures/timeouts leave Unicode fallbacks and console guidance; restart resumes partial work. Explicit custom overrides need access to their source emoji; no claim of live verification. Repost existing public panels to refresh their appearance after styling changes.
- No payment gateways, bank verification, automated approval/refund, hosting deployment or perfect abuse/alternate-account detection.

## Startup and recovery

- `.env` and `main.py` are included. Set DISCORD_TOKEN and OWNER_IDS, enable Members/Message Content intents, invite with bot+applications.commands and run `python main.py` from the project directory. Automatic sync is enabled; COMMAND_GUILD_IDS optionally publishes directly to specified servers.
- Start `main.py` (emojis load automatically) → `/setup` → `/welcome` and `/leave` → configure staff/payment roles and QR details → `/addproduct` → edit terms → publish → `/createshop`.
- Keep populated .env, database and private files when updating. Release ZIP always contains a blank starter generated from .env.example, never local secrets/private products.
- Failed purchase-ticket creation: resume the existing order with /ticket. Failed delivery: fix permissions/DMs/files and retry the same order. Do not create a second payment simply because a Discord operation failed.
- Optional dashboard: set SESSION_SECRET and OAuth credentials, then run the documented Uvicorn factory as a separate service. Wispbyte panel deployment itself is unverified.
