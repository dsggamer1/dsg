from sqlalchemy import select
from ..models import Guild, Audit, Restriction
from ..schemas import GuildConfig, LEGACY_CONFIG_KEYS
from ..security import DomainError


def config(session, guild_id):
    row = session.get(Guild, guild_id)
    saved = row.settings if row else {}
    return GuildConfig.model_validate({key: value for key, value in saved.items() if key not in LEGACY_CONFIG_KEYS}).model_dump()


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
            if actor.guild_id in value['staff_roles'] + value['payment_roles']:
                raise DomainError('The everyone role cannot be used for staff or payment review.')
            automatic_roles = {value['auto_role']}
            if automatic_roles.intersection(value['staff_roles'] + value['payment_roles']):
                raise DomainError('Staff and payment roles cannot be auto-role rewards.')
            row = s.get(Guild, actor.guild_id)
            if row:
                row.settings = value
            else:
                s.add(Guild(id=actor.guild_id, settings=value))
            audit(s, actor, 'configuration.update', fields=list(changes))
        return value

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
