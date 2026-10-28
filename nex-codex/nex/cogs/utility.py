import json
import discord
from discord.ext import commands
from ..utils.discord import actor, respond, embed, safe_role
from ..security import DomainError
from ..services.providers import AIProvider


class HelpSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(placeholder='Choose a command category', options=[discord.SelectOption(label=name, value=name) for name in bot.cogs if bot.get_cog(name).get_commands()])

    async def callback(self, interaction):
        cog = self.bot.get_cog(self.values[0])
        lines = [f'**/{c.qualified_name}** — {c.help or "Server utility"}' for c in cog.get_commands() if not c.hidden]
        await interaction.response.edit_message(embed=embed(f'{cog.qualified_name} commands', '\n'.join(lines)), view=self.view)


class RoleSelect(discord.ui.Select):
    def __init__(self, roles):
        super().__init__(placeholder='Choose a role to toggle', custom_id='nex:self_roles', options=[discord.SelectOption(label=r.name[:100], value=str(r.id)) for r in roles])

    async def callback(self, interaction):
        bot = interaction.client
        cfg = bot.core.config(interaction.guild_id)
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        try:
            if role_id not in cfg['self_roles'] or not role:
                raise DomainError('This role is no longer available.')
            safe_role(interaction.guild, None, role)
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason='Self-service role')
            else:
                await interaction.user.add_roles(role, reason='Self-service role')
            await interaction.response.send_message('Your role selection has been updated.', ephemeral=True)
        except (DomainError, discord.HTTPException) as exc:
            await interaction.response.send_message(str(exc) if isinstance(exc, DomainError) else 'Unable to update roles. Check bot permissions.', ephemeral=True)


class Utility(commands.Cog):
    """Server tools and configuration."""
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(help='Browse actual registered commands by category.')
    async def help(self, ctx):
        view = discord.ui.View(timeout=180)
        view.add_item(HelpSelect(self.bot))
        await respond(ctx, 'NEX CODEX command center', 'Choose a category below. Commands support slash and configured text prefixes. Sensitive commands check permissions on the server.', view=view)

    @commands.hybrid_command(help='Check gateway latency.')
    async def ping(self, ctx):
        await respond(ctx, 'Connection healthy', f'Gateway latency: **{self.bot.latency * 1000:.0f} ms**')

    @commands.hybrid_command(help='Bot version and service information.')
    async def about(self, ctx):
        await respond(ctx, 'NEX CODEX', f'Modular community management and marketplace.\nVersion **1.0.0** • {len(self.bot.guilds)} servers\nDashboard: {self.bot.config.public_url}\nPayments are reviewed manually by server staff.')

    @commands.hybrid_command(help='Show server information.')
    @commands.guild_only()
    async def serverinfo(self, ctx):
        await respond(ctx, ctx.guild.name, f'Members: **{ctx.guild.member_count}**\nChannels: **{len(ctx.guild.channels)}**\nCreated: {discord.utils.format_dt(ctx.guild.created_at)}')

    @commands.hybrid_command(help='Show member information.')
    @commands.guild_only()
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        await respond(ctx, str(member), f'ID: `{member.id}`\nCreated: {discord.utils.format_dt(member.created_at)}\nJoined: {discord.utils.format_dt(member.joined_at) if member.joined_at else "Unknown"}')

    @commands.hybrid_command(help='View a member avatar.')
    async def avatar(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        item = embed(str(member))
        item.set_image(url=member.display_avatar.url)
        await ctx.send(embed=item)

    @commands.hybrid_command(help='Inspect a role.')
    @commands.guild_only()
    async def roleinfo(self, ctx, role: discord.Role):
        await respond(ctx, role.name, f'ID: `{role.id}`\nMembers: {len(role.members)}\nPosition: {role.position}\nManaged: {role.managed}')

    @commands.hybrid_command(help='Inspect a channel.')
    @commands.guild_only()
    async def channelinfo(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        await respond(ctx, channel.name, f'ID: `{channel.id}`\nCreated: {discord.utils.format_dt(channel.created_at)}')

    @commands.hybrid_command(name='prefix', help='Set the server text-command prefix.')
    @commands.guild_only()
    async def set_prefix(self, ctx, prefix: str):
        self.bot.core.configure(actor(ctx), {'prefix': prefix})
        await respond(ctx, 'Prefix updated', f'New prefix: `{prefix}`')

    @commands.hybrid_command(help='Set a configuration field using a JSON value.')
    @commands.guild_only()
    async def configure(self, ctx, key: str, value: str):
        try:
            data = json.loads(value)
        except ValueError:
            raise DomainError('Value must be valid JSON, for example true, 123, [123], or "text".')
        self.bot.core.configure(actor(ctx), {key: data})
        await respond(ctx, 'Configuration saved', f'Updated `{key}`.')

    @commands.hybrid_command(help='Assign or remove a safe role below your role.')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def role(self, ctx, member: discord.Member, role: discord.Role, remove: bool = False):
        safe_role(ctx.guild, ctx.author, role)
        await (member.remove_roles(role, reason=f'NEX role utility by {ctx.author.id}') if remove else member.add_roles(role, reason=f'NEX role utility by {ctx.author.id}'))
        await respond(ctx, 'Role updated', f'{role.name} {"removed from" if remove else "assigned to"} {member.display_name}.')

    @commands.hybrid_command(help='Choose from configured self-service roles.')
    @commands.guild_only()
    async def roles(self, ctx):
        configured = self.bot.core.config(ctx.guild.id)['self_roles']
        roles = [r for r in ctx.guild.roles if r.id in configured]
        if not roles:
            raise DomainError('No self-service roles configured.')
        view = discord.ui.View(timeout=180)
        view.add_item(RoleSelect(roles))
        await respond(ctx, 'Your server roles', 'Select a role to add or remove it.', view=view)

    @commands.hybrid_command(help='Create a native Discord poll; answers separated with |.')
    @commands.has_guild_permissions(manage_messages=True)
    async def poll(self, ctx, question: str, answers: str, hours: int = 24):
        from datetime import timedelta
        choices = [a.strip() for a in answers.split('|')]
        if not 2 <= len(choices) <= 10 or any(not a or len(a) > 55 for a in choices) or not 1 <= hours <= 168 or len(question) > 300:
            raise DomainError('Use 2–10 answers of up to 55 characters, a question up to 300 characters, and 1–168 hours.')
        poll = discord.Poll(question=question, duration=timedelta(hours=hours))
        for answer in choices:
            poll.add_answer(text=answer)
        await ctx.send(poll=poll)

    @commands.hybrid_command(help='Ask the configured AI provider; your prompt is sent to that provider.')
    @commands.cooldown(3, 60, commands.BucketType.user)
    @commands.guild_only()
    async def ask(self, ctx, *, prompt: str):
        if not self.bot.core.config(ctx.guild.id)['ai_enabled']:
            raise DomainError('AI is disabled in this server.')
        await ctx.defer(ephemeral=True)
        await respond(ctx, 'AI response', await AIProvider(self.bot.config).ask(prompt))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def sync(self, ctx):
        commands_synced = await self.bot.tree.sync()
        await respond(ctx, 'Commands synchronized', f'{len(commands_synced)} slash commands registered.')


async def setup(bot):
    await bot.add_cog(Utility(bot))
