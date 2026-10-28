import discord
from discord.ext import commands
from ..security import Actor, DomainError

CYAN = 0x38CFEF


def embed(title, description='', *, error=False):
    result = discord.Embed(title=title[:256], description=description[:4096], color=0xF87171 if error else CYAN, timestamp=discord.utils.utcnow())
    result.set_footer(text='NEX CODEX • Your community, connected')
    return result


def actor(ctx):
    if not ctx.guild or not isinstance(ctx.author, discord.Member):
        raise DomainError('Use this command in a server.')
    return Actor(ctx.author.id, ctx.guild.id, frozenset(r.id for r in ctx.author.roles), ctx.author.guild_permissions.administrator, ctx.author.id in ctx.bot.config.owner_ids)


async def respond(ctx, title, text='', **kwargs):
    return await ctx.send(embed=embed(title, text), ephemeral=True, **kwargs)


class Confirm(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=45)
        self.user_id, self.confirmed = user_id, False

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('This confirmation belongs to someone else.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        self.confirmed = True
        await interaction.response.edit_message(content='Confirmed.', view=None)
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(content='Cancelled.', view=None)
        self.stop()


async def confirm(ctx, title):
    view = Confirm(ctx.author.id)
    message = await ctx.send(embed=embed('Confirm action', title), view=view, ephemeral=True)
    await view.wait()
    if not view.confirmed:
        try:
            await message.edit(view=None)
        except discord.HTTPException:
            pass
    return view.confirmed


def safe_role(guild, member, role, protected_roles=()):
    if role.id in protected_roles:
        raise DomainError('Staff and payment-review roles cannot be assigned with this utility.')
    if role.is_default() or role.managed or role >= guild.me.top_role:
        raise DomainError('This role cannot be assigned by the bot.')
    permissions = role.permissions
    if any(getattr(permissions, p) for p in ('administrator', 'manage_guild', 'manage_roles', 'manage_channels', 'ban_members', 'kick_members', 'moderate_members', 'manage_webhooks', 'manage_messages', 'mention_everyone', 'manage_threads', 'manage_events', 'manage_expressions', 'view_audit_log')):
        raise DomainError('Privileged roles cannot be assigned through this utility.')
    if member and member.id != guild.owner_id and role >= member.top_role:
        raise DomainError('Choose a role below your highest role.')


def price_minor(value):
    from decimal import Decimal, InvalidOperation
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0 or amount > 1000000 or amount * 100 != (amount * 100).to_integral_value():
            raise ValueError
        return int(amount * 100)
    except (InvalidOperation, ValueError, TypeError):
        raise DomainError('Use a price from 0 to 1000000 with at most two decimal places, for example 499.00.') from None
