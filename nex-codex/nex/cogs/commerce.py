from typing import Literal
import asyncio
import io
import json
import discord
from discord.ext import commands
from sqlalchemy import select
from ..models import Order, Ticket
from ..security import DomainError
from ..utils.discord import actor, respond, embed, confirm, price_minor, owner_only
from ..services.core import audit
from ..schemas import ProductInput
from ..utils.theme import themed_embed
from ..utils.cards import send_card
from ..utils.storefront import ShopView, CheckoutView, ShopPanel, product_embed


class Commerce(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(ShopPanel())

    @commands.hybrid_command(extras={'owner_only': True}, help='Post a persistent shop panel in a channel (bot owner).')
    @owner_only()
    @commands.guild_only()
    async def createshop(self, ctx, channel: discord.TextChannel = None):
        a = actor(ctx)
        a.require_owner()
        channel = channel or ctx.guild.get_channel(self.bot.core.config(ctx.guild.id)['shop_channel']) or ctx.channel
        if channel.guild.id != ctx.guild.id:
            raise DomainError('Choose a channel in this server.')
        cfg = self.bot.core.config(ctx.guild.id)
        item = themed_embed('shop', cfg['shop_title'], cfg['shop_description'], config=cfg)
        if cfg['shop_image']:
            item.set_image(url=cfg['shop_image'])
        message = await send_card(channel.send, item, key='shop', channel=channel, view=ShopPanel(cfg))
        with self.bot.db.transaction() as session:
            audit(session, a, 'shop.publish', message.id, channel_id=channel.id)
        await respond(ctx, 'Shop created', f'Your shop panel is live in {channel.mention}. Its browse button survives bot restarts.')

    @commands.hybrid_command(help='Browse templates and bot source code. Filter with category or search.')
    @commands.guild_only()
    async def shop(self, ctx, category: Literal['template', 'bot'] = None, search: str = '', page: int = 1):
        view = ShopView(ctx.author.id, self.bot, ctx.guild.id, category or '', search, page)
        await send_card(ctx.send, view.card(), key='shop', channel=ctx.channel, view=view)

    @commands.hybrid_command(help='Inspect product details, price and terms.')
    @commands.guild_only()
    async def product(self, ctx, product_id: str):
        from ..models import Product
        with self.bot.db.sessions() as s:
            p = self.bot.market.resolve(s, ctx.guild.id, product_id)
            if not p or p.category not in ('template', 'bot') or p.guild_id != ctx.guild.id or not p.published or p.archived:
                raise DomainError('Product not found.')
        cfg = self.bot.core.config(ctx.guild.id)
        item = product_embed(p, cfg)
        await send_card(ctx.send, item, key='product', channel=ctx.channel, view=CheckoutView(ctx.author.id, p, cfg))

    @commands.hybrid_command(name='addproduct', aliases=['productadd'], extras={'owner_only': True}, help='Create a template/bot draft (bot owner). Price example: 499.00.')
    @owner_only()
    @commands.guild_only()
    async def productadd(self, ctx, name: str, category: Literal['template', 'bot'], price: str, delivery: str, description: str = ''):
        a = actor(ctx)
        cfg = self.bot.core.config(ctx.guild.id)
        a.require_owner()
        kind = 'link' if delivery.startswith('https://') else 'instructions'
        p = self.bot.market.save_product(a, {'name': name, 'category': category, 'price': price_minor(price), 'currency': cfg['currency'], 'delivery_kind': kind, 'delivery_value': delivery, 'description': description})
        await respond(ctx, 'Product draft created', f'**{p.name}** · {p.currency} {p.price/100:,.2f}\nProduct ID: `{p.code}`\nSet terms: `/productedit product_id: {p.code} field: terms value: YOUR_TERMS`\nPublish: `/productpublish product_id: {p.code} published: true`\nThen `/createshop`. Use `/setup` → Add products for examples.')

    @commands.hybrid_command(extras={'owner_only': True}, help='Edit a product field (bot owner). Prices use currency units; other values use JSON.')
    @owner_only()
    @commands.guild_only()
    async def productedit(self, ctx, product_id: str, field: str, *, value: str):
        from ..models import Product
        a = actor(ctx)
        a.require_owner()
        if field not in ProductInput.model_fields:
            raise DomainError('Unknown product field. Use name, description, price, terms, thumbnail, delivery_kind, delivery_value, published, archived or available.')
        with self.bot.db.sessions() as session:
            product = self.bot.market.resolve(session, ctx.guild.id, product_id)
            if not product or product.guild_id != ctx.guild.id or product.category not in ('template', 'bot'):
                raise DomainError('Product not found.')
            data = {key: getattr(product, key) for key in ProductInput.model_fields}
        if field == 'price':
            data[field] = price_minor(value)
        else:
            try:
                data[field] = json.loads(value)
            except ValueError:
                data[field] = value
        self.bot.market.save_product(a, data, product_id)
        await respond(ctx, 'Product updated', f'Updated **{field}** for {product.name}. Existing orders keep their original purchase terms.')

    @commands.hybrid_command(extras={'owner_only': True}, help='Publish or unpublish a reviewed product (bot owner).')
    @owner_only()
    @commands.guild_only()
    async def productpublish(self, ctx, product_id: str, published: bool = True):
        from ..models import Product
        a = actor(ctx)
        a.require_owner()
        with self.bot.db.sessions() as session:
            p = self.bot.market.resolve(session, ctx.guild.id, product_id)
            if not p or p.guild_id != ctx.guild.id or p.category not in ('template', 'bot'):
                raise DomainError('Product not found.')
            data = {key: getattr(p, key) for key in ProductInput.model_fields}
        data['published'] = published
        self.bot.market.save_product(a, data, product_id)
        await respond(ctx, 'Storefront updated', f'**{p.name}** is now {"published" if published else "unpublished"}. Use /shop to browse the collection.')

    @commands.hybrid_command(extras={'owner_only': True}, help='Change a product’s short public ID without changing old orders (owner).')
    @owner_only()
    @commands.guild_only()
    async def productid(self, ctx, product_id: str, new_id: str):
        product=self.bot.market.change_code(actor(ctx),product_id,new_id)
        await respond(ctx,'Product ID updated',f'**{product.name}** → `{product.code}`. Existing orders are preserved.')

    async def product_choices(self, interaction, current):
        if not interaction.guild_id:
            return []
        owner=interaction.user.id in self.bot.config.owner_ids
        # Search the whole guild catalogue, including owner drafts, not only its first page.
        from ..models import Product
        with self.bot.db.sessions() as session:
            query=select(Product).where(Product.guild_id==interaction.guild_id,Product.category.in_(['template','bot']))
            if not owner:
                query=query.where(Product.published.is_(True),Product.archived.is_(False))
            if current:
                from sqlalchemy import or_
                term='%'+current[:80]+'%'
                query=query.where(or_(Product.name.ilike(term),Product.code.ilike(term)))
            rows=list(session.scalars(query.order_by(Product.name).limit(25)))
        return [discord.app_commands.Choice(name=(f'{p.name} · {p.code}'+(' · Draft' if not p.published else ''))[:100],value=p.code) for p in rows]

    @commands.hybrid_command(help='Create a confirmed order or claim a free product.')
    @commands.guild_only()
    @commands.cooldown(2, 30, commands.BucketType.user)
    async def buy(self, ctx, product_id: str):
        from ..models import Product
        with self.bot.db.sessions() as s:
            p = self.bot.market.resolve(s, ctx.guild.id, product_id)
            if not p or p.category not in ('template', 'bot') or p.guild_id != ctx.guild.id or not p.published or p.archived:
                raise DomainError('Product not found.')
            shown = (p.price, p.currency, p.terms, p.name)
        if not await confirm(ctx, f'{p.name}\n{p.currency} {p.price/100:.2f}\n{p.terms[:2000]}\nConfirm this order?'):
            return
        with self.bot.db.sessions() as s:
            current = self.bot.market.resolve(s, ctx.guild.id, product_id)
            if not current or (current.price, current.currency, current.terms, current.name) != shown:
                raise DomainError('Product terms changed. Please start again and confirm the updated terms.')
        a = actor(ctx)
        order = self.bot.market.order(a, product_id, str(ctx.interaction.id if ctx.interaction else ctx.message.id), expected_terms=shown)
        if not order.amount:
            await respond(ctx, 'Claim recorded', f'Order `{order.id}`\nUse `/deliver {order.id}` to receive your product privately.')
            return
        await self.purchase_ticket(ctx, a, order)

    async def purchase_ticket(self, ctx, a, order):
        await self.send_purchase_ticket(ctx.guild, ctx.author, a, order, ctx.send)

    async def send_purchase_ticket(self, guild, customer, a, order, reply):
        key = (guild.id, customer.id)
        lock = self.bot.ticket_locks.setdefault(key, asyncio.Lock())
        async with lock:
            _, channel = await self.bot.tickets.open(a, guild, customer, 'purchase', order.id)
        cfg = self.bot.core.config(guild.id)
        item = themed_embed('ticket', 'Your private order workspace', f'Order: `{order.id}`\nProduct: **{order.snapshot["name"]}**\nListed price: **{order.currency} {order.amount/100:.2f}**\n\nDiscuss your request with staff here. The bot does not collect or verify payments. Product access stays locked until the bot owner releases this order.', config=cfg)
        await send_card(channel.send, item, key='ticket', channel=channel, content=f'<@{customer.id}>')
        await send_card(reply, themed_embed('ticket', 'Purchase ticket ready', f'Continue in {channel.mention}. Order `{order.id}`', config=cfg), key='ticket', channel=channel, ephemeral=True)

    @commands.hybrid_command(help='Open a support or appeal ticket; resume a purchase with its order ID.')
    @commands.guild_only()
    @commands.cooldown(2, 60, commands.BucketType.user)
    async def ticket(self, ctx, category: str = 'support', order_id: str = ''):
        a = actor(ctx)
        if order_id:
            with self.bot.db.sessions() as s:
                order = self.bot.market.scoped_order(s, a, order_id)
            await self.purchase_ticket(ctx, a, order)
        else:
            lock = self.bot.ticket_locks.setdefault((ctx.guild.id, ctx.author.id), asyncio.Lock())
            async with lock:
                row, channel = await self.bot.tickets.open(a, ctx.guild, ctx.author, category)
            await send_card(ctx.send, themed_embed('ticket', 'Ticket ready', f'{channel.mention}\nTicket `{row.id}`', config=self.bot.core.config(ctx.guild.id)), key='ticket', channel=ctx.channel, ephemeral=True)

    @commands.hybrid_command(help='Claim, unclaim, close or reopen a ticket (staff).')
    @commands.guild_only()
    async def ticketmanage(self, ctx, ticket_id: str, action: str):
        await self.bot.tickets.change(actor(ctx), ctx.guild, ticket_id, action)
        await respond(ctx, 'Ticket updated', action.title())

    @commands.hybrid_command(help='Export the last 500 messages from this ticket (staff).')
    @commands.guild_only()
    async def transcript(self, ctx):
        a = actor(ctx)
        a.require(self.bot.core.config(ctx.guild.id))
        with self.bot.db.sessions() as s:
            row = s.scalar(select(Ticket).where(Ticket.guild_id == ctx.guild.id, Ticket.channel_id == ctx.channel.id))
            if not row:
                raise DomainError('Use this command inside a ticket.')
        lines = []
        async for m in ctx.channel.history(limit=500, oldest_first=False):
            lines.append(f'[{m.created_at.isoformat()}] {m.author.id}: {m.clean_content}\n' + '\n'.join(a.url for a in m.attachments))
        await ctx.author.send(file=discord.File(io.BytesIO('\n\n'.join(reversed(lines)).encode()), filename=f'ticket-{row.id}.txt'))
        await respond(ctx, 'Transcript sent', 'Sent privately to your DMs. Attachment URLs may expire.')



    @commands.hybrid_command(extras={'owner_only': True}, help='Release product access for a manually handled order (bot owner).')
    @owner_only()
    @commands.guild_only()
    async def orderfulfill(self, ctx, order_id: str, *, reason: str):
        actor(ctx).require_owner()
        if not await confirm(ctx, 'Release product access for this order? This does not send the product yet.'):
            return
        # Recheck the configured bot owner at the mutation boundary.
        self.bot.market.fulfill(actor(ctx), order_id, reason)
        await respond(ctx, 'Product access released', f'Order `{order_id}` is ready. The customer can use `/deliver order_id: {order_id}` with DMs open.')

    @commands.hybrid_command(help='Retrieve an entitled product privately; after a free claim or owner release.')
    @commands.guild_only()
    @commands.cooldown(3, 60, commands.BucketType.user)
    async def deliver(self, ctx, order_id: str):
        a = actor(ctx)
        result = self.bot.market.delivery(a, order_id)
        if result['delivery_kind'] == 'file':
            await ctx.author.send(embed=embed(result['name'], 'Your product file is attached.'), file=discord.File(result['path']))
        else:
            await send_card(ctx.author.send, themed_embed('product', result['name'], result['delivery_value'], config=self.bot.core.config(ctx.guild.id)), key='product')
        self.bot.market.delivered(a, order_id)
        await respond(ctx, 'Delivery sent', 'Your product is in your DMs.')

    @commands.hybrid_command(help='View your latest orders and delivery status.')
    @commands.guild_only()
    async def orders(self, ctx, page: int = 1):
        with self.bot.db.sessions() as s:
            rows = list(s.scalars(select(Order).where(Order.guild_id == ctx.guild.id, Order.user_id == ctx.author.id).order_by(Order.created_at.desc()).offset((max(1, page)-1)*8).limit(8)))
            lines = []
            for o in rows:
                lines.append(f'**{o.snapshot["name"]}** • {o.state}' + f'\n`{o.id}` • {o.currency} {o.amount/100:.2f}')
        # Text-command results are sent by DM to avoid exposing order details.
        if not ctx.interaction:
            await send_card(ctx.author.send, themed_embed('shop', 'Your orders', '\n'.join(lines) or 'No orders yet.', config=self.bot.core.config(ctx.guild.id)), key='shop')
        else:
            await respond(ctx, 'Your orders', '\n'.join(lines) or 'No orders yet.')

    @commands.hybrid_command(help='Cancel an order and revoke its delivery access (staff).')
    @commands.guild_only()
    async def orderstate(self, ctx, order_id: str, state: str, *, reason: str):
        self.bot.market.change_order(actor(ctx), order_id, state, reason)
        await respond(ctx, 'Order updated', 'Order cancelled; its product access is revoked.')



async def setup(bot):
    cog=Commerce(bot)
    for name in ('product','productedit','productpublish','productid','buy'):
        getattr(cog,name).app_command.autocomplete('product_id')(cog.product_choices)
    await bot.add_cog(cog)
