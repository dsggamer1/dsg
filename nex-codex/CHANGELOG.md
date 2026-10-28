# Changelog

## 1.7.0 — 2026-10-28

- Add short editable public product codes and scoped product-name autocomplete. Keep immutable internal order links; migrate schema1→2 safely and rename source category to bot.
- Add shop/channel/welcome/leave/ticket/giveaway setup commands; keep automatic private purchase tickets and manual payment approval.
- Add permission/hierarchy checked kick, ban, warning/history, timeout and safe give/take role controls.
- Add opt-in persistent kick-on-rejoin rule with exemptions, default disabled, clear command and failed-action logging.
- Expand help to five900×820 animated pages with command index and live readable usage; retain consistent cards and actual controls.

## 1.6.0 — 2026-10-28

- Ship only the focused Discord bot: remove dashboard/OAuth assets, web deployment and dependencies, unused AI/provider and inactive moderation/automod modules.
- Remove premium, XP, reviews/rewards/referrals and reminder code; simplify environment and configuration to active features.
- Preserve all 28 active commands, existing marketplace/payment/ticket protections and themed artwork. Remove unreachable customer-rating UI.
- Read old guild settings compatibly without restoring retired features; retain existing database tables and historical order cleanup. No destructive data migration.
- Replace broad documentation with bot-only setup and keep the complete Hinglish owner command guide.

## 1.5.0 — 2026-10-28

- Extend the NEX visual theme to community/store cards, with ten compact bundled headers and graceful media fallback; preserve actual payment QR and configured shop images.
- Add owner/admin paymentsetup with role/category selectors, validated UPI/QR configuration and additive staff membership; retain owner-only product management and independent payment review.
- Add personal setup walkthroughs, product category choices, clearer draft next steps and complete Hinglish OWNER_GUIDE.md.
- Reply to direct bot mentions with rate-limited personal Help/Shop shortcuts; preserve normal command dispatch and ignore automated messages.
- Add real Shop/Setup shortcuts below help navigation. Images remain visual; interaction lives in Discord components.

## 1.4.1 — 2026-10-28

- Refine all four original help animations with an orbital NEX emblem, glass cards, subtle particles and coordinated category accents; 32-frame, 3.2-second loops.
- Add real Previous / Home / Next buttons synchronized with category selection and personal interaction checks.
- Disable expired help controls after three minutes, tolerating deleted or inaccessible messages.
- Preserve owner/admin permissions, automatic emoji startup and manual QR/UPI shop flows.

## 1.4.0 — 2026-10-28

- Add a complete NEX CODEX animated help theme: cyan/blue cards, the supplied icon set and original Home/community/shop-ticket/giveaway GIF pages.
- Add Home navigation, matching per-category uploads and personal help controls while preserving live registered command lists and owner/admin access.
- Defer category uploads, replace prior attachments, close image streams and keep text help available if assets or Attach Files permission are missing.
- Bundle all four small GIFs in the complete ZIP and add an optional artwork rebuild script; no runtime Pillow dependency or manual GIF setup.

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
