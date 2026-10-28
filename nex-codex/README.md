# NEX CODEX

A focused Python Discord bot for community essentials and a server-template / bot-source shop. Includes a cyan animated help menu, matching cards, automatic custom emojis, personal controls and persistent SQLite storage. PostgreSQL is supported.

## Run on Wispbyte

1. Upload the **contents of `NEX_CODEX/`**, keeping all `nex/assets/` folders.
2. Choose Python **3.11+**. Install:
   ```bash
   pip install -r requirements.txt
   ```
3. Edit the included `.env`:
   ```env
   DISCORD_TOKEN=
   OWNER_IDS=[123456789012345678]
   COMMAND_GUILD_IDS=[123456789012345678]
   ```
   Fill your bot token and replace the examples with your **Discord user ID** and **server ID**, respectively. Numeric ID lists use JSON. `COMMAND_GUILD_IDS=[]` uses global command registration only.
4. Start with **`python main.py`** (startup file `main.py`).
5. Run `/setup` for the guided setup. Read **[OWNER_GUIDE.md](OWNER_GUIDE.md)** for every command with Hinglish examples.

Keep your token private. The distributed `.env` has blank secrets. When upgrading, preserve your populated `.env`, `nex.db` (and its WAL/SHM files while running), and `private/products/`. Stop the bot before copying SQLite backups; do not overwrite existing data with a fresh empty database.

Wispbyte itself has not been accessed or tested. The Python 3.14 dependency snapshot is `requirements.lock`; `requirements.txt` supports Python 3.11+. No image library is needed at runtime.

## Discord setup

In Discord Developer Portal, create the bot, copy its token and enable **Server Members Intent** and **Message Content Intent**. Invite with `bot` + `applications.commands` scopes.

Grant View Channels, Send Messages, Embed Links, Attach Files, Read Message History and Manage Channels (private tickets). Manage Roles is only needed for optional welcome auto-role; place the bot above the selected nonprivileged role. Enable Kick Members, Ban Members, Moderate Members and Manage Roles only for the moderation actions you use. Bot Administrator is not required.

Slash commands sync at startup. Optional `COMMAND_GUILD_IDS` provides direct server registration. Keep the same list when updating to replace old guild commands. Global propagation can take time. Prefix defaults to `!`; owner-only `!sync` retries registration. `/diagnostics` checks local registration and channel permissions.

Discord controls installation permissions. OWNER_IDS and Administrator checks protect runtime setup. For private installation, configure Public Bot and server integration permissions in Discord; the bot does not override Discord's invitation rules.

## Included commands

| Access | Commands |
|---|---|
| Members | `/help`, `/shop`, `/product`, `/buy`, `/orders`, `/deliver`, `/ticket` |
| Staff / admin / owner | `/say`, `/broadcast`, `/giveaway`, `/reroll`, `/ticketmanage`, `/transcript`, `/orderstate` |
| Owner or server Administrator | `/setup`, `/welcome`, `/leave`, `/prefix`, `/configure`, `/diagnostics`, `/installemojis` |
| Discord moderation permissions | `/kick`, `/ban`, `/warn`, `/timeout`, `/warnings`, `/giverole`, `/takerole` |
| Owner or server Administrator | `/welcomesetup`, `/leavesetup`, `/ticketsetup`, `/giveawaysetup`, `/channelsetup`, `/rejoinallow` |
| Configured bot owners only | `/addproduct`, `/productedit`, `/productpublish`, `/createshop`, `/shopsetup`, `/productid`, `/orderfulfill`, hidden prefix `sync` |

41 slash commands plus prefix equivalents. Staff roles do not grant product ownership or server configuration rights. All sensitive operations enforce permissions independently of menu visibility.

## Owner shop setup

1. `/ticketsetup category: Tickets staff_role: @Support`: choose a private ticket category and trusted staff role. Currency defaults to INR; `/configure key: currency value: "USD"` changes new product defaults.
2. `/addproduct`: choose `template` or `bot`; price `499` means 499 currency units, `0` means free. Enter private delivery link/instructions.
3. Select the product by name in `/productedit` or `/productpublish` suggestions. Products get an 8-character public ID. `/productid` changes it to a 3–16 character name such as `gaming-bot`, preserving all orders.
4. `/createshop` posts a persistent browse button.

Customer: shop → confirm → private purchase ticket → staff assistance → owner `/orderfulfill order_id: ORDER_ID reason: Request completed` → customer `/deliver` to DMs. Priced orders stay locked as `awaiting_staff` until owner release; the bot does not track or verify transactions. Free claims save an entitlement immediately (`ready`). Product ID and Order ID are different.

**There is no payment system:** no QR/UPI setup, receipt uploads, review/approval commands or refunds. Prices are catalogue information. `/orderstate state: cancelled` cancels orders and revokes access. Orders preserve the listed price, terms and delivery snapshot accepted at checkout. `/orderfulfill` releases product access; it does not assert that a payment happened or send the product itself.

### Private product files

