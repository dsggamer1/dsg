from datetime import timedelta
import secrets
from sqlalchemy import select, func
from ..models import Entitlement, Order, Review, Reward, Referral, Level, Giveaway, Entry, Hosting, now
from ..security import DomainError
from .core import config, audit


class Community:
    def __init__(self, db):
        self.db = db

    def review(self, actor, product_id, rating, text):
        if not 1 <= rating <= 5 or not 1 <= len(text.strip()) <= 1000:
            raise DomainError('Use a rating from 1–5 and 1–1000 characters.')
        with self.db.transaction() as s:
            e = s.scalar(select(Entitlement).where(Entitlement.guild_id == actor.guild_id, Entitlement.user_id == actor.user_id, Entitlement.product_id == product_id))
            if not e:
                raise DomainError('Only entitled customers may review this product.')
            if not config(s, actor.guild_id)['reviews_allow_free'] and s.get(Order, e.order_id).amount == 0:
                raise DomainError('This server requires a paid purchase to review.')
            if s.scalar(select(Review).where(Review.product_id == product_id, Review.user_id == actor.user_id)):
                raise DomainError('You already reviewed this product.')
            s.add(Review(product_id=product_id, user_id=actor.user_id, rating=rating, text=text))
            audit(s, actor, 'review.create', product_id)

    def refer(self, actor, referrer_id):
        if actor.user_id == referrer_id:
            raise DomainError('You cannot refer yourself.')
        with self.db.transaction() as s:
            cfg = config(s, actor.guild_id)
            if not cfg['rewards_enabled']:
                raise DomainError('Referral rewards are disabled.')
            if s.scalar(select(Referral).where(Referral.guild_id == actor.guild_id, Referral.invitee_id == actor.user_id)):
                raise DomainError('A referral has already been recorded.')
            if not s.scalar(select(Entitlement).where(Entitlement.guild_id == actor.guild_id, Entitlement.user_id == actor.user_id)):
                raise DomainError('Claim or purchase a product before redeeming a referral.')
            s.add(Referral(guild_id=actor.guild_id, referrer_id=referrer_id, invitee_id=actor.user_id))
            s.add(Reward(guild_id=actor.guild_id, user_id=referrer_id, points=cfg['referral_points'], event_key=f'referral:{actor.guild_id}:{actor.user_id}'))
            audit(s, actor, 'referral.redeem', referrer_id)

    def xp(self, guild_id, user_id):
        with self.db.transaction() as s:
            cfg = config(s, guild_id)
            if not cfg['leveling_enabled']:
                return None
            row = s.scalar(select(Level).where(Level.guild_id == guild_id, Level.user_id == user_id))
            if not row:
                row = Level(guild_id=guild_id, user_id=user_id, xp=0)
                s.add(row)
            if row.last_xp and row.last_xp + timedelta(seconds=cfg['xp_cooldown']) > now():
                return None
            old = row.xp // 100
            row.xp += 10
            row.last_xp = now()
            return row.xp // 100 if row.xp // 100 > old else None

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

    def hosting(self, actor, hosting_id, state, notes):
        allowed = {'queued': {'provisioning', 'cancelled'}, 'provisioning': {'running', 'failed', 'cancelled'}, 'running': {'stopped', 'failed', 'expired', 'cancelled'}, 'stopped': {'running', 'cancelled', 'expired'}, 'failed': {'provisioning', 'cancelled'}, 'expired': set(), 'cancelled': set()}
        with self.db.transaction() as s:
            actor.require(config(s, actor.guild_id))
            h = s.get(Hosting, hosting_id)
            order = s.get(Order, h.order_id) if h else None
            if not order or order.guild_id != actor.guild_id or order.state not in ('paid', 'delivered'):
                raise DomainError('Hosting order not available.')
            if state not in allowed[h.state] or not notes.strip() or len(notes) > 1000:
                raise DomainError('Invalid hosting transition or missing provisioning notes.')
            h.state, h.notes = state, notes
            if state == 'running' and h.expires_at is None:
                h.expires_at = now() + timedelta(days=order.snapshot['duration_days'])
                order.state, order.delivered_at = 'delivered', now()
            audit(s, actor, 'hosting.' + state, h.id, notes=notes)
            return h
