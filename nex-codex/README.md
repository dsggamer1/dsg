# NEX CODEX

A focused Discord community and digital-product bot with a matching FastAPI dashboard. Current command families: **welcome, leave, tickets, giveaways, say, broadcast, products, shop and help**. Sell Discord server templates and bot source code using **manual QR/UPI payments**. Hosting is not offered.

## Install and run

Use Python **3.11+**. Run from the directory containing `main.py`, `.env`, `requirements.txt` and `nex/`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

The ZIP contains a blank starter **`.env`** (one leading dot). Set these locally before starting:

```dotenv
DISCORD_TOKEN=YOUR_BOT_TOKEN
OWNER_IDS=[123456789012345678]
SYNC_COMMANDS=true
COMMAND_GUILD_IDS=[123456789012345678]
```

Replace the example owner ID with **your Discord user ID** and the command guild ID with **your server ID**. These are different IDs. Both lists use valid JSON, without quotes around numbers. `COMMAND_GUILD_IDS=[]` uses global registration only; direct guild registration is useful for immediate visibility. Do not post your populated environment file or token. Keep your existing `.env` when updating the project. The tracked starter has empty secrets; never commit a populated copy.

`main.py` initializes the database and starts the bot. The database and `private/products/` need persistent storage. The tested Python 3.14 dependency snapshot is in `requirements.lock`; use `requirements.txt` on Python 3.11.

### Wispbyte / Python panels

Upload the **contents of `NEX_CODEX/`** together. Select Python 3.11 or newer, install `requirements.txt`, and set the startup file to `main.py` or command to `python main.py`. Enable hidden-file display to find `.env`. Wispbyte itself has not been accessed or tested. The dashboard is optional and needs a separate web process/port supported by your plan.

### Discord Developer Portal

1. Create an application and bot at <https://discord.com/developers/applications>.
2. Copy its current bot token into `DISCORD_TOKEN`. Enable **Server Members Intent** and **Message Content Intent** under Bot. Members supports welcome/leave; message content supports prefix commands and transcripts.
3. Invite with **bot** and **applications.commands** scopes. Grant View Channels, Send Messages, Embed Links, Attach Files, Read Message History and Manage Channels for private tickets. Manage Roles is needed only if using the optional welcome auto-role; place the bot above that nonprivileged role. Administrator is not required.
4. Set your own user ID in `OWNER_IDS`. Only those IDs can configure NEX CODEX or manage products/shop panels. Guild owners, administrators and staff do **not** gain those rights automatically.
5. Start/restart the bot. Slash commands synchronize automatically. Use `/help`; the bot owner can use `/setup` and `/diagnostics`. Prefix defaults to `!`, or `DEFAULT_PREFIX` until a guild override is saved.

If old commands remain visible, keep the same `COMMAND_GUILD_IDS` used previously and restart so that guild's registration is replaced. Global changes can take time to propagate. Owner-only `!sync` retries registration. If prefix commands do not respond, check Message Content Intent, the prefix and channel permissions. Clear startup messages explain absent/rejected tokens or disabled privileged intents. Actual live Discord setup still needs verification with your credentials.

## Command and permission map

Slash commands and equivalent prefix commands are registered. `/help` lists the current registry, with owner setup commands hidden from nonowners. Runtime checks enforce permissions even when a command is visible in Discord's menu.

| Access | Commands |
|---|---|
| Members | `/help`, `/shop`, `/product`, `/buy`, `/orders`, `/deliver`, `/ticket`, `/payment` |
| Staff or administrator | `/say`, `/broadcast`, `/giveaway`, `/reroll`, `/ticketmanage`, `/transcript`, `/orderstate` |
| Payment reviewers or administrator | `/paymentreview` — self-review is always prohibited |
| **Bot owners in OWNER_IDS only** | `/welcome`, `/leave`, `/addproduct`, `/productedit`, `/productpublish`, `/createshop`, `/configure`, `/prefix`, `/setup`, `/diagnostics`, `!sync` |

Configured bot owners can also perform staff/reviewer operations, subject to the self-payment prohibition. `staff_roles` grant staff access; `payment_roles` grant payment review only. Configuration/product ownership checks also run in services and the dashboard. The old text spelling `!productadd` is an alias for `!addproduct`; the slash command is `/addproduct`.

Moderation, generic utility/fun, XP, role selection, premium, referrals and AI commands are **not registered** in this focused release. Their historical models/services remain for data compatibility. Automated moderation/security/XP message processors are inactive. Existing saved reminders still finish through the recovery worker; no new reminder command is exposed. Hosting remains excluded.

## Owner setup

Start with `/setup`. `/configure key value` accepts validated JSON. With slash commands, enter a string value as `"text"`, role IDs as `[123456789012345678]`, and a channel ID as a number. Examples:

```text
/configure key:staff_roles value:[123456789012345678]
/configure key:payment_roles value:[234567890123456789]
/configure key:ticket_category value:345678901234567890
/configure key:log_channel value:456789012345678901
```

