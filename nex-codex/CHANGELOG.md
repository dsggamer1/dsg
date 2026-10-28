# Changelog

## 1.3.1 — 2026-10-28

- Correct the manual-only emoji workflow: main.py now automatically uploads/reuses all49 bundled application-owned emojis at startup by default, with the existing bot token. No installer command/server emoji permissions or slots are needed for the automatic artwork.
- Restore returned emoji IDs before cog/persistent-view initialization; keep explicit server overrides and the optional server-owned installer.
- Add progress logging, reuse after restarts/moving hosts, partial success/fallback handling, capacity checks and a180-second startup bound. AUTO_LOAD_EMOJIS=false disables this optional behavior.
- Document Wispbyte's complete-folder upload and extend startup/API-mock regression coverage. No live upload or Wispbyte deployment claimed.

## 1.3.0 — 2026-10-28

- Allow configured bot owners OR current server administrators to integrate/configure their server through commands, services and the dashboard, replacing v1.2's owner-only settings rule at the user's request.
- Keep addproduct/edit/publish, createshop and global sync restricted to OWNER_IDS. Preserve customer/staff/reviewer flows and payment self-review protection.
- Split the supplied cyan artwork into49 Discord-ready PNGs; add an administrator/owner emoji installer that reuses uploads and saves only actual Discord-returned IDs. Report partial uploads, capacity and permission failures honestly.
- Update help visibility, deployment permissions documentation, distribution asset inclusion and authorization/emoji regression coverage.

## 1.2.0 — 2026-10-28

- Narrowed active commands to welcome/leave, tickets, giveaways, say/broadcast, products/shop and help, plus owner setup and the purchase/payment/delivery subflows.
- Restricted product and configuration management to configured bot owners in Discord, service layer and dashboard; guild administrator/staff roles no longer grant those rights.
- Added owner welcome/leave setup, previews and disable controls; staff announcement commands with mention suppression, rate limits and audits.
- Added owner-only createshop with persistent public browse button and per-customer private storefronts.
- Added configurable Unicode/custom emoji slots and focused help that hides owner controls from nonowners. Requested user emoji list not received; defaults retained pending input.
- Removed active unrelated event processors and premium dashboard routes while preserving historical data and existing saved-work recovery.
- Extended command, owner authorization, dashboard, announcement, welcome/leave, emoji and persistent-shop regression checks.

## 1.1.0 — 2026-10-28

- Audited the complete source ZIP with isolated dependencies and Python 3.11/3.14 validation.
- Publish slash commands automatically at startup, optionally to configured guilds; defer interactions before slow operations, honor the initial environment prefix, and report token/intents failures clearly.
- Add a four-category command center, setup/diagnostic commands, paginated product dropdowns, branded product cards and personal checkout confirmation buttons.
- Add Discord staff product draft/edit/publication commands with exact decimal price validation.
- Remove active hosting commands, dashboard pages, product categories and provider interfaces at the user's request; preserve legacy database data and prevent historical hosting approval/delivery.
- Block staff/reviewer roles from self-service/automatic assignment; restore existing private-ticket overwrites, handle malformed automod links and bound public pagination.
- Restrict the distribution manifest, exclude environment overrides/runtime data, and reject populated secret examples.
- Add regression coverage for commands, checkout, failed delivery, role escalation, protected downloads and ZIP safety.


- Added `main.py` as a Python hosting-panel entry point and documented upload/startup instructions.
- Added a starter `.env` with empty credentials at the user's request.
- ZIP packaging generates its starter `.env` from the example, excluding local credential values.

## 1.0.0 — 2026-10-28

Initial runnable NEX CODEX foundation, added alongside the existing portfolio.

- Added modular discord.py bot with hybrid commands, categorized help, confirmation views, structured logging and lifecycle handling.
- Added SQLAlchemy schema v1 with SQLite/PostgreSQL support, persistent domain records, uniqueness constraints, transaction serialization and audits.
- Added moderation, guild configuration, safe role selection, welcome/leave, automod signals, audit-event security alerts, XP, polls, reminders and persistent giveaways.
- Added staff product management, free claims, snapshotted orders, private tickets, manual QR/UPI payment submissions/review, protected delivery and recorded manual refunds.
- Added hosting handoff/status adapter, premium entitlements, product reviews, points/referrals, freebie restrictions and appeal tickets.
- Added dark responsive FastAPI dashboard with Discord OAuth, opaque server sessions, CSRF, current role checks, bounded requests and redacted read APIs.
- Added tests for domain/security flows and offline Discord command registration, plus an explicit PostgreSQL smoke script.
- Added configuration examples, deployment examples, setup documentation and an explicit unfinished-feature ledger.
- Preserved the original static website. No payment gateway or live credentials were added.
