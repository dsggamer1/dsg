"""Bundled help artwork; no external image host or image library is needed at runtime."""
import logging
from pathlib import Path
import discord

HELP_ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'help'
HELP_FILES = {'Home': 'home.gif', 'Utility': 'utility.gif', 'Commerce': 'commerce.gif', 'Community': 'community.gif', 'Moderation': 'moderation.gif'}


def help_file(section):
    try:
        path = HELP_ROOT / HELP_FILES[section]
        if path.resolve().parent != HELP_ROOT.resolve() or not 0 < path.stat().st_size <= 4 * 1024 * 1024:
            raise ValueError('Invalid help image.')
        data = path.read_bytes()
        if not data.startswith((b'GIF87a', b'GIF89a')):
            raise ValueError('Invalid help image.')
        return discord.File(path, filename='nex_help.gif')
    except (OSError, KeyError, ValueError):
        logging.getLogger('nex').warning('help.artwork.unavailable Use the complete project ZIP to restore help images.')
        return None


def can_attach(ctx):
    guild, channel = getattr(ctx, 'guild', None), getattr(ctx, 'channel', None)
    member = getattr(guild, 'me', None)
    return not (guild and channel and member) or channel.permissions_for(member).attach_files
