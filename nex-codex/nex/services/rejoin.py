"""Opt-in rejoin enforcement. No retroactive blocks or leave-time bans."""
from sqlalchemy import select, delete
from ..models import RejoinBlock
from .core import audit
from ..security import Actor


def exempt(bot, member, cfg):
    return (member.bot or member.id in bot.config.owner_ids or member.id==member.guild.owner_id or member.guild_permissions.administrator or bool({r.id for r in member.roles}.intersection(cfg['staff_roles'])))


def remember(bot,member,cfg):
    if not cfg['restrict_rejoin'] or exempt(bot,member,cfg):return
    with bot.db.transaction() as s:
        if not s.scalar(select(RejoinBlock).where(RejoinBlock.guild_id==member.guild.id,RejoinBlock.user_id==member.id)):
            s.add(RejoinBlock(guild_id=member.guild.id,user_id=member.id))
            audit(s,Actor(member.id,member.guild.id),'rejoin.block',member.id)


async def enforce(bot,member,cfg):
    if not cfg['restrict_rejoin'] or exempt(bot,member,cfg):return False
    with bot.db.sessions() as s:
        blocked=s.scalar(select(RejoinBlock.id).where(RejoinBlock.guild_id==member.guild.id,RejoinBlock.user_id==member.id))
    if not blocked:return False
    if not member.guild.me.guild_permissions.kick_members or member.top_role>=member.guild.me.top_role:
        return None  # Caller logs missing capability; never report a successful kick.
    await member.kick(reason='Configured leave/rejoin restriction; contact server staff for review')
    with bot.db.transaction() as s:audit(s,Actor(bot.user.id,member.guild.id),'rejoin.kick',member.id)
    return True


def clear(bot,actor,user_id):
    actor.require_admin()
    with bot.db.transaction() as s:
        s.execute(delete(RejoinBlock).where(RejoinBlock.guild_id==actor.guild_id,RejoinBlock.user_id==user_id))
        audit(s,actor,'rejoin.clear',user_id)
