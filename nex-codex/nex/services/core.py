from datetime import timedelta
from sqlalchemy import select, func
from ..models import Guild, Audit, Premium, Restriction, now
from ..schemas import GuildConfig
from ..security import DomainError


def config(session, guild_id):
    row = session.get(Guild, guild_id)
    return GuildConfig.model_validate(row.settings if row else {}).model_dump()


def audit(session, actor, action, target='', **details):
    session.add(Audit(guild_id=actor.guild_id, actor_id=actor.user_id, action=action, target=str(target), details=details))


class Core:
    def __init__(self, db):
        self.db = db

    def config(self, guild_id):
        with self.db.sessions() as session:
            return config(session, guild_id)

    def configure(self, actor, changes):
        actor.require_admin()
        with self.db.transaction() as s:
            value = GuildConfig.model_validate(config(s, actor.guild_id) | changes).model_dump()
            if actor.guild_id in value['staff_roles'] + value['payment_roles'] + value['self_roles']:
                raise DomainError('The everyone role cannot be used for staff, payment review or self-service.')
            automatic_roles = set(value['self_roles']) | set(value['level_rewards'].values()) | {value['auto_role']}
            if automatic_roles.intersection(value['staff_roles'] + value['payment_roles']):
                raise DomainError('Staff and payment roles cannot be self-service, auto-role or level rewards.')
            row = s.get(Guild, actor.guild_id)
            if row:
                row.settings = value
            else:
                s.add(Guild(id=actor.guild_id, settings=value))
            audit(s, actor, 'configuration.update', fields=list(changes))
        return value

    def premium(self, actor, user_id, plan, days=None, revoke=False, extend=False):
        actor.require(self.config(actor.guild_id))
        if not plan or len(plan) > 50 or days is not None and not 1 <= days <= 36500:
            raise DomainError('Use a plan name and 1–36500 days, or lifetime.')
        with self.db.transaction() as s:
            row = s.scalar(select(Premium).where(Premium.guild_id == actor.guild_id, Premium.user_id == user_id))
            if not row:
                row = Premium(guild_id=actor.guild_id, user_id=user_id, plan=plan)
                s.add(row)
            if extend and row.active and row.expires_at is None:
                raise DomainError('Lifetime access does not need extending.')
            base = max(row.expires_at or now(), now()) if extend else now()
            row.plan, row.active = plan, not revoke
            row.expires_at = base + timedelta(days=days) if days else None
            audit(s, actor, 'premium.revoke' if revoke else 'premium.grant', user_id, plan=plan, days=days)
            return row

    def has_premium(self, guild_id, user_id):
        with self.db.sessions() as s:
            row = s.scalar(select(Premium).where(Premium.guild_id == guild_id, Premium.user_id == user_id))
            return bool(row and row.active and (row.expires_at is None or row.expires_at > now()))

    def restrict(self, actor, user_id, reason, active=True):
        actor.require(self.config(actor.guild_id))
        if not reason.strip() or len(reason) > 500:
            raise DomainError('A reason of 1–500 characters is required.')
        with self.db.transaction() as s:
            row = s.scalar(select(Restriction).where(Restriction.guild_id == actor.guild_id, Restriction.user_id == user_id))
            if not row:
                row = Restriction(guild_id=actor.guild_id, user_id=user_id)
                s.add(row)
            row.reason, row.active = reason, active
            audit(s, actor, 'freebie.restriction', user_id, active=active, reason=reason)
