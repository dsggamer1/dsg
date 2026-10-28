# NEX CODEX — Owner ka complete setup guide

Slash command type karo, phir Discord ke named fields fill karo. Neeche `PRODUCT_ID`, `ORDER_ID`, `YOUR_UPI_ID`, etc. placeholders hain—apni value daalo. `<...>` ya placeholder text literally paste mat karo.

## 1. Owner bano

`.env` mein `OWNER_IDS=[APNI_NUMERIC_DISCORD_USER_ID]` set karo aur bot restart karo. Yeh **user ID** hai, role/server ID nahi. Bot owner product aur shop manage kar sakta hai. Server Administrator payment/server configuration kar sakta hai. Staff role se product ownership nahi milti.

Bot ko View Channels, Send Messages, Embed Links, Attach Files, Read Message History aur ticket creation ke liye Manage Channels chahiye. Developer Portal mein Server Members aur Message Content intents enable karo.

## 2. Payment aur ticket setup — ek command

Discord mein pehle `Support`, `Payment Reviewers` roles aur `Tickets` category banao. Trusted people ko roles do. Phir:

```text
/paymentsetup
  upi_id: YOUR_UPI_ID
  payee: YOUR_PAYEE_NAME
  qr_url: YOUR_HTTPS_QR_IMAGE_URL
  staff_role: @Support
  payment_role: @Payment Reviewers
  ticket_category: Tickets
  currency: INR
```

- UPI ID aur QR apne payment app se lo. Bot koi payment details invent nahi karta.
- QR URL HTTPS image URL honi chahiye; preview mein apna QR check karo.
- Command selected staff/reviewer roles ko existing lists mein add karta hai. @everyone allowed nahi.
- Existing staff role remove karna ho: `/configure key: staff_roles value: [ROLE_ID]` se complete desired list save karo. Payment reviewers ke liye key `payment_roles`.
- Instructions change: `/configure key: payment_instructions value: "Pay exact amount; receipt yahin submit karein."`
- Currency new products par apply hoti hai; old prices/orders automatically convert nahi hote.

## 3. Product add karo — owner only

### Categories

| Category option | Kya sell karna hai |
|---|---|
| `template` | Discord server template / template JSON |
| `bot` | Discord bot source code / source ZIP |

Hosting category nahi hai.

### Price

- `499` = INR 499 (jab currency INR hai).
- `499.50` = INR 499.50.
- `0` = free product.
- Price mein ₹, comma ya `free` mat likho.

### Example: paid Discord server template

```text
/addproduct
  name: Gaming Server Template
  category: template
  price: 499
  delivery: YOUR_HTTPS_DOWNLOAD_URL
  description: Gaming server layout with organized channels and roles.
```

Bot **draft** banayega aur Product ID dega. Draft abhi shop mein visible nahi hai. Delivery `https://` se start hoti hai toh link; otherwise instructions ke taur par save hoti hai. Public description/terms mein private download URL mat daalo.

```text
/productedit product_id: PRODUCT_ID field: terms value: Personal use only. Reselling is not allowed.
/productpublish product_id: PRODUCT_ID published: true
/createshop channel: #shop
```

Ab `/shop` se product check karo. `createshop` persistent Browse button post karta hai, jo restart ke baad bhi work karta hai. Product add karne par har baar naya panel banane ki zarurat nahi.

### Example: bot source code

```text
/addproduct name: Ticket Bot Source category: bot price: 799 delivery: YOUR_HTTPS_DOWNLOAD_URL description: Python ticket bot source with setup instructions.
```

Product suggestions se select karke terms set aur publish karo. Product apne aap publish nahi hota.

### File se delivery

Wispbyte mein file `private/products/ticket-bot.zip` par upload karo. Phir:

```text
/productedit product_id: PRODUCT_ID field: delivery_value value: ticket-bot.zip
/productedit product_id: PRODUCT_ID field: delivery_kind value: file
```

Agar current delivery kind `link` hai, pehle `delivery_kind: instructions` set karo, phir filename, phir `file`. Draft par ye setup karke last mein publish karo. Relative filename use karo; `/home/...` absolute path nahi. Allowed types: .zip, .json, .txt, .pdf, .tar, .gz. Bot paid delivery se pehle entitlement check karta hai. Download link recipient copy kar sakta hai; link revocation external host ka feature hai.

### Product editing

```text
/productedit product_id: PRODUCT_ID field: price value: 599
/productedit product_id: PRODUCT_ID field: description value: New product details.
/productedit product_id: PRODUCT_ID field: thumbnail value: YOUR_HTTPS_IMAGE_URL
/productpublish product_id: PRODUCT_ID published: false
```

