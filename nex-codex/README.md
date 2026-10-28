# NEX CODEX

**Your community. Connected.** A modular Discord bot and companion FastAPI dashboard, with server management and a marketplace for server templates, bot source code, and manually provisioned hosting.

This is a runnable v1 foundation with implemented end-to-end services, not a hosted service. See [PROJECT_STATE.md](PROJECT_STATE.md) for the precise coverage, verified results, and remaining work. The existing portfolio website in the parent repository is preserved.

## Quick start

Requires Python **3.11+** (verified locally with 3.14.4). Run all commands from this directory.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put that generated value in `SESSION_SECRET` in `.env`. Do not commit `.env`. `requirements.lock` records the exact versions tested on Linux/Python 3.14; use `pip install -r requirements.lock` to reproduce that environment. On other Python versions/platforms install `requirements.txt` and run the tests before deployment.

```bash
python -m nex.db
uvicorn nex.dashboard.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Open **http://localhost:8000**. The homepage, catalogue, setup guide and `/health` work without Discord credentials. The catalogue starts empty. Authentication and guild management require the configuration below. The health response honestly reports the bot offline until its heartbeat is current.

In a second terminal, activate the same virtual environment, then:

```bash
python -m nex.bot
```

The bot exits with a clear message if `DISCORD_TOKEN` is missing. Ctrl+C gracefully closes the Discord client. Run **one bot process** and **one dashboard worker** for v1. Both use the same database and private product directory.

## Discord Developer Portal setup

1. Create an application at <https://discord.com/developers/applications> and add its bot.
2. Copy the bot token into `DISCORD_TOKEN`. Set `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET` from the application/OAuth settings.
3. Enable **Server Members Intent** and **Message Content Intent**. Message content powers prefix commands and automod; member intent powers join/leave, role and membership features. Discord may require approval for privileged intents at scale.
4. Configure an OAuth redirect URI that exactly matches `DISCORD_REDIRECT_URI`, initially `http://localhost:8000/auth/callback`. Set `PUBLIC_URL=http://localhost:8000` locally. The web authorization flow requests **identify** and **guilds**; it does not store OAuth access tokens after sign-in.
5. Invite the bot with **bot** and **applications.commands** scopes. Grant only the permissions needed for enabled features: View Channels, Send Messages, Embed Links, Attach Files, Read Message History, Manage Channels (tickets), Manage Roles (safe role tools), Manage Messages (purge/automod), Kick Members, Ban Members, Moderate Members, View Audit Log (security alerts), and Send Polls. You need not grant Administrator.
6. Place the bot role above roles and members it must manage. Discord administrators and guild owners retain their platform-level access to ticket channels.
7. Put your own Discord user ID in `OWNER_IDS`, JSON syntax: `[123456789012345678]`. Run `!sync` as a configured bot owner to publish global slash commands. Sync is explicit; it is not repeated at every restart. Propagation can take time.
8. Use `/help` to browse the **actual registered commands**. Text commands use `!` initially; `/prefix` changes it per guild. Complex argument workflows are easiest through slash commands.

The sign-in session is an opaque random HttpOnly cookie backed by an expiring server-side record. OAuth state is bound to a cookie, expires in ten minutes and is single-use. Sensitive forms require CSRF tokens. Protected guild requests fetch current membership, roles and ownership from Discord and fail closed if verification fails.

## Server setup

Open **My servers → Manage → Server settings**, or use `/configure key value`. Values in `/configure` must be JSON (quote strings; IDs are numbers; roles are arrays).

Suggested order:

1. `staff_roles`, `payment_roles`, `ticket_category`, `log_channel`.
2. `welcome_channel`, `leave_channel`, `welcome_message`, `leave_message`, optional `auto_role`. Templates support `{user}`, `{name}`, `{server}`; arbitrary formatting is not executed.
3. `self_roles` for `/roles`, and optional `leveling_enabled`, `xp_cooldown`, `level_channel`, `level_rewards` (for example `{"5": 123456789012345678}`). Only nonprivileged, unmanaged roles below the bot can be assigned.
4. Enable `automod_enabled` after reviewing thresholds/exemptions. Default action is **log**. Optional **delete** never automatically bans or times out. Rules cover bursts, repeated text, mention spam, invites, capitals, and explicitly configured blocked domains. Caps and spam signals are not proof of malicious intent.
5. Enable `security_enabled` and configure `security_threshold`, `security_window`, `security_exempt_users`. Supported audit actions: channel/role deletion, bans, kicks and webhook creation. Detection requires the necessary Discord events and View Audit Log permission. Responses currently persist incidents and alert staff. No automatic restoration, quarantine or permission stripping is implemented.

The dashboard JSON configuration editor exposes all fields with server-side validation. Full field defaults and bounds are in `nex/schemas.py`. Advanced settings do not have individual visual toggle pages yet.

