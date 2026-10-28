import discord
from sqlalchemy import select
from ..models import Ticket, Order
from ..security import DomainError
from .core import config, audit


def ticket_overwrites(guild, customer, bot_member, staff_roles):
    if not staff_roles:
        raise DomainError('Configure at least one staff role before opening tickets.')
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        customer: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
        bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, attach_files=True),
    }
    for role in staff_roles:
        if role == guild.default_role:
            raise DomainError('The everyone role cannot be ticket staff.')
        overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    return overwrites


class Tickets:
    def __init__(self, db):
        self.db = db

    def reserve(self, actor, category, order_id=None):
        if category not in ('support', 'purchase', 'hosting', 'appeal'):
            raise DomainError('Invalid ticket category.')
        with self.db.transaction() as s:
            cfg = config(s, actor.guild_id)
            if not cfg['staff_roles']:
                raise DomainError('Staff must configure ticket roles first.')
            if order_id:
                order = s.get(Order, order_id)
                if not order or order.guild_id != actor.guild_id or order.user_id != actor.user_id:
                    raise DomainError('Order not found.')
                existing = s.scalar(select(Ticket).where(Ticket.order_id == order_id))
                if existing:
                    return existing
            key = f'{actor.guild_id}:{actor.user_id}:{category}'
            existing = s.scalar(select(Ticket).where(Ticket.active_key == key))
            if existing:
                if order_id and existing.order_id != order_id:
                    raise DomainError('Close your current purchase ticket before opening another.')
                return existing
            row = Ticket(guild_id=actor.guild_id, user_id=actor.user_id, category=category, order_id=order_id, active_key=key)
            s.add(row)
            s.flush()
            audit(s, actor, 'ticket.reserve', row.id)
            return row

    async def open(self, actor, guild, customer, category='support', order_id=None):
        row = self.reserve(actor, category, order_id)
        if row.state == 'closed':
            raise DomainError('This ticket is closed. Ask staff to reopen it.')
        if row.channel_id:
            channel = guild.get_channel(row.channel_id)
            if channel:
                return row, channel
            raise DomainError('Ticket channel is missing. Ask staff to repair or close the ticket.')
        with self.db.sessions() as s:
            cfg = config(s, actor.guild_id)
        roles = [guild.get_role(r) for r in set(cfg['staff_roles'] + cfg['payment_roles'])]
        if any(role is None for role in roles):
            raise DomainError('A configured ticket role no longer exists.')
        # Recover a channel created before a process crash, identified by its immutable ticket ID.
        channel = next((c for c in guild.text_channels if c.topic == f'NEX ticket {row.id}'), None)
        if channel is None:
            channel = await guild.create_text_channel(f'ticket-{row.id[:8]}', category=guild.get_channel(cfg['ticket_category']), topic=f'NEX ticket {row.id}', overwrites=ticket_overwrites(guild, customer, guild.me, roles), reason='NEX CODEX private ticket')
        with self.db.transaction() as s:
            current = s.get(Ticket, row.id)
            current.channel_id, current.state = channel.id, 'open'
            audit(s, actor, 'ticket.open', row.id)
        return row, channel

    async def change(self, actor, guild, ticket_id, action):
        with self.db.sessions() as s:
            cfg = config(s, actor.guild_id)
            actor.require(cfg)
            row = s.get(Ticket, ticket_id)
            if not row or row.guild_id != actor.guild_id:
                raise DomainError('Ticket not found.')
            channel = guild.get_channel(row.channel_id)
        if not channel:
            raise DomainError('Ticket channel unavailable.')
        if action in ('close', 'reopen'):
            member = guild.get_member(row.user_id) or await guild.fetch_member(row.user_id)
            if action == 'reopen':
                with self.db.sessions() as s:
                    duplicate = s.scalar(select(Ticket).where(Ticket.active_key == f'{row.guild_id}:{row.user_id}:{row.category}', Ticket.id != row.id))
                    if duplicate:
                        raise DomainError('This customer already has an active ticket in that category.')
            await channel.set_permissions(member, view_channel=True, send_messages=action == 'reopen', read_message_history=True, attach_files=action == 'reopen', reason=f'NEX ticket {action}')
        elif action not in ('claim', 'unclaim'):
            raise DomainError('Use close, reopen, claim or unclaim.')
        with self.db.transaction() as s:
            current = s.get(Ticket, row.id)
            if action in ('claim', 'unclaim'):
                current.staff_id = actor.user_id if action == 'claim' else None
            else:
                current.state = 'closed' if action == 'close' else 'open'
                current.active_key = None if action == 'close' else f'{row.guild_id}:{row.user_id}:{row.category}'
            audit(s, actor, 'ticket.' + action, row.id)
