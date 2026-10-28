"""Discord storefront controls. Every checkout revalidates the saved product terms."""
import logging
import discord
from ..models import Product
from ..security import Actor, DomainError
from .discord import embed


def product_embed(product):
    item = embed(product.name, product.description or 'A new addition to the NEX CODEX collection.')
    item.add_field(name='Price', value=f'{product.currency} {product.price/100:,.2f}' if product.price else 'Free claim')
    item.add_field(name='Collection', value='Server template' if product.category == 'template' else 'Bot source code')
    item.add_field(name='Terms', value=product.terms[:1024] or 'No additional terms.', inline=False)
    item.add_field(name='How it works', value='Confirm your order → private ticket → manual payment review → private delivery.' if product.price else 'Confirm your claim → saved entitlement → private delivery.', inline=False)
    if product.thumbnail:
        item.set_thumbnail(url=product.thumbnail)
    return item


class PersonalView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('Run /shop to open your own storefront.', ephemeral=True)
            return False
        return True

    async def on_error(self, interaction, error, item):
        if isinstance(error, DomainError):
            text = str(error)
        elif isinstance(error, discord.Forbidden):
            text = 'Discord denied this action. Ask staff to check bot permissions and your DM settings. Your order is saved if it was already created; use /orders and /ticket to resume.'
        else:
            text = 'This action could not be completed. Check /orders before retrying a purchase, or contact staff.'
            logging.getLogger('nex').error('storefront.failed type=%s', type(error).__name__)
        send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        await send(embed=embed('Action unavailable', text, error=True), ephemeral=True)


class CheckoutView(PersonalView):
    def __init__(self, user_id, product):
        super().__init__(user_id)
        self.product_id = product.id
        self.expected_terms = (product.price, product.currency, product.terms, product.name)
        self.confirm_order.label = 'Confirm purchase' if product.price else 'Claim free product'
        self.confirm_order.disabled = not product.available

    @discord.ui.button(label='Confirm purchase', style=discord.ButtonStyle.primary, emoji='🛍️')
    async def confirm_order(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        bot = interaction.client
        bot.limiter.check(('checkout', interaction.guild_id, interaction.user.id), 3, 60)
        actor = Actor(interaction.user.id, interaction.guild_id)
        order = bot.market.order(actor, self.product_id, str(interaction.id), expected_terms=self.expected_terms)
        if not order.amount:
            await interaction.followup.send(embed=embed('Your claim is saved', f'**{order.snapshot["name"]}**\nOrder `{order.id}`\nUse `/deliver {order.id}` for private delivery.'), ephemeral=True)
        else:
            await bot.get_cog('Commerce').send_purchase_ticket(interaction.guild, interaction.user, actor, order, interaction.followup.send)
        for control in self.children:
            control.disabled = True
        await interaction.message.edit(view=self)
        self.stop()


class ProductSelect(discord.ui.Select):
    def __init__(self, products):
        super().__init__(placeholder='Explore a product and place an order', options=[discord.SelectOption(label=p.name[:100], value=p.id, description=(f'{p.currency} {p.price/100:,.2f}' if p.price else 'Free') + ' · ' + ('Server template' if p.category == 'template' else 'Bot source code')) for p in products])

    async def callback(self, interaction):
        bot = interaction.client
        with bot.db.sessions() as s:
            product = s.get(Product, self.values[0])
            if not product or product.guild_id != interaction.guild_id or not product.published or product.archived or product.category not in ('template', 'source'):
                raise DomainError('This product is no longer available.')
        await interaction.response.send_message(embed=product_embed(product), view=CheckoutView(interaction.user.id, product), ephemeral=True)


class ShopView(PersonalView):
    def __init__(self, user_id, bot, guild_id, category='', search='', page=1):
        super().__init__(user_id)
        self.bot, self.guild_id, self.category, self.search, self.page = bot, guild_id, category, search, max(1, page)
        self.products = bot.market.browse(guild_id, category or None, search, self.page)
        if self.products:
            self.add_item(ProductSelect(self.products))
        self.previous.disabled = self.page == 1
        self.next_page.disabled = not bot.market.browse(guild_id, category or None, search, self.page+1)

    def card(self):
        item = embed('NEX CODEX • The collection', 'Server templates and bot source code, ready for your next idea.\nChoose a product below to view its terms and confirm an order.')
        for p in self.products:
            price = f'{p.currency} {p.price/100:,.2f}' if p.price else 'Free'
            item.add_field(name=f'{p.name} · {price}', value=f'{p.description[:160] or "Explore this product."}\n`{p.id}`', inline=False)
        if not self.products:
            item.description = 'No published products match this view. Staff can add a product with /productadd and publish it with /productpublish.'
        item.set_footer(text=f'NEX CODEX • Page {self.page} • Payments checked by people')
        return item

    async def turn(self, interaction, offset):
        view = ShopView(self.user_id, self.bot, self.guild_id, self.category, self.search, self.page+offset)
        await interaction.response.edit_message(embed=view.card(), view=view)

    @discord.ui.button(label='Previous', style=discord.ButtonStyle.secondary, emoji='◀️', row=1)
    async def previous(self, interaction, button):
        await self.turn(interaction, -1)

    @discord.ui.button(label='Next', style=discord.ButtonStyle.secondary, emoji='▶️', row=1)
    async def next_page(self, interaction, button):
        await self.turn(interaction, 1)