Unpublish sales pause karta hai. Existing orders apne original price, terms aur delivery snapshot rakhte hain. Fields: name, description, category, price, currency, thumbnail, terms, published, archived, available, delivery_kind, delivery_value, claim_limit, cooldown_seconds. Booleans `true` / `false`; numbers without quotes. `/productedit` plain text bhi accept karta hai; `/configure` values valid JSON honi chahiye.

Prefix example (default `!`):

```text
!addproduct "Gaming Template" template 499 "YOUR_HTTPS_DOWNLOAD_URL" "Gaming layout"
!productedit PRODUCT_ID terms Personal use only; no resale.
!productpublish PRODUCT_ID true
```

Multi-word positional values ko quotes mein rakho. Slash fields use karna easiest hai.

### Short ID aur product suggestions

Naye product ko short 8-character ID milti hai. `/productpublish`, `/productedit`, `/product`, `/buy` aur `/productid` ke product_id field mein type karo: product names + short IDs suggestions mein dikhenge (25 matches; name type karke filter karo). Owner ko drafts bhi dikhenge; members ko published products. ID badalne ke liye:

```text
/productid product_id: OLD_ID new_id: gaming-bot
```

3–16 lowercase letters/numbers, hyphen ya underscore. Old orders safe rehte hain. Internal database/order IDs change nahi hote. Categories sirf **template / bot** hain; old source category update mein bot ho jaati hai.

## 4. Customer purchase aur payment review

1. Customer `/shop` khole → product select → Confirm purchase.
2. Private purchase ticket mein **Order ID**, exact amount, UPI, QR aur instructions dikhenge.
3. Customer independently payment kare.
4. Usi ticket mein `/payment order_id: ORDER_ID screenshot: ATTACH_IMAGE reference: OPTIONAL_REFERENCE`.
5. Authorized reviewer apne payment/bank app mein actual transaction check kare.
6. Approve: `/paymentreview order_id: ORDER_ID approve: true` → confirmation. Reject: `approve: false reason: REASON`.
7. Customer `/deliver order_id: ORDER_ID` kare. Product DM mein jayega; DMs open hone chahiye.

Screenshot se automatic approval nahi hota. Customer apna payment approve nahi kar sakta, chahe owner ho. Apne account se test purchase karoge toh doosra authorized reviewer chahiye. Duplicate approvals aur unauthorized delivery blocked hain.

Free products: confirm claim → entitlement save → `/deliver`. Payment step skip hota hai. `/orders` se Order ID dobara mil sakta hai. Product ID aur Order ID alag hain.

## 5. Community setup

```text
/welcome channel: #welcome message: Welcome {user} to {server}!
/leave channel: #logs message: {name} left {server}.
/broadcast title: New collection message: Check our latest templates! channel: #news
/say message: Hello everyone! channel: #general
/giveaway prize: Free template minutes: 60 winners: 1
```

Welcome/leave placeholders: `{user}`, `{name}`, `{server}`. Disable: `/welcome enabled: false` or `/leave enabled: false`. Welcome/leave setup owner/admin; say/broadcast/giveaway staff/admin/owner. `/say` intentionally plain message hai; `/broadcast` branded announcement card hai. Giveaway prize delivery staff handles manually.

## 6. Direct setup + moderation

```text
/shopsetup channel: #shop title: NEX Shop description: Templates and bots.
/channelsetup kind: logs channel: #logs
/welcomesetup channel: #welcome message: Welcome {user}!
/leavesetup channel: #leave restrict_rejoin: false message: Bye {name}.
/ticketsetup category: Tickets staff_role: @Support
/giveawaysetup channel: #giveaways
```

Shop setup/product changes OWNER_IDS only; other setup owner/admin. `/paymentsetup` remains QR/UPI setup. Confirm purchase par private ticket automatic banega; manually /ticket chalana required nahi (sirf recovery ke liye).

```text
/kick member: @user reason: REASON
/ban member: @user reason: REASON
/warn member: @user reason: REASON
/timeout member: @user minutes: 30 reason: REASON
/timeout member: @user minutes: 0 reason: Remove timeout
/giverole member: @user role: @Member
/takerole member: @user role: @Member
/warnings member: @user
```

Actual Discord permissions required (Kick/Ban/Moderate Members/Manage Roles). Bot aur moderator role target se upar honi chahiye. Kick/ban confirmation maangte hain; warnings persist. Privileged/staff/payment/managed roles safe role command se assign/remove nahi hote.

### Optional leave/rejoin rule

`/leavesetup restrict_rejoin: true` enable karo toh jo member uske baad leave kare, uski ID save hogi aur wapis join par kick milega. Default false. Owners/admins/configured staff/reviewers/bots exempt. Bot ko Kick Members aur target se upar role chahiye. Leave event mein moderation kick bhi include ho sakta hai; yeh abuse detection nahi hai. Existing saved IDs re-enable karne par apply honge.