## Marketplace and manual QR/UPI payments

**No payment gateway, payment webhook, automatic bank verification, or automatic refund is implemented.**

### Staff configuration

Set actual values for `upi_id`, `qr_url` (public HTTPS image URL), `payee`, `payment_instructions`, `currency` and `payment_roles`. No real payment details ship with this project. The payment currency must match the product currency. UPI is ordinarily used with INR; configure currency consistently with what your receiving account actually supports.

Staff create/edit/publish/unpublish/archive products in **Products**. Monetary values are integers in minor units: `49900` means `499.00`. Categories are `template`, `source`, `hosting`. Include terms before publication. Hosting requires `delivery_kind=hosting`; its duration and capacity are snapshotted into the order.

### Purchase flow

1. Customer uses `/shop`, `/product` and `/buy` in the relevant guild.
2. `/buy` asks for confirmation of product, amount and terms. The service checks those terms again inside the order transaction. The order gets a UUID, immutable price/currency/delivery snapshots and `pending_payment` status.
3. A private purchase channel is created for the customer, bot, staff roles and reviewer roles. The channel displays order ID, exact amount, QR and UPI instructions.
4. Customer pays independently, then uses `/payment` **inside that open ticket**, attaching a PNG/JPEG/WebP screenshot up to 8 MB and optional reference. The bot stores the Discord attachment URL; it does not OCR or automatically trust it. Attachment URLs can expire; staff should review promptly and consult the original ticket if needed.
5. Reviewers independently verify the receiving account, amount and reference. `/paymentreview` or the dashboard payment queue records an explicit decision, reviewer, timestamp and reason. Rejection requires a reason and allows resubmission. **Reviewers cannot approve/reject their own order**, including administrators and owners. Configured ordinary staff roles do not implicitly grant payment-review access.
6. Approval atomically records `paid`, entitlement and any hosting handoff. Concurrent/duplicate approvals produce one entitlement.
7. Customer uses `/deliver` (private DM) or **My orders → Access product**. A failed Discord send does not mark delivery successful. Hosting becomes delivered only when staff record an actual running provisioning result.

Order states implemented: `pending_payment`, `payment_submitted`, `paid`, `rejected`, `delivered`, `cancelled`, `manually_refunded`. The service also accepts `verification_required` for review compatibility, but there is no command that places an order into that intermediate state. `/orderstate` records unpaid cancellation or an already-completed external manual refund. It never transfers money. Refund recording revokes download entitlement but cannot recall an already downloaded file or automatically stop externally hosted resources.

If a ticket fails after order creation, the order remains recorded. Retry with `/ticket order_id:<ID>`; do not pay a new order. Ticket reservations and channel topics allow recovery after a crash. If a channel was deleted or a ticket was closed, staff must resolve it. A customer may have one active ticket per category; close an earlier purchase ticket before opening a second one.

### Free claims and reviews

Free products use `/buy` too and immediately receive an entitlement. Duplicate ownership is blocked. Guild and product free-claim limits are **lifetime total free orders per user in that guild**, with the stricter configured cap/cooldown applied. They are not daily resetting quotas. Free claims, entitlement and delivery times persist. Staff may restrict/restore claims with `/freebierestrict`, inspect `/freebiehistory`, and review an `/ticket category:appeal` request. Membership departures are logged with entitlement counts; leaving alone triggers no restriction or ban. No alternate-account identification is claimed.

`/review` requires an entitlement and supports a 1–5 rating and text. One review per customer/product. `reviews_allow_free` controls free-claim eligibility; `/reviewmoderate` hides/restores a review with an audit reason. Public product pages show visible ratings and reviews.

### Private product files

Place `.zip`, `.json`, `.txt`, `.pdf`, `.tar` or `.gz` files beneath `PRODUCT_ROOT` (default `private/products`). Use a **relative filename**, for example `community-template.zip`, in the product's delivery value. Publishing checks that the file exists and stays inside the root, including symlinks. Runtime downloads revalidate the path and entitlement. Private files are never mounted as web static files.

- `file`: protected dashboard attachment or Discord DM. Keep file sizes within your guild/Discord upload limits; larger files can be downloaded through the dashboard.
- `link`: HTTPS URL disclosed only after entitlement verification. This protects disclosure, not the remote file itself: recipients can copy the URL. Configure expiring provider links yourself or use private files when each download must be authorized.
- `instructions`: private textual delivery instructions.
- `hosting`: verified order enters a manual provisioning queue.

A successful server response means the server transmitted the file or instructions; it cannot prove the recipient saved them. Re-downloads are intentionally allowed while entitlement is active. The initial delivery transition and timestamp are idempotent. The bot and database do not form a distributed transaction; a crash after sending but before committing can result in a retry sending the same product again.

