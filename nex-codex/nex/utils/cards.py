"""Bundled compact artwork shared by community and store messages."""
from contextlib import closing
from pathlib import Path
import discord

CARD_ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'cards'
CARD_KEYS = frozenset({'shop', 'product', 'ticket', 'payment', 'giveaway', 'welcome', 'leave', 'broadcast', 'settings', 'help'})


def card_file(item, key, channel=None):
    # Preserve configured shop images, payment QR codes and explicit attachments.
    if item.image.url or key not in CARD_KEYS:
        return None
    guild = getattr(channel, 'guild', None)
    if guild and getattr(guild, 'me', None) and hasattr(channel, 'permissions_for'):
        if not channel.permissions_for(guild.me).attach_files:
            return None
    path = CARD_ROOT / f'{key}.png'
    try:
        if path.resolve().parent != CARD_ROOT.resolve() or not 0 < path.stat().st_size <= 1024*1024:
            return None
        with path.open('rb') as stream:
            if stream.read(8) != b'\x89PNG\r\n\x1a\n':
                return None
        return discord.File(path, filename='nex_card.png')
    except OSError:
        return None


async def send_card(send, item, *, key, channel=None, **kwargs):
    file = None if 'file' in kwargs or 'files' in kwargs else card_file(item, key, channel)
    if file:
        with closing(file):
            item.set_image(url='attachment://nex_card.png')
            return await send(embed=item, file=file, **kwargs)
    return await send(embed=item, **kwargs)


async def edit_card(interaction, item, *, key, view):
    await interaction.response.defer()
    file = card_file(item, key, interaction.channel)
    if file:
        with closing(file):
            item.set_image(url='attachment://nex_card.png')
            return await interaction.edit_original_response(embed=item, view=view, attachments=[file])
    return await interaction.edit_original_response(embed=item, view=view, attachments=[])
