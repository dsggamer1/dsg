import logging
import discord
from discord.ext import commands, tasks
from sqlalchemy import select, delete
from ..models import Entitlement, Giveaway, Reminder, Heartbeat, OAuthState, WebSession, now
from ..security import Actor, DomainError
from ..services.core import audit
from ..utils.discord import embed, safe_role
from ..utils.theme import themed_embed


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
    async def on_member_join(self, member):
        cfg = self.bot.core.config(member.guild.id)
        with self.bot.db.transaction() as s:
            audit(s, Actor(member.id, member.guild.id), 'member.join', member.id)
        channel = member.guild.get_channel(cfg['welcome_channel'])
        if channel:
            message = self.render(cfg['welcome_message'], member)
            try:
                await channel.send(embed=themed_embed('welcome', 'Welcome to the community', message, config=cfg))
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
        with self.bot.db.transaction() as s:
            count = len(list(s.scalars(select(Entitlement.id).where(Entitlement.guild_id == member.guild.id, Entitlement.user_id == member.id))))
            audit(s, Actor(member.id, member.guild.id), 'member.leave', member.id, entitlement_count=count, enforcement='none')
        channel = member.guild.get_channel(cfg['leave_channel'])
        if channel:
            try:
                await channel.send(embed=themed_embed('leave', 'Member left', self.render(cfg['leave_message'], member), config=cfg))
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
            s.execute(delete(OAuthState).where(OAuthState.expires_at < now()))
            s.execute(delete(WebSession).where(WebSession.expires_at < now()))
        with self.bot.db.sessions() as s:
            due = list(s.scalars(select(Giveaway).where(Giveaway.state == 'open', Giveaway.ends_at <= now()).limit(50)))
            reminders = list(s.scalars(select(Reminder).where(Reminder.sent.is_(False), Reminder.due_at <= now()).limit(50)))
        for giveaway in due:
            self.bot.community.draw(giveaway.id)
        with self.bot.db.sessions() as s:
            announcements = list(s.scalars(select(Giveaway).where(Giveaway.state == 'ended', Giveaway.announced.is_(False)).limit(50)))
        for giveaway in announcements:
            channel = self.bot.get_channel(giveaway.channel_id)
            if channel:
                try:
                    await channel.send(embed=themed_embed('giveaway', 'Giveaway complete', f'**{giveaway.prize}**\n' + (', '.join(f'<@{u}>' for u in giveaway.winners) or 'No eligible entries.'), config=self.bot.core.config(giveaway.guild_id)))
                except discord.HTTPException:
                    continue
                with self.bot.db.transaction() as s:
                    s.get(Giveaway, giveaway.id).announced = True
        for reminder in reminders:
            try:
                user = self.bot.get_user(reminder.user_id) or await self.bot.fetch_user(reminder.user_id)
                await user.send(embed=embed('Your reminder', reminder.text))
            except discord.HTTPException:
                continue
            with self.bot.db.transaction() as s:
                s.get(Reminder, reminder.id).sent = True


async def setup(bot):
    await bot.add_cog(Events(bot))