Use actual existing server IDs. Do not use @everyone as staff. Automatic/self-service roles cannot grant configured staff or reviewer roles.

### Welcome and leave

```text
/welcome channel:#welcome message:Welcome {user} to {server}!
/leave channel:#goodbye message:{name} left {server}.
/welcome
/leave
/welcome enabled:false
```

A call without a channel shows a preview. A channel/message saves the configuration; `enabled:false` disables that message. Templates support `{user}`, `{name}` and `{server}`. Join/leave messages are branded embeds with optional membership audit logging. An optional safe `auto_role` can be configured; missing Discord permissions are handled. Departures never cause automatic bans or claim restrictions.

### Say and broadcast

`/say message:... channel:#announcements` posts plain text. `/broadcast title:... message:... channel:#announcements` posts a branded embed. The channel defaults to the current one. These require staff/admin access; nonowner staff must also be able to view/send in the destination. Everyone/role/user mention notifications are suppressed. Sends are rate-limited and audited; failed sends are not reported as success.

### Emoji styling

Owners can customize the `emojis` JSON configuration. Accepted slots:

`welcome`, `leave`, `ticket`, `giveaway`, `say`, `broadcast`, `product`, `shop`, `help`, `settings`, `success`, `error`, `previous`, `next`.

```text
/configure key:emojis value:{"welcome":"👋","giveaway":"🎉","shop":"🛍️"}
```

Unicode emojis and Discord custom codes (`<:name:ID>` or `<a:name:ID>`) are validated. Custom emojis must exist and be available to the bot in Discord; inaccessible custom emojis cannot be verified offline. Defaults remain until replacements are supplied. Repost shop panels/giveaways to change their existing button appearance; new embeds and views use the current configuration. No specific user-supplied emoji list was received for this revision.

## Products and persistent shop

1. Owner uses `/addproduct` with category **template** or **source**, name, description, private delivery instructions or HTTPS URL, and a price such as `499.00`. New products are drafts.
2. Use `/productedit` to set terms, thumbnail, availability, delivery type/value or archive status. Except price, values accept JSON or plain text. `/productpublish` publishes/unpublishes a reviewed product.
3. Configure `shop_title`, `shop_description` and optional public HTTPS `shop_image` with `/configure`.
4. Owner runs `/createshop channel:#shop`. This posts a persistent browse button. Each click opens a fresh private storefront bound to that customer. The handler is restored after restart; products are fetched from the database each time.
5. `/shop` also supports category, search and page arguments. Dropdown product cards display price/terms and confirmation checkout buttons.

**Prices:** Discord `/addproduct` and `/productedit price` use currency units, e.g. `499.00`. Dashboard forms use integer minor units, e.g. `49900`. Database prices are integers, and orders snapshot their amount, currency, name, terms and delivery content.

Free claims immediately receive an entitlement. Duplicate ownership, pending orders, configurable lifetime total free-claim caps and cooldowns are enforced. Existing claims/orders remain accessible after restart. Entitlement records do not identify alternate accounts.

### Private delivery

Place product files under `PRODUCT_ROOT`, default `private/products/`. Configure `delivery_kind=file` and a relative `delivery_value`, such as `community-template.zip`. Supported extensions: `.zip`, `.json`, `.txt`, `.pdf`, `.tar`, `.gz`. Publishing and downloads recheck existence, traversal/symlink containment and entitlement. Private files are never web static assets or included in release ZIPs.

Other kinds: `link` (public HTTPS URL disclosed only after authorization) or `instructions` (private text). Recipients can copy disclosed links; use protected files for per-request access checks. `/deliver` sends privately by DM and records delivery only after successful send; authenticated dashboard downloads also check entitlement. Re-downloads are allowed. A crash between sending and database commit can lead to a duplicate send on retry.

## Private tickets and manual QR/UPI payments

**No payment gateway, automatic bank/screenshot verification, payment webhook or automatic refund.**

Owner configures `upi_id`, `qr_url` (public HTTPS image), `payee`, `currency`, `payment_instructions`, `staff_roles` and `payment_roles`. No real payment information ships with the project. Currency must match the product.

1. Customer confirms a paid product. A UUID order records the exact price and `pending_payment` status.
2. A private purchase ticket includes the customer, bot, staff and reviewer roles; @everyone is denied. Discord administrators retain platform-level access.
3. The ticket displays exact amount, order ID, QR, UPI ID, payee and instructions. Customer pays independently.
4. Customer uses `/payment` **inside their open purchase ticket** with a PNG/JPEG/WebP attachment up to 8 MB and optional reference. Discord attachment URLs may expire; reviewers should check promptly.
5. An authorized reviewer independently checks the receiving account, amount and reference, then explicitly approves/rejects with `/paymentreview` or the dashboard. A screenshot alone never marks paid. Rejection requires a reason. Nobody can review their own order.
6. Approval atomically records the reviewer, time, decision, paid state and one entitlement. Duplicate/concurrent approvals are prevented. `/deliver` or My orders provides authorized access.

