from datetime import timedelta
import discord
from discord.ext import commands
from sqlalchemy import select
from ..models import Moderation as Case
from ..security import check_hierarchy, DomainError
from ..utils.discord import respond, confirm, embed


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def record(self, ctx, target, action, reason):
        if len(reason) > 500:
            reason = reason[:500]
        with self.bot.db.transaction() as s:
            case = Case(guild_id=ctx.guild.id, user_id=target.id, moderator_id=ctx.author.id, action=action, reason=reason)
            s.add(case)
            s.flush()
        channel = ctx.guild.get_channel(self.bot.core.config(ctx.guild.id)['log_channel'])
        if channel:
            try:
                await channel.send(embed=embed(f'Moderation • {action}', f'Case #{case.id}\nUser: {target.id}\nModerator: {ctx.author.id}\nReason: {reason}'))
            except discord.HTTPException:
                pass
        await respond(ctx, 'Action recorded', f'{action.title()} • Case #{case.id}\n{reason}')

    @commands.hybrid_command(help='Ban a member after confirmation.')
    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str):
        check_hierarchy(ctx.guild, ctx.author, member, ctx.guild.me)
        if await confirm(ctx, f'Ban {member.display_name}?\n{reason[:500]}'):
            # Recheck permission/hierarchy after the confirmation delay.
            current = await ctx.guild.fetch_member(ctx.author.id)
            target = await ctx.guild.fetch_member(member.id)
            if not current.guild_permissions.ban_members:
                raise DomainError('Your ban permission has changed.')
            check_hierarchy(ctx.guild, current, target, ctx.guild.me)
            await target.ban(reason=f'{current.id}: {reason}'[:512], delete_message_seconds=0)
            await self.record(ctx, target, 'ban', reason)

    @commands.hybrid_command(help='Unban a user by Discord ID.')
    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def unban(self, ctx, user_id: str, *, reason: str):
        if not user_id.isdecimal():
            raise DomainError('Use a numeric Discord user ID.')
        user = discord.Object(id=int(user_id))
        await ctx.guild.unban(user, reason=f'{ctx.author.id}: {reason}'[:512])
        await self.record(ctx, user, 'unban', reason)

    @commands.hybrid_command(help='Kick a member after confirmation.')
    @commands.has_guild_permissions(kick_members=True)
    @commands.bot_has_guild_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str):
        check_hierarchy(ctx.guild, ctx.author, member, ctx.guild.me)
        if await confirm(ctx, f'Kick {member.display_name}?'):
            current = await ctx.guild.fetch_member(ctx.author.id)
            target = await ctx.guild.fetch_member(member.id)
            if not current.guild_permissions.kick_members:
                raise DomainError('Your kick permission has changed.')
            check_hierarchy(ctx.guild, current, target, ctx.guild.me)
            await target.kick(reason=f'{current.id}: {reason}'[:512])
            await self.record(ctx, target, 'kick', reason)

    @commands.hybrid_command(help='Timeout a member for 1–40320 minutes.')
    @commands.has_guild_permissions(moderate_members=True)
    @commands.bot_has_guild_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason: str):
        check_hierarchy(ctx.guild, ctx.author, member, ctx.guild.me)
        if not 1 <= minutes <= 40320:
            raise DomainError('Timeout duration must be between 1 minute and 28 days.')
        await member.timeout(timedelta(minutes=minutes), reason=f'{ctx.author.id}: {reason}'[:512])
        await self.record(ctx, member, 'timeout', reason)

    @commands.hybrid_command(help='Remove a member timeout.')
    @commands.has_guild_permissions(moderate_members=True)
    @commands.bot_has_guild_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member, *, reason: str):
        check_hierarchy(ctx.guild, ctx.author, member, ctx.guild.me)
        await member.timeout(None, reason=f'{ctx.author.id}: {reason}'[:512])
        await self.record(ctx, member, 'untimeout', reason)

    @commands.hybrid_command(help='Record a member warning.')
    @commands.has_guild_permissions(moderate_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        check_hierarchy(ctx.guild, ctx.author, member, ctx.guild.me)
        await self.record(ctx, member, 'warn', reason)

    @commands.hybrid_command(help='Show moderation history or warnings only.')
    @commands.has_guild_permissions(moderate_members=True)
    async def history(self, ctx, member: discord.Member, warnings_only: bool = False, page: int = 1):
        with self.bot.db.sessions() as s:
            q = select(Case).where(Case.guild_id == ctx.guild.id, Case.user_id == member.id)
            if warnings_only:
                q = q.where(Case.action == 'warn')
            rows = list(s.scalars(q.order_by(Case.id.desc()).offset((max(1, page)-1)*8).limit(8)))
        await respond(ctx, f'History • {member.display_name}', '\n'.join(f'**#{r.id} {r.action}** • moderator {r.moderator_id}\n{r.created_at:%Y-%m-%d %H:%M} UTC • {r.reason}' for r in rows) or 'No records.')

    @commands.hybrid_command(help='Delete up to 100 recent messages after confirmation.')
    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_guild_permissions(manage_messages=True, read_message_history=True)
    @commands.cooldown(1, 15, commands.BucketType.guild)
    async def purge(self, ctx, count: int):
        if not 1 <= count <= 100:
            raise DomainError('Choose 1–100 messages.')
        if await confirm(ctx, f'Delete up to {count} messages in this channel?'):
            current = await ctx.guild.fetch_member(ctx.author.id)
            if not ctx.channel.permissions_for(current).manage_messages:
                raise DomainError('Your message-management permission has changed.')
            deleted = await ctx.channel.purge(limit=count, before=ctx.message.created_at)
            await self.record(ctx, ctx.author, 'purge', f'Deleted {len(deleted)} messages in {ctx.channel.id}')


async def setup(bot):
    await bot.add_cog(Moderation(bot))
