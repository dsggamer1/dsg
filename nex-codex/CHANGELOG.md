# Changelog

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