Put source/template files under `private/products/` (or `PRODUCT_ROOT`). Set product `delivery_kind=file` and `delivery_value` to a relative filename using `/productedit`. Supported suffixes: `.zip`, `.json`, `.txt`, `.pdf`, `.tar`, `.gz`. Traversal and symlink escapes are rejected. Private product files are deliberately excluded from the distribution ZIP; upload your own files separately. Delivery checks ownership/released access/entitlement and marks success only after sending. DMs must be open.

### Theme and controls

Keep `nex/assets/emojis/`, `help/` and `cards/`. Startup uploads/reuses the 49 bundled application emojis with the bot token (`AUTO_LOAD_EMOJIS=true`). Partial upload failures retain successful mappings and Unicode fallbacks; restart to resume. Optional `/installemojis` creates server overrides.

Help has five animated pages (900×820), real Previous/Home/Next buttons, Shop and management Setup shortcuts. Buttons are Discord components below images; image pixels are not clickable. Direct mentions show personal Help/Shop shortcuts with rate limits. Valid commands, bots and webhooks do not trigger duplicate greetings.

Welcome/leave, shop/products, tickets, giveaways, broadcast and setup use matching compact banners. Custom shop images take precedence. Missing assets/Attach Files fall back to usable embeds. `/say` sends plain text. `scripts/render_help.py` and `render_cards.py` are optional Pillow/DejaVu build tools; shipped artwork requires no rendering at startup.

## Direct setup and moderation

Use `/shopsetup channel: #shop` to set the shop channel/branding and post its persistent panel. `/welcomesetup`, `/leavesetup`, `/ticketsetup`, `/giveawaysetup` and `/channelsetup` expose specific configuration without JSON. Existing `/welcome` and `/leave` still preview/configure messages.

Kick/ban require confirmation, current Discord permissions and both member/bot role hierarchy. Warnings/cases persist. Timeout accepts minutes; `0` removes it. Give/take role requires Manage Roles and a safe nonprivileged role below the moderator/bot; staff, managed and dangerous roles are blocked.

### Optional leave/rejoin restriction

`/leavesetup restrict_rejoin: true` records departures and kicks recorded users when they join again. **Default disabled**; requires bot Kick Members permission and sufficient hierarchy. No ban is created on leave. `/rejoinallow user_id: ID` clears an individual restriction; `/leavesetup restrict_rejoin: false` disables enforcement. Bot owners, server owner, administrators, configured staffs and bots are exempt. Only departures observed while enabled are recorded. Discord member-remove events also include kicks; this is a configured access rule, not proof of abuse. Retained restrictions apply again if the feature is re-enabled. Failed kicks are logged as unavailable, never successful.

## Storage and upgrades

Startup initializes schema v3 with SQLAlchemy. Default: `DATABASE_URL=sqlite:///./nex.db`. Keep storage persistent. PostgreSQL: `postgresql+psycopg://USER:PASSWORD@HOST/DB`; never commit credentials.

The bot-only release removes dashboard/OAuth, unused providers/AI, automod, premium, XP, reviews/rewards/referrals and reminders. Existing unused database tables are left intact; no automatic destructive migration is performed. Known retired guild settings are ignored on read; new writes to retired settings are rejected. Existing orders, claims, tickets and giveaways retain their records. Legacy payment tables remain dormant in existing databases; fresh installs have no payments table or ORM/API for it. Old payment configuration is ignored and new writes are rejected. Historical hosting records remain readable only to handle old order cleanup; new hosting products are rejected.

Back up before upgrading. Schema v1→v2 automatically adds/backfills short product codes and renames stored `source` categories to `bot`, preserving internal product IDs/order links. Schema v2→v3 converts pending/rejected/submitted legacy orders to `awaiting_staff`; old entitled `paid` orders become `ready`; refunded orders become `cancelled`. No pending order gains an entitlement during migration. Existing delivered access stays available. Backups are required; it does not migrate arbitrary future column changes. Future schema versions need an explicit migration chain. Do not run old and new bot versions together.

## Development and checks

```bash
python -m venv .venv
# Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m nex.db
python -m pytest -q
python -m compileall -q nex main.py scripts tests
python scripts/package.py /tmp/NEX_CODEX_FINAL.zip
```

Tests use synthetic SQLite fixtures and mocked Discord APIs. They are not live Discord, hosting-panel integration tests. Optional PostgreSQL validation uses a dedicated disposable database named `nex_test`:

```bash
NEX_POSTGRES_TEST_URL='postgresql+psycopg://USER:PASSWORD@HOST/nex_test' PYTHONPATH=. python scripts/smoke_postgres.py
```

`deploy/nex-bot.service` is a Linux systemd example; adapt its user/paths and keep environment files private. Run one bot process per token/database. SIGTERM/systemd or Ctrl+C shuts down the process; network reconnects are handled by discord.py.

## Practical limits

- Rate limits and ticket locks are process-local; use one bot instance.
- Discord sends and database commits cannot be atomic. A crash after an external send can require staff reconciliation. Check `/orders` before retrying purchases.
- Transcript attachment URLs can expire. A copied download link cannot be revoked by the bot; use your file host's protections.
- Giveaways persist entries/results and retry announcements; prize fulfillment is manual staff work.
- Live Discord gateway/uploads, actual emoji creation and Wispbyte hosting need verification with your credentials.
