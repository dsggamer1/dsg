from datetime import timedelta
import discord
from discord.ext import commands
from ..models import Giveaway, now
from ..security import DomainError
from ..utils.discord import actor, respond
from ..utils.theme import themed_embed, emoji_for
from ..services.core import audit
from ..utils.cards import send_card


class GiveawayEntry(discord.ui.View):
    def __init__(self, config=None):
        super().__init__(timeout=None)
        self.enter.emoji = emoji_for('giveaway', config)

    @discord.ui.button(label='Enter giveaway', style=discord.ButtonStyle.primary, custom_id='nex:giveaway:enter')
    async def enter(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        try:
            from ..security import Actor
            giveaway_id = interaction.message.embeds[0].footer.text.split(' • ')[-1]
            interaction.client.community.enter(Actor(interaction.user.id, interaction.guild_id), giveaway_id)
            await interaction.followup.send(embed=themed_embed('success', 'You’re on the list', 'Your giveaway entry is saved. Good luck!', config=interaction.client.core.config(interaction.guild_id)), ephemeral=True)
        except (DomainError, IndexError):
            await interaction.followup.send('Entry unavailable: giveaway ended, entry already recorded, or invalid giveaway.', ephemeral=True)


class Community(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(GiveawayEntry())

    @commands.hybrid_command(help='Start a persistent giveaway (staff).')
    @commands.guild_only()
    async def giveaway(self, ctx, prize: str, minutes: int, winners: int = 1):
        a = actor(ctx)
        a.require(self.bot.core.config(ctx.guild.id))
        if not 1 <= minutes <= 43200 or not 1 <= winners <= 20 or not 1 <= len(prize) <= 200:
            raise DomainError('Use a prize up to 200 characters, 1–43200 minutes and 1–20 winners.')
        cfg=self.bot.core.config(ctx.guild.id)
        channel=ctx.guild.get_channel(cfg['giveaway_channel']) if cfg['giveaway_channel'] else ctx.channel
        if not channel:raise DomainError('Configured giveaway channel is missing; run /giveawaysetup.')
        with self.bot.db.transaction() as s:
            row = Giveaway(guild_id=ctx.guild.id, channel_id=channel.id, prize=prize, winner_count=winners, ends_at=now()+timedelta(minutes=minutes))
            s.add(row)
            s.flush()
            audit(s, a, 'giveaway.create', row.id)
        item = themed_embed('giveaway', 'Community giveaway', f'**{prize}**\n{winners} winner(s) • Ends <t:{int(row.ends_at.replace(tzinfo=__import__("datetime").timezone.utc).timestamp())}:R>\nClick below to enter.', config=self.bot.core.config(ctx.guild.id))
        item.set_footer(text=f'NEX CODEX • {row.id}')
        if channel.id==ctx.channel.id:
            await send_card(ctx.send,item,key='giveaway',channel=channel,view=GiveawayEntry(cfg))
        else:
            await send_card(channel.send,item,key='giveaway',channel=channel,view=GiveawayEntry(cfg))
            await respond(ctx,'Giveaway posted',channel.mention)

    @commands.hybrid_command(help='Reroll an ended giveaway (staff).')
    @commands.guild_only()
    async def reroll(self, ctx, giveaway_id: str):
        row = self.bot.community.draw(giveaway_id, actor(ctx))
        await respond(ctx, 'Giveaway rerolled', f'Winners recorded for `{row.id}`. Announcement will follow.')



async def setup(bot):
    await bot.add_cog(Community(bot))
