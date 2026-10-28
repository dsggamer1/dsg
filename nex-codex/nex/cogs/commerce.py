import asyncio
import io
import json
import discord
from discord.ext import commands
from sqlalchemy import select, func
from ..models import Order, Ticket, Payment, Hosting, Review, Audit, Premium, Reward, Entitlement
from ..security import DomainError
from ..utils.discord import actor, respond, embed, confirm
from ..services.core import audit


class Commerce(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(help='Browse templates, source code and hosting. Filter with category or search.')
    @commands.guild_only()
    async def shop(self, ctx, category: str = '', search: str = '', page: int = 1):
        products = self.bot.market.browse(ctx.guild.id, category or None, search, page)
        item = embed('NEX marketplace', f'Page {max(1, page)} • Use /buy with a product ID.\n{self.bot.config.public_url}/marketplace')
        for p in products:
            item.add_field(name=f'{p.name} • {p.currency} {p.price/100:.2f}' if p.price else f'{p.name} • Free', value=f'{p.description[:150]}\n`{p.id}`', inline=False)
        if not products:
            item.description = 'No products found. Staff can add products from the dashboard.'
        await ctx.send(embed=item)

    @commands.hybrid_command(help='Inspect product terms, details and rating.')
    @commands.guild_only()
    async def product(self, ctx, product_id: str):
        from ..models import Product
        with self.bot.db.sessions() as s:
            p = s.get(Product, product_id)
            if not p or p.guild_id != ctx.guild.id or not p.published or p.archived:
                raise DomainError('Product not found.')
            rating = s.scalar(select(func.avg(Review.rating)).where(Review.product_id == p.id, Review.hidden.is_(False)))
        item = embed(p.name, p.description)
        item.add_field(name='Price', value=f'{p.currency} {p.price/100:.2f}' if p.price else 'Free')
        item.add_field(name='Rating', value=f'{rating:.1f}/5' if rating else 'No reviews yet')
        item.add_field(name='Terms', value=p.terms[:1024] or 'No additional terms.', inline=False)
        if p.thumbnail:
            item.set_thumbnail(url=p.thumbnail)
        await ctx.send(embed=item)

    @commands.hybrid_command(help='Create a confirmed order or claim a free product.')
    @commands.guild_only()
    @commands.cooldown(2, 30, commands.BucketType.user)
    async def buy(self, ctx, product_id: str):
        from ..models import Product
        with self.bot.db.sessions() as s:
            p = s.get(Product, product_id)
            if not p or p.guild_id != ctx.guild.id or not p.published or p.archived:
                raise DomainError('Product not found.')
            shown = (p.price, p.currency, p.terms, p.name)
        if not await confirm(ctx, f'{p.name}\n{p.currency} {p.price/100:.2f}\n{p.terms[:2000]}\nConfirm this order?'):
            return
        with self.bot.db.sessions() as s:
            current = s.get(Product, product_id)
            if not current or (current.price, current.currency, current.terms, current.name) != shown:
                raise DomainError('Product terms changed. Please start again and confirm the updated terms.')
        a = actor(ctx)
        order = self.bot.market.order(a, product_id, str(ctx.interaction.id if ctx.interaction else ctx.message.id), expected_terms=shown)
        if not order.amount:
            await respond(ctx, 'Claim recorded', f'Order `{order.id}`\nUse `/deliver {order.id}` to receive your product privately.')
            return
        await self.purchase_ticket(ctx, a, order)

    async def purchase_ticket(self, ctx, a, order):
        key = (ctx.guild.id, ctx.author.id)
        lock = self.bot.ticket_locks.setdefault(key, asyncio.Lock())
        async with lock:
            _, channel = await self.bot.tickets.open(a, ctx.guild, ctx.author, 'purchase', order.id)
        cfg = self.bot.core.config(ctx.guild.id)
        item = embed('Manual payment • staff verification required', f'Order: `{order.id}`\nAmount: **{order.currency} {order.amount/100:.2f}**\nPayee: {cfg["payee"]}\nUPI: `{cfg["upi_id"]}`\n\n{cfg["payment_instructions"]}\n\nUpload your receipt with `/payment`. A screenshot alone is not proof of payment. Staff will independently check the transaction.')
        if cfg['qr_url']:
            item.set_image(url=cfg['qr_url'])
        await channel.send(content=f'<@{ctx.author.id}>', embed=item)
        await respond(ctx, 'Purchase ticket ready', f'Continue in {channel.mention}. Order `{order.id}`')

    @commands.hybrid_command(help='Open a support, appeal or hosting ticket; resume a purchase with its order ID.')
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
            await respond(ctx, 'Ticket ready', f'{channel.mention}\nTicket `{row.id}`')

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

    @commands.hybrid_command(help='Submit a receipt inside your purchase ticket. Staff must verify it.')
    @commands.guild_only()
    @commands.cooldown(3, 60, commands.BucketType.user)
    async def payment(self, ctx, order_id: str, screenshot: discord.Attachment, reference: str = ''):
        if screenshot.size > 8 * 1024 * 1024 or screenshot.content_type not in ('image/png', 'image/jpeg', 'image/webp'):
            raise DomainError('Upload a PNG, JPEG or WebP screenshot up to 8 MB.')
        with self.bot.db.sessions() as s:
            ticket = s.scalar(select(Ticket).where(Ticket.order_id == order_id, Ticket.guild_id == ctx.guild.id, Ticket.channel_id == ctx.channel.id, Ticket.user_id == ctx.author.id, Ticket.state == 'open'))
            if not ticket:
                raise DomainError('Submit payment inside your open purchase ticket.')
        self.bot.market.submit_payment(actor(ctx), order_id, screenshot.url, reference)
        cfg = self.bot.core.config(ctx.guild.id)
        roles = [discord.Object(id=r) for r in cfg['payment_roles']]
        await ctx.send(content=' '.join(f'<@&{r.id}>' for r in roles), embed=embed('Payment review requested', f'Order `{order_id}`\nReceipt submitted. Staff must check the actual transaction before approval.'), allowed_mentions=discord.AllowedMentions(roles=roles))

    @commands.hybrid_command(help='Approve or reject a submitted payment after independent verification.')
    @commands.guild_only()
    @commands.cooldown(5, 60, commands.BucketType.user)
    async def paymentreview(self, ctx, order_id: str, approve: bool, reason: str = ''):
        actor(ctx).require(self.bot.core.config(ctx.guild.id), 'payment')
        if approve and not await confirm(ctx, 'Have you independently verified this exact payment? Approval enables delivery.'):
            return
        fresh = await ctx.guild.fetch_member(ctx.author.id)
        from ..security import Actor
        a = Actor(fresh.id, ctx.guild.id, frozenset(r.id for r in fresh.roles), fresh.guild_permissions.administrator, fresh.id in self.bot.config.owner_ids)
        order = self.bot.market.review_payment(a, order_id, approve, reason)
        await respond(ctx, 'Payment decision recorded', f'Order `{order.id}` • {order.state}')

    @commands.hybrid_command(help='Retrieve an entitled product privately; hosting shows handoff status.')
    @commands.guild_only()
    @commands.cooldown(3, 60, commands.BucketType.user)
    async def deliver(self, ctx, order_id: str):
        a = actor(ctx)
        result = self.bot.market.delivery(a, order_id)
        if result['delivery_kind'] == 'hosting':
            await respond(ctx, 'Hosting handoff', 'Your verified order is in the staff provisioning queue. Use /orders for status.')
            return
        if result['delivery_kind'] == 'file':
            await ctx.author.send(embed=embed(result['name'], 'Your product file is attached.'), file=discord.File(result['path']))
        else:
            await ctx.author.send(embed=embed(result['name'], result['delivery_value']))
        self.bot.market.delivered(a, order_id)
        await respond(ctx, 'Delivery sent', 'Your product is in your DMs.')

    @commands.hybrid_command(help='View your latest orders and hosting status.')
    @commands.guild_only()
    async def orders(self, ctx, page: int = 1):
        with self.bot.db.sessions() as s:
            rows = list(s.scalars(select(Order).where(Order.guild_id == ctx.guild.id, Order.user_id == ctx.author.id).order_by(Order.created_at.desc()).offset((max(1, page)-1)*8).limit(8)))
            lines = []
            for o in rows:
                h = s.scalar(select(Hosting).where(Hosting.order_id == o.id))
                lines.append(f'**{o.snapshot["name"]}** • {o.state}' + (f' • hosting: {h.state}' if h else '') + f'\n`{o.id}` • {o.currency} {o.amount/100:.2f}')
        # Text-command results are sent by DM to avoid exposing order details.
        if not ctx.interaction:
            await ctx.author.send(embed=embed('Your orders', '\n'.join(lines) or 'No orders yet.'))
        else:
            await respond(ctx, 'Your orders', '\n'.join(lines) or 'No orders yet.')

    @commands.hybrid_command(help='Record a manual cancellation or completed external refund (staff).')
    @commands.guild_only()
    async def orderstate(self, ctx, order_id: str, state: str, *, reason: str):
        self.bot.market.change_order(actor(ctx), order_id, state, reason)
        await respond(ctx, 'Order updated', 'This command records a decision. It does not send money or stop a hosting provider resource.')

    @commands.hybrid_command(help='Record an actual manual hosting provisioning result (staff).')
    @commands.guild_only()
    async def hosting(self, ctx, hosting_id: str, state: str, *, notes: str):
        row = self.bot.community.hosting(actor(ctx), hosting_id, state, notes)
        await respond(ctx, 'Hosting updated', f'{row.id} • {row.state}')

    @commands.hybrid_command(help='Grant, extend, revoke or inspect premium. Zero days means lifetime.')
    @commands.guild_only()
    async def premium(self, ctx, member: discord.Member, action: str = 'inspect', plan: str = 'community', days: int = 30):
        a = actor(ctx)
        if action == 'inspect':
            await respond(ctx, 'Premium status', 'Active' if self.bot.core.has_premium(ctx.guild.id, member.id) else 'Inactive or expired')
            return
        if action not in ('grant', 'extend', 'revoke'):
            raise DomainError('Use grant, extend, revoke or inspect.')
        self.bot.core.premium(a, member.id, plan, days or None, revoke=action == 'revoke', extend=action == 'extend')
        await respond(ctx, 'Premium updated', f'{member.display_name} • {action}')

    @commands.hybrid_command(help='Review a product you own.')
    @commands.guild_only()
    async def review(self, ctx, product_id: str, rating: int, *, feedback: str):
        self.bot.community.review(actor(ctx), product_id, rating, feedback)
        await respond(ctx, 'Review submitted', 'Thank you for sharing your experience.')

    @commands.hybrid_command(help='Hide or restore a product review (staff).')
    @commands.guild_only()
    async def reviewmoderate(self, ctx, review_id: int, hidden: bool, *, reason: str):
        from ..models import Product
        a = actor(ctx)
        a.require(self.bot.core.config(ctx.guild.id))
        if not reason.strip() or len(reason) > 500:
            raise DomainError('Provide a reason of 1–500 characters.')
        with self.bot.db.transaction() as s:
            r = s.get(Review, review_id)
            p = s.get(Product, r.product_id) if r else None
            if not p or p.guild_id != ctx.guild.id:
                raise DomainError('Review not found.')
            r.hidden = hidden
            audit(s, a, 'review.moderate', review_id, hidden=hidden, reason=reason)
        await respond(ctx, 'Review visibility updated')

    @commands.hybrid_command(help='Restrict or restore free claims with a recorded staff reason.')
    @commands.guild_only()
    async def freebierestrict(self, ctx, member: discord.Member, restricted: bool, *, reason: str):
        self.bot.core.restrict(actor(ctx), member.id, reason, restricted)
        await respond(ctx, 'Claim access updated', 'The member can open an appeal ticket to request a review.')

    @commands.hybrid_command(help='Inspect free-claim and membership audit records for a member (staff).')
    @commands.guild_only()
    async def freebiehistory(self, ctx, member_id: str):
        a = actor(ctx)
        a.require(self.bot.core.config(ctx.guild.id))
        if not member_id.isdecimal():
            raise DomainError('Use a numeric Discord user ID.')
        with self.bot.db.sessions() as s:
            rows = list(s.scalars(select(Order).where(Order.guild_id == ctx.guild.id, Order.user_id == int(member_id), Order.amount == 0).order_by(Order.created_at.desc()).limit(10)))
        await respond(ctx, 'Free claim history', '\n'.join(f'{r.created_at:%Y-%m-%d} • {r.snapshot["name"]} • {r.state}' for r in rows) or 'No claims. Leaving a server alone is not evidence of abuse.')


async def setup(bot):
    await bot.add_cog(Commerce(bot))
