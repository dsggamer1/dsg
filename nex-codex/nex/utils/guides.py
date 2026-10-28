"""Actionable setup guidance: examples are documentation, never executed as commands."""
import discord
from .theme import themed_embed, emoji_for
from .cards import send_card, edit_card
from .storefront import PersonalView

GUIDES = {
    'start': ('Start here', [
        ('01 · Your access', 'Set `OWNER_IDS=[YOUR_DISCORD_USER_ID]` in .env and restart. Bot owners manage products and shop panels. Owners or server administrators configure the server.'),
        ('02 · Payment & tickets', 'Run `/paymentsetup` and fill in your UPI ID, payee name, HTTPS QR image URL, staff role, reviewer role and ticket category. Select roles/channels from Discord suggestions.'),
        ('03 · Add → publish → shop', 'Owner: run `/addproduct`, select its short product ID from suggestions, set terms with `/productedit`, then `/productpublish`. Finally `/createshop` posts a lasting Browse button.'),
        ('04 · Community', 'Run `/welcome`, `/leave`, `/broadcast` or `/giveaway`. Choose a guide page below for exact examples. Advanced settings remain available through `/configure`.'),
    ]),
    'products': ('Add products · owner only', [
        ('Category & price', '`template` = Discord server template. `bot` = bot source code. Price `499` means 499 currency units (INR by default); `499.50` is allowed; `0` makes it free. Do not enter ₹ or commas.'),
        ('Create a draft', 'Slash command fields:\n`/addproduct name: Gaming Server category: template price: 499 delivery: YOUR_HTTPS_DOWNLOAD_URL description: Gaming server layout`\nUse your own delivery URL or delivery instructions. The delivery value is only sent after an eligible claim or verified payment.'),
        ('Set terms & publish', '`/productedit product_id: PRODUCT_ID field: terms value: Personal use only; no resale.`\n`/productpublish product_id: PRODUCT_ID published: true`\nSelect product name/short ID from suggestions; /productid changes the short ID. Drafts do not appear in /shop.'),
        ('Edit / pause sales', '`/productedit product_id: PRODUCT_ID field: price value: 599`\n`/productpublish product_id: PRODUCT_ID published: false`\nUse `/createshop channel: #shop`, then `/shop` to check published products.'),
        ('Private files', 'Upload your .zip/.json file under `private/products/` on the host. Set `delivery_kind` to `file` and `delivery_value` to its relative filename with /productedit. Never use an absolute host path. Existing orders keep the delivery terms saved at checkout.'),
    ]),
    'payments': ('Payments & tickets · owner / admin', [
        ('One-time setup', '`/paymentsetup upi_id: YOUR_UPI_ID payee: YOUR_PAYEE_NAME qr_url: YOUR_HTTPS_QR_IMAGE staff_role: @Support payment_role: @Reviewers ticket_category: Tickets currency: INR`\nUse real details from your own payment app. The QR URL must show your QR image.'),
        ('Who can see tickets?', 'The customer, bot and configured staff/reviewer roles. Do not select @everyone. /paymentsetup adds the selected roles to existing role lists; it does not remove other configured staff.'),
        ('Customer flow', '`/shop` → choose product → Confirm purchase → private ticket → pay exact amount → `/payment order_id: ORDER_ID screenshot: ATTACH_IMAGE reference: OPTIONAL_REFERENCE`'),
        ('Review & delivery', 'An authorized reviewer independently checks the actual transaction, then `/paymentreview order_id: ORDER_ID approve: true`. To reject, use `approve: false reason: REASON`. Customers retrieve the product using `/deliver order_id: ORDER_ID` with DMs open.'),
        ('Important', 'No automatic verification or gateway. A screenshot does not prove payment. Customers cannot approve their own orders. Changing currency affects new products; existing prices/orders are not converted.'),
    ]),
    'community': ('Welcome, messages & giveaways', [
        ('Welcome / leave · owner or admin', '`/welcome channel: #welcome message: Welcome {user} to {server}!`\n`/leave channel: #logs message: {name} left {server}.`\nPlaceholders: `{user}`, `{name}`, `{server}`. Disable with `enabled: false`.'),
        ('Announcements · staff', '`/say message: Hello everyone! channel: #general`\n`/broadcast title: New collection message: Explore our latest templates. channel: #news`\nSay sends plain text; broadcast sends a branded card. Mentions are suppressed.'),
        ('Giveaways · staff', '`/giveaway prize: Free server template minutes: 60 winners: 1`\nMembers click Enter giveaway. Entries survive restarts. `/reroll giveaway_id: GIVEAWAY_ID` draws again after the giveaway ends.'),
        ('Support · members / staff', 'Members: `/ticket category: support` or `appeal`.\nStaff: `/ticketmanage ticket_id: TICKET_ID action: claim` (also unclaim, close, reopen). `/transcript` inside the ticket sends its transcript to your DMs.'),
    ]),
}


def guide_card(section, config=None):
    title, fields = GUIDES[section]
    item = themed_embed('settings', title, 'Fill the named fields in Discord’s slash-command form. UPPERCASE values are placeholders to replace.', config=config)
    for name, text in fields:
        item.add_field(name=name, value=text, inline=False)
    item.set_footer(text='NEX CODEX • Setup guide • /help lists all registered commands')
    return item


class GuideSelect(discord.ui.Select):
    def __init__(self, config=None):
        self.config = config
        super().__init__(placeholder='Choose a setup guide', options=[discord.SelectOption(label=title, value=key, default=key=='start') for key,(title,_) in GUIDES.items()])

    async def callback(self, interaction):
        section=self.values[0]
        for option in self.options:
            option.default=option.value==section
        await edit_card(interaction, guide_card(section,self.config), key='settings',view=self.view)


class GuideView(PersonalView):
    def __init__(self,user_id,config=None):
        super().__init__(user_id)
        self.add_item(GuideSelect(config))

    async def interaction_check(self,interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('Run /setup to open your own guide.',ephemeral=True)
            return False
        return True


class IntroView(PersonalView):
    """Personal shortcuts opened from a direct mention. No configuration mutations."""
    def __init__(self,user_id,config=None):
        super().__init__(user_id)
        self.help_button.emoji=emoji_for('help',config)
        self.shop_button.emoji=emoji_for('shop',config)

    async def interaction_check(self,interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('Mention the bot or run /help to open your own menu.',ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Explore commands',style=discord.ButtonStyle.primary)
    async def help_button(self,interaction,button):
        await interaction.response.defer(ephemeral=True)
        await interaction.client.get_cog('Utility').send_help(interaction.user,interaction.guild,interaction.channel,interaction.followup.send)

    @discord.ui.button(label='Browse the shop',style=discord.ButtonStyle.secondary)
    async def shop_button(self,interaction,button):
        from .storefront import ShopView
        await interaction.response.defer(ephemeral=True)
        interaction.client.limiter.check(('mention_shop',interaction.guild_id,interaction.user.id),5,60)
        view=ShopView(interaction.user.id,interaction.client,interaction.guild_id)
        await send_card(interaction.followup.send,view.card(),key='shop',channel=interaction.channel,view=view,ephemeral=True)
