from datetime import timedelta
import secrets
import discord
from discord.ext import commands
from sqlalchemy import select, func
from ..models import Level, Giveaway, Reminder, Reward, Heartbeat, now
from ..security import DomainError
from ..utils.discord import actor, respond, embed
from ..services.core import audit


class GiveawayEntry(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Enter giveaway', style=discord.ButtonStyle.primary, custom_id='nex:giveaway:enter')
    async def enter(self, interaction, button):
        try:
            from ..security import Actor
            giveaway_id = interaction.message.embeds[0].footer.text.split(' • ')[-1]
            interaction.client.community.enter(Actor(interaction.user.id, interaction.guild_id), giveaway_id)
            await interaction.response.send_message('Your entry is saved. Good luck!', ephemeral=True)
        except (DomainError, IndexError):
            await interaction.response.send_message('Entry unavailable: giveaway ended, entry already recorded, or invalid giveaway.', ephemeral=True)


class Community(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(GiveawayEntry())

    @commands.hybrid_command(help='Show the server XP leaderboard.')
    @commands.guild_only()
    async def leaderboard(self, ctx, page: int = 1):
        with self.bot.db.sessions() as s:
            rows = list(s.scalars(select(Level).where(Level.guild_id == ctx.guild.id).order_by(Level.xp.desc(), Level.user_id).offset((max(1, page)-1)*10).limit(10)))
        await respond(ctx, 'Community leaderboard', '\n'.join(f'**{(max(1,page)-1)*10+i+1}.** <@{r.user_id}> • Level {r.xp//100} • {r.xp} XP' for i, r in enumerate(rows)) or 'No XP recorded. Staff can enable leveling in settings.')

    @commands.hybrid_command(help='Start a persistent giveaway (staff).')
    @commands.guild_only()
    async def giveaway(self, ctx, prize: str, minutes: int, winners: int = 1):
        a = actor(ctx)
        a.require(self.bot.core.config(ctx.guild.id))
        if not 1 <= minutes <= 43200 or not 1 <= winners <= 20 or not 1 <= len(prize) <= 200:
            raise DomainError('Use a prize up to 200 characters, 1–43200 minutes and 1–20 winners.')
        with self.bot.db.transaction() as s:
            row = Giveaway(guild_id=ctx.guild.id, channel_id=ctx.channel.id, prize=prize, winner_count=winners, ends_at=now()+timedelta(minutes=minutes))
            s.add(row)
            s.flush()
            audit(s, a, 'giveaway.create', row.id)
        item = embed('Community giveaway', f'**{prize}**\n{winners} winner(s) • Ends <t:{int(row.ends_at.replace(tzinfo=__import__("datetime").timezone.utc).timestamp())}:R>\nClick below to enter.')
        item.set_footer(text=f'NEX CODEX • {row.id}')
        await ctx.send(embed=item, view=GiveawayEntry())

    @commands.hybrid_command(help='Reroll an ended giveaway (staff).')
    @commands.guild_only()
    async def reroll(self, ctx, giveaway_id: str):
        row = self.bot.community.draw(giveaway_id, actor(ctx))
        await respond(ctx, 'Giveaway rerolled', f'Winners recorded for `{row.id}`. Announcement will follow.')

    @commands.hybrid_command(help='Save a reminder that survives restarts.')
    @commands.cooldown(3, 60, commands.BucketType.user)
    async def remind(self, ctx, minutes: int, *, text: str):
        if not 1 <= minutes <= 525600 or not 1 <= len(text) <= 500:
            raise DomainError('Use 1–525600 minutes and 1–500 characters.')
        with self.bot.db.transaction() as s:
            count = s.scalar(select(func.count()).select_from(Reminder).where(Reminder.user_id == ctx.author.id, Reminder.sent.is_(False)))
            if count >= 20:
                raise DomainError('You already have 20 pending reminders.')
            s.add(Reminder(user_id=ctx.author.id, text=text, due_at=now()+timedelta(minutes=minutes)))
        await respond(ctx, 'Reminder saved', 'I will send you a DM. Allow direct messages from this server.')

    @commands.hybrid_command(help='Roll a die with 2–1000 sides.')
    async def roll(self, ctx, sides: int = 6):
        if not 2 <= sides <= 1000:
            raise DomainError('Choose 2–1000 sides.')
        await respond(ctx, 'Dice roll', f'You rolled **{secrets.randbelow(sides)+1}** on a {sides}-sided die.')

    @commands.hybrid_command(help='Redeem a referral from a current server member after your first claim or purchase.')
    @commands.guild_only()
    @commands.cooldown(2, 60, commands.BucketType.user)
    async def referral(self, ctx, referrer: discord.Member):
        if referrer.bot:
            raise DomainError('Bots cannot receive referral rewards.')
        self.bot.community.refer(actor(ctx), referrer.id)
        await respond(ctx, 'Referral recorded', 'The configured points were credited once to your referrer.')

    @commands.hybrid_command(help='Show your reward balance and latest transactions.')
    @commands.guild_only()
    async def rewards(self, ctx):
        with self.bot.db.sessions() as s:
            rows = list(s.scalars(select(Reward).where(Reward.guild_id == ctx.guild.id, Reward.user_id == ctx.author.id).order_by(Reward.id.desc()).limit(10)))
            balance = s.scalar(select(func.sum(Reward.points)).where(Reward.guild_id == ctx.guild.id, Reward.user_id == ctx.author.id)) or 0
        await respond(ctx, 'Your rewards', f'Balance: **{balance} points**\n' + '\n'.join(f'{r.created_at:%Y-%m-%d} • +{r.points} • referral' for r in rows))


async def setup(bot):
    await bot.add_cog(Community(bot))