## Feature command map

Run `/help` for the live list. Permission failures explain the action and do not expose internal exceptions.

| Area | Commands / interface |
|---|---|
| Moderation | `/ban`, `/unban`, `/kick`, `/timeout`, `/untimeout`, `/warn`, `/history`, `/purge` |
| Server tools | `/ping`, `/about`, `/serverinfo`, `/userinfo`, `/avatar`, `/roleinfo`, `/channelinfo`, `/prefix`, `/configure` |
| Roles & community | `/role`, `/roles`, `/poll`, `/leaderboard`, `/roll`, `/remind` |
| Marketplace | `/shop`, `/product`, `/buy`, `/orders`, `/deliver`; dashboard product CRUD |
| Tickets | `/ticket`, `/ticketmanage` (claim/unclaim/close/reopen), `/transcript` (last 500 messages to staff DM) |
| Payments | `/payment`, `/paymentreview`, `/orderstate`; dashboard review queue |
| Hosting | `/hosting`; dashboard manual provisioning queue |
| Premium | `/premium` grant/revoke/extend/inspect; dashboard entitlement management |
| Reviews & referrals | `/review`, `/reviewmoderate`, `/referral`, `/rewards` |
| Giveaways | `/giveaway`, persistent entry button, `/reroll` |
| Freebie review | `/freebierestrict`, `/freebiehistory`, appeal tickets |
| Optional AI | `/ask`; owner config and guild opt-in required |
| Owner | `!sync` |

Ban, kick, purge, purchases and paid approvals require confirmation. Moderation enforces bot and moderator permissions plus role hierarchy. Warnings/history persist with actor, time and reason. Message edit/delete logging is limited to messages Discord delivers to the bot/cache; it cannot recover unavailable historical message content.

Giveaway entries and random results persist; the worker draws overdue giveaways after restart. It retries unannounced results. Reminders also recover after restart. Delivery/announcement retries are at least once; an abrupt crash between Discord success and database commit may duplicate a notification. Reminders with closed DMs stay pending and retry; users should allow DMs. One bot instance avoids competing workers.

## Hosting and premium

`HostingProvider` defines future `provision`/`stop` adapters. `ManualHosting` explicitly reports that staff action is required; it does not invent resource IDs. The queue enforces transitions: queued → provisioning → running/failed; running ↔ stopped; cancellation/expiry where appropriate. Recording running requires staff notes, sets expiration from purchased duration, and records delivery. Expiration records status only: staff must stop the real service separately. Renewal billing and provider automation are unfinished.

Premium supports named grants, temporary/lifetime entitlement, extension, revocation and server-side `Core.has_premium`. No paid feature is advertised or gated in v1; a premium plan catalogue, pricing and additional premium-only features are unfinished. Grants are unique per guild/customer.

Optional referral points are enabled with `rewards_enabled` and `referral_points`. A new customer must already own a product and select a current non-bot referrer with `/referral`. Self-referral and repeated redemption are blocked; rewards have unique ledger event keys. This does not prove an invitation happened or reliably detect alternate accounts. General earning rules, redemption and configurable referral-code issuance are not implemented.

## Optional AI

Set `AI_API_KEY`, `AI_MODEL`, and an HTTPS `AI_BASE_URL` for a provider implementing `/chat/completions`; enable `ai_enabled` per guild. `/ask` sends the supplied prompt to that provider, limits prompt/output length and applies per-user cooldowns. Provider errors and credentials are not returned to users. This adapter has not been verified against a live provider. No key or model is assumed to exist. Prompts should not contain private ticket contents or secrets.

## API

JSON endpoints:

- `GET /health`: database connectivity and recent bot heartbeat; no secrets or user records.
- `GET /api/products?category=template&q=...&page=1`: published product metadata, **without delivery secrets**.
- `GET /api/guild/{guild_id}/orders?page=1`: authenticated customer's own orders.
- `GET /api/guild/{guild_id}/settings`: authenticated administrator configuration.

The dashboard's POST form endpoints use the same service layer and require session CSRF tokens; they are not unauthenticated integration APIs. API errors currently use the branded HTML error handler. CORS is not enabled. Request bodies are capped at 64 KiB; no web file uploads are accepted. Discord receipt attachment validation is separate.

## Database, migrations and reliability

SQLite is the local default; WAL, foreign keys and a busy timeout are enabled. PostgreSQL uses SQLAlchemy's psycopg driver:

```dotenv
DATABASE_URL=postgresql+psycopg://nex:YOUR_PASSWORD@127.0.0.1:5432/nex
```

Initialize with `python -m nex.db`. Schema version 1 is recorded. Initialization is idempotent but **does not migrate an existing changed schema**. Future schema changes require a versioned migration and backup; do not treat `create_all` as an upgrade engine. No migration from the unrelated portfolio site is needed.

