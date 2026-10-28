# NEX CODEX project state

Version **1.8.0** · Focused Discord bot · 2026-10-28.

## Active scope

41 slash commands plus prefix equivalents/hidden owner sync. Animated help/mention shortcuts; shop/channel/welcome/leave/ticket/giveaway setup; Template/Bot products with short editable IDs and autocomplete; free claims, priced catalogue and automatic private order tickets; owner-only product-access release and private delivery; tickets/transcripts; giveaways; say/broadcast; permission/hierarchy checked kick/ban/warnings/timeout/safe roles; optional rejoin restrictions with review/clear command.

## Payment removal

Paymentsetup/payment/paymentreview commands, QR/UPI/payee/reviewer configuration, receipt handling, submission/decision services, Payment ORM and payment banner removed. Fresh databases have no payments table. Existing payment history tables are left dormant to preserve historical user data, with no executing payment feature or API. Saved retired settings are ignored; new writes reject them. Currency and listed product prices remain catalogue fields.

Priced orders start awaiting_staff with no entitlement. Only configured bot owners use /orderfulfill with confirmation/reason to release access (ready). This records product release, not payment. Customer /deliver sends content privately and marks delivered only after success. Free claims immediately grant access. Staff can cancel/revoke orders. No transaction/refund functionality.

## Migration and compatibility

Schema3 initializes new installs and upgrades1/2 idempotently: short product codes/source→bot migration retained; pending/submitted/rejected legacy orders become awaiting_staff; previously paid orders with saved entitlement become ready; missing entitlement never unlocks; manually refunded orders become cancelled; delivered access and internal order links remain. No tables dropped. Old hosting cleanup retained; no hosting sales/providers.

Back up before upgrading; keep populated.env, database and private product files. Python3.11+, pip install -r requirements.txt, python main.py. One bot process per token/database; process-local limits/locks. Discord sends and SQL commits cannot be atomic. Copied download links cannot be revoked; transcript attachment URLs may expire. Giveaway prize fulfillment is manual. Rejoin enforcement defaults off, depends on member events and bot permissions, exempts owners/admins/staff/bots; no leave-time bans.

## Theme and removed scope

49 automatic application emojis, five900×820 animated help pages and nine compact banners; consistent cyan/blue. Dynamic help shows actual authorized commands; real controls are below images. No dashboard/OAuth/web/AI, automod/antinuke, premium/XP/rewards/referrals/reviews/reminders or hosting sales.

## Validation

See accompanying NEX_CODEX_AUDIT.md for actual results. Tests use synthetic databases and mocked Discord APIs; schema upgrade also uses exact pre-change ORM definitions. Live Discord gateway/sync/uploads and Wispbyte need credentials and remain unverified. PostgreSQL DDL compilation is separate from live migration testing.