`/ticket` opens support/appeal tickets or resumes a purchase by order ID. One active ticket per customer/category; reservations/channel topics help recover interrupted creation. Existing private overwrites are restored before reuse. `/ticketmanage` claims/unclaims/closes/reopens. Closed tickets are visible but read-only to customers. `/transcript` sends staff the latest 500 messages by DM.

If ticket creation fails after saving an order, resume that order with `/ticket order_id:...`; do not pay a replacement order. Missing/deleted channels need staff repair. `/orderstate` records cancellation of an unpaid order or a manual refund completed outside the bot. It never transfers money; recorded refunds revoke future delivery access.

## Giveaways

Staff create `/giveaway prize:... minutes:... winners:...`. Persistent entry buttons, unique entries, random outcomes, reroll history and overdue draws survive restarts. `/reroll` operates on ended giveaways. Notification retries are at least once; an abrupt crash can duplicate an announcement. One bot instance is required for this worker model.

## Dashboard and OAuth

Generate a random secret, then edit `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -m nex.db
uvicorn nex.dashboard.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Set `SESSION_SECRET` to the generated value, plus `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `PUBLIC_URL` and `DISCORD_REDIRECT_URI`. Register the exact redirect URI in Developer Portal → OAuth2, initially `http://localhost:8000/auth/callback`. Production HTTPS requires `COOKIE_SECURE=true` and matching public HTTPS URLs.

Public pages/catalogue and `/health` work without Discord credentials. Sign-in requests identify/guilds. OAuth state is expiring, cookie-bound and single-use. Sessions are opaque HttpOnly cookies backed by expiring database records. Sensitive forms require CSRF. Each protected guild request verifies live membership/roles/ownership with Discord and fails closed if verification fails. OAuth access tokens are not retained.

Product/settings pages and settings API require the configured **bot owner**, not administrator status. Staff can access the overview and authorized reviewer queue. Customers see their own orders/downloads. Premium/hosting management pages are removed. Advanced settings use a validated JSON editor; historical fields remain for compatibility and are not advertised as active features.

Read APIs: `/health`, `/api/products`, `/api/guild/{guild_id}/orders` (own orders), `/api/guild/{guild_id}/settings` (owner only). Public products omit private delivery content. POST form endpoints are authenticated/CSRF-protected, not public integration APIs. Requests are limited to 64 KiB; there is no web upload endpoint. Pagination and sensitive actions are bounded/rate-limited.

## Database and deployment

SQLite is the default, with WAL, foreign keys and busy timeout. PostgreSQL uses `DATABASE_URL=postgresql+psycopg://...`. `python -m nex.db` initializes schema v1 idempotently; it does **not** migrate changed schemas. This revision adds configuration JSON defaults without deleting historical data or changing table schemas.

Use **one bot process and one web worker**, shared database and private product directory. Sensitive writes serialize through SQLite BEGIN IMMEDIATE or PostgreSQL transaction advisory locking. Process-local rate limits and non-atomic Discord/database sends are documented limits. Back up database/private files together using SQLite backup API or stopped services, or PostgreSQL pg_dump. Keep backups and secrets out of public assets.

Deployment examples are in `deploy/`; replace their paths/user, use persistent storage, private environment files, TLS reverse proxy, disabled OAuth query logging and a 64 KiB body limit. Hosted TLS/DNS/systemd/panel configuration needs operator verification.

Stored records include Discord IDs, settings, membership events, orders, receipt URLs/references, entitlements, tickets, audit logs and giveaways. Legacy feature/history tables are retained. Expired sessions/states are purged by the bot worker. Automated retention/export/deletion and durable outbound queues are unfinished; operators need their own retention/backup process. Staff should keep ticket transcripts and log channels private.

## Validation and project state

```bash
python -m pytest -q
python -m compileall -q nex tests scripts main.py
python -m pip check
```

Tests use isolated SQLite databases, synthetic fixtures and Discord/OAuth mocks. They exercise owner-vs-admin/staff restrictions, actual command registry, command checks, welcome/leave rendering, announcements, persistent panels, emoji validation, payment/delivery integrity, tickets, dashboard authorization and packaging safety. Legacy model/service invariants remain covered without exposing their old commands.

An optional PostgreSQL smoke creates synthetic records in a dedicated database named `nex_test`:

```bash
NEX_POSTGRES_TEST_URL='postgresql+psycopg://TEST_USER:TEST_PASSWORD@127.0.0.1:5432/nex_test' PYTHONPATH=. python scripts/smoke_postgres.py
```

Read **PROJECT_STATE.md** for actual validation results, current limitations and external checks. Local tests do not establish live Discord/OAuth/Wispbyte operation. The release ZIP is rebuilt with `python scripts/package.py /path/to/NEX_CODEX_FINAL.zip`; it synthesizes `.env` from the blank example and excludes private/runtime data.