Sensitive mutations use a transaction, uniqueness constraints and serialized writes (SQLite `BEGIN IMMEDIATE`; PostgreSQL transaction-scoped advisory lock). This is deliberately conservative and suitable for a single bot/web deployment, not a high-throughput multi-instance platform. Database timestamps are naive UTC consistently; all IDs are Discord snowflakes or UUID strings; prices never use floating-point arithmetic.

Back up the database and private product directory together. For SQLite, stop both processes or use SQLite's backup API instead of copying a live WAL database blindly. For PostgreSQL, use `pg_dump` with an appropriate private credentials file. Test restoration. Keep raw backup files outside the public/static directory.

## Tests

```bash
pytest -q
python -m compileall -q nex tests
python -m pip check
```

Tests use isolated SQLite databases and synthetic data. They verify database persistence, permissions and hierarchy, invalid products/URLs, order price snapshots, approval authorization, concurrent duplicate approval and free claims, payment rejection/resubmission, delivery access, refund revocation, ticket overwrites, premium expiration/lifetime, referrals/reward uniqueness, reviews, cooldowns, giveaway recovery, XP cooldowns, OAuth state/sessions/CSRF, dashboard access, API redaction and offline slash-command serialization.

These tests **do not connect to live Discord**. Real OAuth consent, gateway intents, Discord moderation/tickets/file sends, and hosted AI/hosting provider behavior require separate staging verification with credentials and a test server. The available CodeRabbit Emulate v0.0.1 catalog was inspected; it does not include Discord or this AI adapter's chat-completions API.

A disposable PostgreSQL 17 smoke was also executed locally for schema creation, configuration, paid order creation, four concurrent approvals (one success), entitlement and delivery. To repeat against your **dedicated test database named `nex_test`**:

```bash
export NEX_POSTGRES_TEST_URL='postgresql+psycopg://TEST_USER:TEST_PASSWORD@127.0.0.1:5432/nex_test'
PYTHONPATH=. python scripts/smoke_postgres.py
```

This script creates synthetic records. It must not point at customer data. The full pytest suite has only been run on SQLite.

## Deployment

1. Use a dedicated OS account and persistent absolute paths for the database and product directory. Install the reviewed dependency lock appropriate for your runtime.
2. Set real Discord credentials, a random `SESSION_SECRET`, `COOKIE_SECURE=true`, `PUBLIC_URL=https://your-domain`, and the matching HTTPS redirect URI. Keep `.env` readable only by the service account. The app rejects HTTPS configuration without secure cookies.
3. Initialize the database, then run the bot and one Uvicorn worker as separate supervised services. Example systemd units are in `deploy/`; replace paths/user and keep environment files private.
4. Terminate HTTPS at a reverse proxy (example `deploy/nginx.conf`), forwarding only the app port. Set a 64 KiB body limit and disable OAuth callback query logging. The documented Uvicorn command disables access logs so authorization codes aren't recorded there.
5. Verify `/health`, sign-in, membership authorization, a free claim and a synthetic paid transaction in a private staging guild before opening to customers. Do not test destructive moderation in a production server.
6. Rate limits are process-local. Use one web worker; add a shared limiter/queue and strengthen operational monitoring before scaling. Review Discord API rate limits for your own usage and keep dependencies updated with regression tests.

### Privacy and retention

Stored data: Discord IDs, server membership events, settings, moderation reasons, order/entitlement/payment-review records, receipt URLs/references, reviews, points/referrals, XP, giveaways, reminders and audit records. Sessions expire after 8 hours; the bot worker purges expired sessions/states. OAuth tokens are not retained. Product links/files can contain confidential material; limit staff roles and filesystem access.

Keep log channels private. The bot can log message contents only when that feature's logging channel is configured. Do not post private payment information in public channels. Staff transcript exports go to DMs; staff must handle them responsibly. Automated data retention, customer export/deletion and transcript archival are unfinished; operators must establish a retention policy and process deletion requests with a reviewed, backed-up database maintenance procedure respecting foreign keys and required transaction records.

## Project layout

```
nex/
  bot.py, config.py, db.py, models.py, schemas.py, security.py
  cogs/         Discord commands, event listeners and periodic worker
  services/     Configuration, marketplace, tickets, community, provider adapters
  dashboard/    OAuth/session handling, FastAPI, Jinja templates and static assets
  utils/        Embeds, confirmation and role safety
private/products/  Private operator-supplied assets (ignored by Git)
tests/             Unit and local integration tests
scripts/           Explicit PostgreSQL smoke test
deploy/            Deployment examples
```

For current limits and the remaining roadmap, read **PROJECT_STATE.md**. Never deploy with test credentials or assume the successful local test suite proves a live Discord installation is configured correctly.
