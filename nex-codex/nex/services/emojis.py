"""Install supplied artwork using real guild emoji responses, never invented IDs."""
import asyncio
from pathlib import Path
import discord
from ..security import DomainError
from .core import audit

ASSET_ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'emojis'
EMOJI_ASSETS = {
    'welcome': 'welcome', 'leave': 'leave', 'ticket': 'ticket',
    'giveaway': 'gift', 'say': 'support', 'broadcast': 'bell',
    'product': 'product', 'shop': 'cart', 'help': 'info',
    'settings': 'settings', 'success': 'success', 'error': 'error',
    'previous': 'previous', 'next': 'next',
}


class EmojiInstaller:
    def __init__(self, core):
        self.core = core
        self._locks = {}

    async def install(self, actor, guild):
        actor.require_admin()
        if guild.id != actor.guild_id:
            raise DomainError('Choose the current server.')
        permissions = guild.me.guild_permissions if guild.me else None
        if not permissions or not (permissions.manage_expressions or permissions.create_expressions):
            raise DomainError('Give the bot Create Expressions or Manage Expressions permission, then retry.')
        # Keep one operation per guild in flight. Re-fetch before each batch so retries
        # reuse successful uploads after a partial failure or a process restart.
        lock = self._locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            existing = await guild.fetch_emojis()
            usable = {e.name: e for e in existing if not e.animated and not e.roles and e.available}
            count = sum(not e.animated for e in existing)
            mapping = {}
            created = reused = 0
            failure = None
            for slot, asset in EMOJI_ASSETS.items():
                name = 'nex_' + asset
                emoji = usable.get(name)
                if emoji is None:
                    if count >= guild.emoji_limit:
                        failure = 'The server has no free static emoji slots.'
                        break
                    path = ASSET_ROOT / (name + '.png')
                    try:
                        data = path.read_bytes()
                        if len(data) > 256 * 1024 or not data.startswith(b'\x89PNG\r\n\x1a\n'):
                            raise ValueError('Invalid bundled emoji image.')
                        emoji = await guild.create_custom_emoji(name=name, image=data, reason=f'NEX CODEX setup by {actor.user_id}')
                    except (OSError, ValueError, discord.HTTPException):
                        failure = 'Discord could not upload the next emoji. Check permissions, slots and rate limits, then retry.'
                        break
                    created += 1
                    count += 1
                    usable[name] = emoji
                else:
                    reused += 1
                mapping[slot] = str(emoji)
            if mapping:
                self.core.configure(actor, {'emojis': self.core.config(guild.id)['emojis'] | mapping})
            with self.core.db.transaction() as session:
                audit(session, actor, 'emojis.install', guild.id, created=created, reused=reused, complete=not failure)
            return {'created': created, 'reused': reused, 'mapped': len(mapping), 'failure': failure}
