# NEX CODEX project state

Version **1.7.0** · Focused Discord bot · 2026-10-28.

## Active scope

43 slash commands plus prefix equivalents/hidden owner sync. The bot includes: animated help and mention shortcuts; direct shop/channel/payment/welcome/leave/ticket/giveaway setup; Template/Bot products and persistent shop; free claims/manual QR-UPI payments/independent review/private delivery; tickets/transcripts; giveaways; say/broadcast; permission/hierarchy checked kick/ban/warn/history/timeout and safe role controls.

Product public IDs are eight characters by default and can be changed to a unique3–16 character slug using /productid. Product-name autocomplete on product/productedit/productpublish/productid/buy shows owner drafts and only published products for customers, with up to25 matches per query. Internal database IDs and existing order links remain immutable.

Consistent cyan/blue theme:49 automatic application emojis, five900×820 animated help pages, ten compact banners. GIF command index comes from registered cog definitions; management commands remain in authorized readable help. Real controls live below images. Owner guide lists commands/examples. No web/AI dependencies.

## Rejoin rule

Owner/admin can enable /leavesetup restrict_rejoin:true; default disabled. Departures observed while enabled are stored. Returning blocked members are kicked only when bot permissions/hierarchy allow. Bot owners/server owner/admins/configured staff/reviewers/bots are exempt. /rejoinallow clears a user; disabling stops enforcement. Existing blocks apply again on re-enable. Discord removals can include moderation kicks, so this is an intentional access rule, not abuse attribution. No automatic leave-time ban. Failed kicks are logged as unavailable.

## Removed scope

Dashboard/FastAPI/OAuth/web deployment, unused AI/provider adapters, automod/antinuke, premium/XP/rewards/referrals/reviews/reminders. Moderation was restored and expanded after the user's later request. Old unused database tables are retained without executing those features. Product customer-rating UI removed because review creation is unavailable.

## Data and deployment

Schema2 initialization migrates schema1 by adding/backfilling a unique per-guild product code and renaming source category to bot. Existing internal IDs/orders/foreign keys are preserved. Initialization is idempotent, rejects unknown future schema versions and never drops historical tables. Original product columns/historical hosting cleanup remain for old orders; new hosting sales are blocked. Known retired guild settings are ignored on read; new retired writes fail validation.

Back up before upgrading; keep the populated.env, database and private product files. Python3.11+, pip install -r requirements.txt, python main.py. One bot process per token/database; process-local limits/locks. Future schema changes require explicit migrations. Discord sends and SQL commits cannot be atomic; reconcile with saved order IDs. Copied download links cannot be revoked by the bot; receipt URLs may expire. Giveaway prize fulfillment is manual. Refund commands only record an external refund.

## Validation

Final results are in NEX_CODEX_AUDIT.md accompanying the ZIP. Tests use synthetic SQLite/Discord mocks; prior-schema upgrade uses exact pre-change ORM definitions. Live Discord gateway/uploads, actual manual payments and Wispbyte hosting remain unverified without user credentials. PostgreSQL dialect compatibility is checked separately from live PostgreSQL deployment.
