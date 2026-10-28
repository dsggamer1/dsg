"""Shared emoji slots for Discord embeds and components; with automatic application artwork and per-server overrides."""
import re
from .discord import embed

DEFAULT_EMOJIS = {
    'welcome': '👋', 'leave': '◇', 'ticket': '🎫', 'giveaway': '🎉',
    'say': '💬', 'broadcast': '📣', 'product': '◇', 'shop': '🛍️',
    'help': '✦', 'settings': '⚙️', 'success': '✓', 'error': '⚠️',
    'previous': '◀️', 'next': '▶️',
}


_APPLICATION_EMOJIS = {}


def set_application_emojis(mapping):
    """Use IDs fetched/created by the authenticated bot; server overrides take priority."""
    validate_emojis(mapping)
    _APPLICATION_EMOJIS.clear()
    _APPLICATION_EMOJIS.update(mapping)


def validate_emojis(values):
    for key, value in values.items():
        if key not in DEFAULT_EMOJIS:
            raise ValueError('Unknown emoji slot: ' + key)
        custom = re.fullmatch(r'<a?:[A-Za-z0-9_]{2,32}:([0-9]{15,20})>', value)
        if custom and 0 < int(custom[1]) < 2**63:
            continue
        symbol = lambda c: 0x2190 <= ord(c) <= 0x2BFF or 0x1F000 <= ord(c) <= 0x1FAFF
        if not 1 <= len(value) <= 16 or not any(symbol(c) for c in value) or any(not symbol(c) and c not in '\u200d\ufe0e\ufe0f\u20e3' and not c.isdecimal() for c in value):
            raise ValueError('Use a Unicode emoji or a Discord custom emoji code.')
    return values


def emoji_for(key, config=None):
    return (config or {}).get('emojis', {}).get(key, _APPLICATION_EMOJIS.get(key, DEFAULT_EMOJIS[key]))


def themed_embed(key, title, description='', *, config=None, error=False):
    return embed(f'{emoji_for(key, config)} {title}', description, error=error)
