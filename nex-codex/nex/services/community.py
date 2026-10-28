import secrets
from sqlalchemy import select
from ..models import Giveaway, Entry, now
from ..security import DomainError
from .core import config, audit


class Community:
    def __init__(self, db):
        self.db = db

    def enter(self, actor, giveaway_id):
        with self.db.transaction() as s:
            g = s.get(Giveaway, giveaway_id)
            if not g or g.guild_id != actor.guild_id or g.state != 'open' or g.ends_at <= now():
                raise DomainError('This giveaway is closed.')
            if s.scalar(select(Entry).where(Entry.giveaway_id == g.id, Entry.user_id == actor.user_id)):
                raise DomainError('You have already entered.')
            s.add(Entry(giveaway_id=g.id, user_id=actor.user_id))

    def draw(self, giveaway_id, actor=None):
        with self.db.transaction() as s:
            g = s.get(Giveaway, giveaway_id)
            if not g:
                raise DomainError('Giveaway not found.')
            if actor:
                if actor.guild_id != g.guild_id:
                    raise DomainError('Giveaway not found.')
                actor.require(config(s, actor.guild_id))
                if g.state != 'ended':
                    raise DomainError('Only ended giveaways can be rerolled.')
            elif g.state != 'open' or g.ends_at > now():
                return g
            entries = list(s.scalars(select(Entry.user_id).where(Entry.giveaway_id == g.id)))
            g.winners = secrets.SystemRandom().sample(entries, min(len(entries), g.winner_count))
            g.state, g.announced = 'ended', False
            if actor:
                audit(s, actor, 'giveaway.reroll', g.id, winners=g.winners)
            return g
