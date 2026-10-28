"""Permission/hierarchy checked moderation and safe role operations."""
from datetime import timedelta
import discord
from discord.ext import commands
from sqlalchemy import select
from ..models import Moderation as Case
from ..security import DomainError, check_hierarchy
from ..utils.discord import confirm, respond, safe_role
from ..utils.theme import themed_embed


class Moderation(commands.Cog):
    def __init__(self,bot):
        self.bot=bot

    async def cog_check(self,ctx):
        if not ctx.guild:
            raise DomainError('Use moderation in a server.')
        return True

    async def record(self,ctx,member,action,reason):
        with self.bot.db.transaction() as s:
            row=Case(guild_id=ctx.guild.id,user_id=member.id,moderator_id=ctx.author.id,action=action,reason=reason[:500])
            s.add(row);s.flush()
        await respond(ctx,'Moderation recorded',f'**{action.title()}** · <@{member.id}>\nCase #{row.id} · {reason[:500]}')
        channel=ctx.guild.get_channel(self.bot.core.config(ctx.guild.id)['log_channel'])
        if channel:
            try:
                await channel.send(embed=themed_embed('settings','Moderation log',f'Case #{row.id} · {action}\nMember: {member.id}\nModerator: {ctx.author.id}\n{reason[:500]}'))
            except discord.HTTPException:pass

    async def fresh(self,ctx,member,permission):
        self.bot.limiter.check(('moderation',ctx.guild.id,ctx.author.id),5,30)
        moderator=await ctx.guild.fetch_member(ctx.author.id)
        target=await ctx.guild.fetch_member(member.id)
        bot_member=ctx.guild.me
        if not getattr(moderator.guild_permissions,permission):
            raise DomainError('Your required Discord permission is missing.')
        check_hierarchy(ctx.guild,moderator,target,bot_member)
        return target

    @commands.hybrid_command(help='Kick a member after confirmation; requires Kick Members.')
    @commands.has_guild_permissions(kick_members=True)
    @commands.bot_has_guild_permissions(kick_members=True)
    async def kick(self,ctx,member:discord.Member,*,reason:str='No reason provided'):
        check_hierarchy(ctx.guild,ctx.author,member,ctx.guild.me)
        if await confirm(ctx,f'Kick {member.display_name}?\n{reason[:500]}'):
            target=await self.fresh(ctx,member,'kick_members')
            if not ctx.guild.me.guild_permissions.kick_members:raise DomainError('Bot Kick Members permission is missing.')
            await target.kick(reason=f'{ctx.author.id}: {reason}'[:512])
            await self.record(ctx,target,'kick',reason)

    @commands.hybrid_command(help='Ban a member after confirmation; requires Ban Members.')
    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def ban(self,ctx,member:discord.Member,*,reason:str='No reason provided'):
        check_hierarchy(ctx.guild,ctx.author,member,ctx.guild.me)
        if await confirm(ctx,f'Ban {member.display_name}?\n{reason[:500]}'):
            target=await self.fresh(ctx,member,'ban_members')
            if not ctx.guild.me.guild_permissions.ban_members:raise DomainError('Bot Ban Members permission is missing.')
            await target.ban(reason=f'{ctx.author.id}: {reason}'[:512],delete_message_seconds=0)
            await self.record(ctx,target,'ban',reason)

    @commands.hybrid_command(help='Record a persistent warning; requires Moderate Members.')
    @commands.has_guild_permissions(moderate_members=True)
    async def warn(self,ctx,member:discord.Member,*,reason:str):
        target=await self.fresh(ctx,member,'moderate_members')
        await self.record(ctx,target,'warn',reason)

    @commands.hybrid_command(help='Timeout for 1–40320 minutes; 0 removes timeout.')
    @commands.has_guild_permissions(moderate_members=True)
    @commands.bot_has_guild_permissions(moderate_members=True)
    async def timeout(self,ctx,member:discord.Member,minutes:int,*,reason:str='No reason provided'):
        if not 0<=minutes<=40320:raise DomainError('Use 0–40320 minutes (0 removes timeout).')
        target=await self.fresh(ctx,member,'moderate_members')
        if target.guild_permissions.administrator:raise DomainError('Discord administrators cannot be timed out.')
        if not ctx.guild.me.guild_permissions.moderate_members:raise DomainError('Bot Moderate Members permission is missing.')
        await target.timeout(timedelta(minutes=minutes) if minutes else None,reason=f'{ctx.author.id}: {reason}'[:512])
        await self.record(ctx,target,'timeout' if minutes else 'untimeout',reason)

    async def role_change(self,ctx,member,role,add):
        target=await self.fresh(ctx,member,'manage_roles')
        moderator=await ctx.guild.fetch_member(ctx.author.id)
        if not ctx.guild.me.guild_permissions.manage_roles:raise DomainError('Bot Manage Roles permission is missing.')
        if role.guild.id!=ctx.guild.id:raise DomainError('Choose a role from this server.')
        cfg=self.bot.core.config(ctx.guild.id)
        safe_role(ctx.guild,moderator,role,cfg['staff_roles'])
        await (target.add_roles if add else target.remove_roles)(role,reason=f'NEX CODEX role change by {ctx.author.id}')
        await self.record(ctx,target,'give role' if add else 'take role',f'Role {role.id}')

    @commands.hybrid_command(help='Give a safe nonprivileged role; requires Manage Roles.')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def giverole(self,ctx,member:discord.Member,role:discord.Role):
        await self.role_change(ctx,member,role,True)

    @commands.hybrid_command(help='Remove a safe nonprivileged role; requires Manage Roles.')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def takerole(self,ctx,member:discord.Member,role:discord.Role):
        await self.role_change(ctx,member,role,False)

    @commands.hybrid_command(help='View saved moderation/warning history; requires Moderate Members.')
    @commands.has_guild_permissions(moderate_members=True)
    async def warnings(self,ctx,member:discord.Member):
        with self.bot.db.sessions() as s:
            rows=list(s.scalars(select(Case).where(Case.guild_id==ctx.guild.id,Case.user_id==member.id).order_by(Case.id.desc()).limit(10)))
        await respond(ctx,'Member history','\n'.join(f'#{r.id} **{r.action}** · {r.created_at:%d %b %H:%M} UTC · {r.reason[:150]}' for r in rows) or 'No saved cases.')


async def setup(bot):
    await bot.add_cog(Moderation(bot))
