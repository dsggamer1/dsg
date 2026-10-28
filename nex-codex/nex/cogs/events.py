from collections import defaultdict, deque
from datetime import timedelta
import logging
import discord
from discord.ext import commands, tasks
from sqlalchemy import select, delete
from ..models import Audit, Entitlement, Giveaway, Reminder, Hosting, Heartbeat, OAuthState, WebSession, now
from ..security import Actor, DomainError
from ..services.core import audit
from ..services.automod import Automod
from ..utils.discord import embed, safe_role


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.automod = Automod()
        self.bursts = defaultdict(lambda: deque(maxlen=50))

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
                await channel.send(embed=embed('Welcome to the community', message))
            except discord.HTTPException:
                pass
        role = member.guild.get_role(cfg['auto_role'])
        if role:
            try:
                safe_role(member.guild, None, role)
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
                await channel.send(embed=embed('Member left', self.render(cfg['leave_message'], member)))
            except discord.HTTPException:
                pass
        await self.log(member.guild, 'Member left', f'{member.id} • {count} entitlement(s). Departure alone does not establish abuse.')

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot or not isinstance(message.author, discord.Member):
            return
        cfg = self.bot.core.config(message.guild.id)
        exempt = message.author.guild_permissions.manage_messages or any(r.id in cfg['automod_exempt_roles'] for r in message.author.roles)
        if cfg['automod_enabled'] and not exempt:
            flags = self.automod.inspect(message.guild.id, message.author.id, message.content, len(message.mentions)+len(message.role_mentions)+(cfg['mention_limit'] if message.mention_everyone else 0), cfg)
            if flags:
                result = 'logged'
                if cfg['automod_action'] == 'delete':
                    try:
                        await message.delete()
                        result = 'deleted'
                    except discord.HTTPException:
                        result = 'delete_failed'
                with self.bot.db.transaction() as s:
                    audit(s, Actor(self.bot.user.id, message.guild.id), 'automod.'+result, message.author.id, flags=flags, message_id=message.id)
                await self.log(message.guild, 'Automod signal', f'User {message.author.id}\n{", ".join(flags)} • {result}\nNo automatic ban or timeout.')
                return
        level = self.bot.community.xp(message.guild.id, message.author.id)
        if level:
            channel = message.guild.get_channel(cfg['level_channel'])
            if channel:
                try:
                    await channel.send(embed=embed('Level up', f'{message.author.display_name} reached **level {level}**.'))
                except discord.HTTPException:
                    pass
            role = message.guild.get_role(cfg['level_rewards'].get(str(level)))
            if role:
                try:
                    safe_role(message.guild, None, role)
                    await message.author.add_roles(role, reason=f'Level {level} reward')
                except (discord.HTTPException, DomainError):
                    await self.log(message.guild, 'Level reward unavailable', f'Role assignment failed for level {level}.')

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild and not message.author.bot:
            await self.log(message.guild, 'Message deleted', f'Author {message.author.id} • channel {message.channel.id}\n{message.content[:1200] or "Content unavailable"}')

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.guild and not after.author.bot and before.content != after.content:
            await self.log(after.guild, 'Message edited', f'Author {after.author.id} • channel {after.channel.id}\nBefore: {before.content[:700]}\nAfter: {after.content[:700]}')

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        cfg = self.bot.core.config(entry.guild.id)
        supported = {discord.AuditLogAction.channel_delete, discord.AuditLogAction.role_delete, discord.AuditLogAction.ban, discord.AuditLogAction.kick, discord.AuditLogAction.webhook_create}
        if not cfg['security_enabled'] or entry.action not in supported or not entry.user_id:
            return
        if entry.user_id in {*cfg['security_exempt_users'], entry.guild.owner_id, self.bot.user.id}:
            return
        with self.bot.db.transaction() as s:
            if s.scalar(select(Audit.id).where(Audit.guild_id == entry.guild.id, Audit.action == 'security.event', Audit.target == str(entry.id))):
                return
            audit(s, Actor(entry.user_id, entry.guild.id), 'security.event', entry.id, event=entry.action.name)
            s.flush()
            # Database-backed burst window survives restarts and duplicate gateway events.
            recent = list(s.scalars(select(Audit.id).where(Audit.guild_id == entry.guild.id, Audit.actor_id == entry.user_id, Audit.action == 'security.event', Audit.created_at >= now()-timedelta(seconds=cfg['security_window']))))
            incident = len(recent) >= cfg['security_threshold']
            if incident:
                audit(s, Actor(entry.user_id, entry.guild.id), 'security.incident', entry.id, count=len(recent), response='alert')
        if incident:
            await self.log(entry.guild, 'Security incident • review required', f'Actor {entry.user_id}: {len(recent)} destructive audit events in {cfg["security_window"]} seconds. Latest: {entry.action.name}. Review Discord audit logs and remove unsafe permissions if needed. Automatic rollback is not available.')

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
            for hosting in s.scalars(select(Hosting).where(Hosting.expires_at <= now(), Hosting.state.in_(['running', 'stopped']))):
                hosting.state = 'expired'  # Records expiry only; never claims provider shutdown.
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
                    await channel.send(embed=embed('Giveaway complete', f'**{giveaway.prize}**\n' + (', '.join(f'<@{u}>' for u in giveaway.winners) or 'No eligible entries.')))
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