`/rejoinallow user_id: NUMERIC_ID` kisi user ka block clear karega. `/leavesetup restrict_rejoin: false` enforcement band karega. No automatic ban. Serious restrictions review karna staff ka kaam hai.

## 7. Har registered command

| Command | Fields / purpose | Access |
|---|---|---|
| `/help` | Animated categories, command usage, Browse shop; management users get Setup guide | Everyone |
| `/shop` | Optional category, search, page | Members |
| `/product` | product_id: inspect details | Members |
| `/buy` | product_id: confirm order/free claim | Members |
| `/orders` | Optional page: your order IDs/status | Members |
| `/deliver` | order_id: entitled private delivery | Customer |
| `/ticket` | category: support/appeal; order_id to resume a purchase | Members |
| `/payment` | order_id, screenshot, optional reference; inside purchase ticket | Customer |
| `/paymentreview` | order_id, approve, rejection reason | Reviewer/admin/owner; never own order |
| `/ticketmanage` | ticket_id, action: claim/unclaim/close/reopen | Staff/admin/owner |
| `/transcript` | Inside ticket; sends last 500 messages privately | Staff/admin/owner |
| `/orderstate` | order_id, state: cancelled/manually_refunded, reason | Staff/admin/owner |
| `/say` | message, optional channel | Staff/admin/owner |
| `/broadcast` | title, message, optional channel | Staff/admin/owner |
| `/giveaway` | prize, minutes, optional winners | Staff/admin/owner |
| `/reroll` | giveaway_id: ended giveaway | Staff/admin/owner |
| `/welcome` | channel, enabled, message | Owner/admin |
| `/leave` | channel, enabled, message | Owner/admin |
| `/prefix` | prefix: new text-command prefix | Owner/admin |
| `/configure` | key, value: validated JSON setting | Owner/admin |
| `/setup` | Interactive guide: start/products/payments/community | Owner/admin |
| `/paymentsetup` | UPI/payee/QR, staff role, reviewer role, ticket category, currency | Owner/admin |
| `/diagnostics` | Command/prefix/channel-permission checklist | Owner/admin |
| `/installemojis` | Optional server emoji override; startup already auto-loads application emojis | Owner/admin |
| `/addproduct` | name, category, price, delivery, description | Configured bot owner |
| `/productedit` | product_id, field, value | Configured bot owner |
| `/productpublish` | product_id, published | Configured bot owner |
| `/createshop` | Optional channel: persistent shop panel | Configured bot owner |
| `/productid` | product_id, new_id: short public ID change | Configured bot owner |
| `/shopsetup` | channel, optional title/description/image | Configured bot owner |
| `/channelsetup` | kind, channel | Owner/admin; shop kind owner only |
| `/welcomesetup` | channel, message | Owner/admin |
| `/leavesetup` | channel, restrict_rejoin, message | Owner/admin |
| `/ticketsetup` | category, staff_role | Owner/admin |
| `/giveawaysetup` | channel | Owner/admin |
| `/rejoinallow` | user_id | Owner/admin |
| `/kick`, `/ban` | member, reason; confirmation | Discord Kick/Ban Members |
| `/warn`, `/warnings`, `/timeout` | member; minutes/reason as applicable | Discord Moderate Members |
| `/giverole`, `/takerole` | member, role | Discord Manage Roles |
| `!sync` | Hidden prefix-only registration retry (use your configured prefix) | Configured bot owner |

`orderstate` records a manual decision; it never transfers/refunds money. Ticket IDs appear in the ticket response/channel topic; Giveaway IDs appear in giveaway footers.

## 8. Theme, buttons aur mention reply

- Bot ko directly mention karo: branded reply with Explore commands / Browse shop buttons. Bots/webhooks, everyone-only mentions and normal mention-prefix commands don't cause duplicate greetings. Rate limits apply.
- Help ke real buttons Discord image ke **neeche** hain. Image/GIF pixels clickable nahi hote. Help has Previous/Home/Next plus Shop and, when allowed, Setup guide.
- Matching cyan/blue artwork covers shop/products, support, payment receipts, welcome/leave, announcements, giveaway and setup. QR/shop custom images take precedence. Keep **all** `nex/assets/` folders when hosting.
- Attach Files missing ho toh messages text/embed form mein work karte hain. Compact status/error embeds retain the same color/branding; `/say` stays plain text.

## Run

Fill `.env`, install `pip install -r requirements.txt`, run `python main.py`. Existing hosting update mein apna `.env`, database aur private products preserve karo. Tests use mocked Discord APIs; live Discord/Wispbyte behavior requires your account credentials and permissions.
