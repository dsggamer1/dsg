import logging
import discord
from discord.ext import commands, tasks
from sqlalchemy import select
from ..models import Entitlement, Giveaway, Heartbeat, now
from ..security import Actor, DomainError
from ..services.core import audit
from ..utils.discord import embed, safe_role
from ..utils.theme import themed_embed
from ..utils.cards import send_card
from ..utils.guides import IntroView
from ..services import rejoin


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.worker.start()

    async def cog_unload(self):
        self.worker.cancel()

    async def log(self, guild, title, text):
        channel = guild.get_channel(self.bot.core.config(guild.id)['log_channel'])
        if channel:
            try:
                await channel.send(embed=embed(title, text))
            except discord.HTTPException:
                logging.getLogger('nex').warning('guild_log.failed guild=%s', guild.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot or message.webhook_id or not self.bot.user:
            return
        if self.bot.user.id not in {user.id for user in message.mentions}:
            return
        # Leave mention-prefix commands to discord.py's normal command dispatcher.
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return
        try:
            self.bot.limiter.check(('mention_user', message.guild.id, message.author.id), 2, 30)
            self.bot.limiter.check(('mention_channel', message.channel.id), 5, 30)
        except DomainError:
            return
        cfg = self.bot.core.config(message.guild.id)
        item = themed_embed('help', 'Hey, I’m NEX CODEX', 'Your community, connected. Explore commands, discover server templates and bot source code, or open a private support ticket.', config=cfg)
        item.add_field(name='Start here', value=f"`/help` or `{discord.utils.escape_markdown(cfg['prefix'])}help` • `/shop` • `/ticket`", inline=False)
        if message.author.id in self.bot.config.owner_ids or message.author.guild_permissions.administrator:
            item.add_field(name='Your workspace', value='`/setup` opens the step-by-step guide. `/paymentsetup` configures QR/UPI and ticket roles.', inline=False)
        try:
            await send_card(message.reply, item, key='help', channel=message.channel, view=IntroView(message.author.id,cfg), mention_author=False, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            logging.getLogger('nex').warning('mention.reply.failed guild=%s', message.guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        cfg = self.bot.core.config(member.guild.id)
        try:
            enforced = await rejoin.enforce(self.bot,member,cfg)
        except discord.HTTPException:
            enforced = None
        if enforced is not False:
            await self.log(member.guild, 'Rejoin restriction', f'User {member.id}: '+('kicked' if enforced else 'kick unavailable; check permissions/hierarchy'))
            if enforced:return
        with self.bot.db.transaction() as s:
            audit(s, Actor(member.id, member.guild.id), 'member.join', member.id)
        channel = member.guild.get_channel(cfg['welcome_channel'])
        if channel:
            message = self.render(cfg['welcome_message'], member)
            try:
                await send_card(channel.send, themed_embed('welcome', 'Welcome to the community', message, config=cfg), key='welcome', channel=channel)
            except discord.HTTPException:
                pass
        role = member.guild.get_role(cfg['auto_role'])
        if role:
            try:
                safe_role(member.guild, None, role, cfg['staff_roles'] + cfg['payment_roles'])
                await member.add_roles(role, reason='Configured welcome role')
            except (discord.HTTPException, DomainError):
                await self.log(member.guild, 'Auto-role unavailable', 'Check the configured role and bot hierarchy.')
        await self.log(member.guild, 'Member joined', f'{member.id} • {member.display_name}')

    @staticmethod
    def render(template, member):
        return template.replace('{user}', member.mention).replace('{name}', member.display_name).replace('{server}', member.guild.name)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        cfg = self.bot.core.config(member.guild.id)
        rejoin.remember(self.bot,member,cfg)
        with self.bot.db.transaction() as s:
            count = len(list(s.scalars(select(Entitlement.id).where(Entitlement.guild_id == member.guild.id, Entitlement.user_id == member.id))))
            audit(s, Actor(member.id, member.guild.id), 'member.leave', member.id, entitlement_count=count, enforcement='none')
        channel = member.guild.get_channel(cfg['leave_channel'])
        if channel:
            try:
                await send_card(channel.send, themed_embed('leave', 'Member left', self.render(cfg['leave_message'], member), config=cfg), key='leave', channel=channel)
            except discord.HTTPException:
                pass
        await self.log(member.guild, 'Member left', f'{member.id} • {count} entitlement(s). Departure alone does not establish abuse.')

    @tasks.loop(seconds=30)
    async def worker(self):
        try:
            await self.tick()
        except Exception as exc:
            logging.getLogger('nex').error('worker.failed type=%s', type(exc).__name__)

    @worker.before_loop
    async def before_worker(self):
        await self.bot.wait_until_ready()

    async def tick(self):
        with self.bot.db.transaction() as s:
            h = s.get(Heartbeat, 'bot')
            if not h:
                h = Heartbeat(name='bot')
                s.add(h)
            h.updated_at, h.details = now(), {'guilds': len(self.bot.guilds), 'latency_ms': round(self.bot.latency*1000) if self.bot.is_ready() else None}
        with self.bot.db.sessions() as s:
            due = list(s.scalars(select(Giveaway).where(Giveaway.state == 'open', Giveaway.ends_at <= now()).limit(50)))
        for giveaway in due:
            self.bot.community.draw(giveaway.id)
        with self.bot.db.sessions() as s:
            announcements = list(s.scalars(select(Giveaway).where(Giveaway.state == 'ended', Giveaway.announced.is_(False)).limit(50)))
        for giveaway in announcements:
            channel = self.bot.get_channel(giveaway.channel_id)
            if channel:
                try:
                    await send_card(channel.send, themed_embed('giveaway', 'Giveaway complete', f'**{giveaway.prize}**\n' + (', '.join(f'<@{u}>' for u in giveaway.winners) or 'No eligible entries.'), config=self.bot.core.config(giveaway.guild_id)), key='giveaway', channel=channel)
                except discord.HTTPException:
                    continue
                with self.bot.db.transaction() as s:
                    s.get(Giveaway, giveaway.id).announced = True


async def setup(bot):
    await bot.add_cog(Events(bot))
