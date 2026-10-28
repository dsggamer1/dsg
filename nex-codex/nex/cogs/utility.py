from contextlib import closing
import json
import discord
from discord.ext import commands
from ..utils.discord import actor, respond, embed, owner_only, admin_or_owner
from ..utils.theme import themed_embed, emoji_for
from ..utils.help_media import help_file, can_attach
from ..utils.storefront import PersonalView
from ..security import DomainError
from ..services.core import audit

HELP_CATEGORIES = {'Utility': ('help', 'Welcome & announcements'), 'Commerce': ('shop', 'Shop & tickets'), 'Community': ('giveaway', 'Giveaways')}


def visible_commands(cog, owner, administrator=False):
    return sorted((c for c in cog.get_commands() if not c.hidden and (owner or not c.extras.get('owner_only')) and (owner or administrator or not c.extras.get('admin_only'))), key=lambda c:c.name)


def help_card(bot, owner, administrator, config, section='Home'):
    if section != 'Home':
        cog = bot.get_cog(section)
        key, title = HELP_CATEGORIES[section]
        item = themed_embed(key, title, 'Use slash commands or your server prefix. <Brackets> are required; [brackets] are optional. Staff commands enforce permissions.', config=config)
        for command in visible_commands(cog, owner, administrator):
            access = ' · Owner' if command.extras.get('owner_only') else ' · Admin' if command.extras.get('admin_only') else ''
            item.add_field(name=f'/{command.qualified_name}{access}', value=f'{command.help}\n`{command.name} {command.signature}`'[:1024], inline=False)
        return item
    item = themed_embed('help', 'NEX CODEX • Command center', 'Your community, connected. Choose a category below for the commands and their usage.', config=config)
    for name, (key, title) in HELP_CATEGORIES.items():
        cog = bot.get_cog(name)
        commands_here = visible_commands(cog, owner, administrator) if cog else []
        if commands_here:
            item.add_field(name=f'{emoji_for(key,config)} {title}', value=' · '.join(f'`/{c.name}`' for c in commands_here), inline=False)
    if owner:
        item.add_field(name='Owner workspace', value='/setup · /welcome · /leave · /addproduct · /createshop · /configure', inline=False)
    item.set_footer(text='NEX CODEX • Choose a category or use the buttons • Personal menu · 3 minutes')
    return item


class HelpView(PersonalView):
    def __init__(self, user_id, config=None):
        super().__init__(user_id)
        self.current_section = 'Home'
        self.message = None
        self.previous.emoji = emoji_for('previous', config)
        self.home.emoji = emoji_for('help', config)
        self.next_page.emoji = emoji_for('next', config)

    def update_navigation(self, section, options):
        self.current_section = section
        self.previous.disabled = section == options[0].value
        self.home.disabled = section == 'Home'
        self.next_page.disabled = section == options[-1].value

    async def navigate(self, interaction, step):
        menu = next(child for child in self.children if isinstance(child, HelpSelect))
        sections = [option.value for option in menu.options]
        index = 0 if step is None else max(0, min(len(sections)-1, sections.index(self.current_section)+step))
        await menu.show_page(interaction, sections[index])

    @discord.ui.button(label='Previous', style=discord.ButtonStyle.secondary, row=1, disabled=True)
    async def previous(self, interaction, button):
        await self.navigate(interaction, -1)

    @discord.ui.button(label='Home', style=discord.ButtonStyle.primary, row=1, disabled=True)
    async def home(self, interaction, button):
        await self.navigate(interaction, None)

    @discord.ui.button(label='Next', style=discord.ButtonStyle.secondary, row=1)
    async def next_page(self, interaction, button):
        await self.navigate(interaction, 1)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass  # The original message may have been deleted or become inaccessible.

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('Run /help to open your own command center.', ephemeral=True)
            return False
        return True

    async def on_error(self, interaction, error, item):
        import logging
        logging.getLogger('nex').warning('help.menu.failed type=%s', type(error).__name__)
        send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        await send('The help menu could not update. Run /help to open it again.', ephemeral=True)


class HelpSelect(discord.ui.Select):
    def __init__(self, bot, owner=False, config=None, administrator=False, media_enabled=True):
        self.bot, self.owner, self.config, self.administrator = bot, owner, config, administrator
        self.media_enabled = media_enabled
        options = [discord.SelectOption(label='Home', value='Home', emoji=emoji_for('help', config), description='Your NEX CODEX command center')]
        options.extend(discord.SelectOption(label=HELP_CATEGORIES[name][1], value=name, emoji=emoji_for(HELP_CATEGORIES[name][0], config)) for name in HELP_CATEGORIES if bot.get_cog(name) and visible_commands(bot.get_cog(name), owner, administrator))
        options[0].default = True
        super().__init__(placeholder='Explore NEX CODEX', options=options, row=0)

    async def callback(self, interaction):
        await self.show_page(interaction, self.values[0])

    async def show_page(self, interaction, section):
        item = help_card(self.bot, self.owner, self.administrator, self.config, section)
        for option in self.options:
            option.default = option.value == section
        if isinstance(self.view, HelpView):
            self.view.update_navigation(section, self.options)
        # Acknowledge before uploading category artwork, including on slower hosts.
        await interaction.response.defer()
        file = help_file(section) if self.media_enabled else None
        if file:
            with closing(file):
                item.set_image(url='attachment://nex_help.gif')
                await interaction.edit_original_response(embed=item, view=self.view, attachments=[file])
        else:
            await interaction.edit_original_response(embed=item, view=self.view, attachments=[])


class Utility(commands.Cog):
    """Focused community controls and owner configuration."""
    def __init__(self, bot):
        self.bot = bot
        from ..services.emojis import EmojiInstaller
        self.emoji_installer = EmojiInstaller(bot.core)

    @commands.hybrid_command(help='Browse the actual shop, ticket, giveaway and announcement commands.')
    async def help(self, ctx):
        owner = ctx.author.id in self.bot.config.owner_ids
        administrator = bool(ctx.guild and getattr(getattr(ctx.author, 'guild_permissions', None), 'administrator', False))
        cfg = self.bot.core.config(ctx.guild.id) if ctx.guild else None
        media_enabled = can_attach(ctx)
        view = HelpView(ctx.author.id, cfg)
        menu = HelpSelect(self.bot, owner, cfg, administrator, media_enabled)
        view.add_item(menu)
        view.update_navigation('Home', menu.options)
        item = help_card(self.bot, owner, administrator, cfg)
        file = help_file('Home') if media_enabled else None
        if file:
            with closing(file):
                item.set_image(url='attachment://nex_help.gif')
                view.message = await ctx.send(embed=item, view=view, file=file, ephemeral=True)
        else:
            view.message = await ctx.send(embed=item, view=view, ephemeral=True)

    async def membership_message(self, ctx, kind, channel, message, enabled):
        a = actor(ctx)
        a.require_admin()
        if not enabled:
            self.bot.core.configure(a, {kind+'_channel': None})
            await respond(ctx, 'Message disabled', f'{kind.title()} messages are disabled for this server.')
            return
        if channel is not None:
            if channel.guild.id != ctx.guild.id:
                raise DomainError('Choose a channel in this server.')
            changes = {kind+'_channel': channel.id}
            if message:
                changes[kind+'_message'] = message
            self.bot.core.configure(a, changes)
        elif message:
            self.bot.core.configure(a, {kind+'_message': message})
        cfg = self.bot.core.config(ctx.guild.id)
        text = self.bot.get_cog('Events').render(cfg[kind+'_message'], ctx.author)
        item = themed_embed(kind, f'{kind.title()} message • Preview', text, config=cfg)
        destination = cfg[kind+'_channel']
        item.add_field(name='Destination', value=f'<#{destination}>' if destination else f'Not configured. Use /{kind} with a channel.')
        await ctx.send(embed=item, ephemeral=True)

    @commands.hybrid_command(extras={'admin_only': True}, help='Set or preview the welcome message; enabled:false disables it (owner or administrator).')
    @admin_or_owner()
    @commands.guild_only()
    async def welcome(self, ctx, channel: discord.TextChannel = None, enabled: bool = True, *, message: str = ''):
        await self.membership_message(ctx, 'welcome', channel, message, enabled)

    @commands.hybrid_command(extras={'admin_only': True}, help='Set or preview the leave message; enabled:false disables it (owner or administrator).')
    @admin_or_owner()
    @commands.guild_only()
    async def leave(self, ctx, channel: discord.TextChannel = None, enabled: bool = True, *, message: str = ''):
        await self.membership_message(ctx, 'leave', channel, message, enabled)

    async def announce(self, ctx, channel, message, title=None):
        a = actor(ctx)
        a.require(self.bot.core.config(ctx.guild.id))
        channel = channel or ctx.channel
        if channel.guild.id != ctx.guild.id:
            raise DomainError('Choose a channel in this server.')
        if not a.owner:
            permissions = channel.permissions_for(ctx.author)
            if not permissions.view_channel or not permissions.send_messages:
                raise DomainError('You must be able to view and send messages in that channel.')
        if not message.strip() or len(message) > (3500 if title is not None else 2000):
            raise DomainError('Use a nonempty message up to 2000 characters for say or 3500 for broadcast.')
        self.bot.limiter.check(('announcement', ctx.guild.id, ctx.author.id), 3, 60)
        if title is not None:
            if not title.strip() or len(title)>120:
                raise DomainError('Use a title of 1–120 characters.')
            sent = await channel.send(embed=themed_embed('broadcast', title, message, config=self.bot.core.config(ctx.guild.id)), allowed_mentions=discord.AllowedMentions.none())
        else:
            sent = await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
        with self.bot.db.transaction() as session:
            audit(session, a, 'broadcast.send' if title is not None else 'say.send', sent.id, channel_id=channel.id)
        await ctx.send(embed=themed_embed('broadcast' if title is not None else 'say', 'Message published', f'Sent to {channel.mention}. Mentions are disabled.', config=self.bot.core.config(ctx.guild.id)), ephemeral=True)

    @commands.hybrid_command(help='Send a plain message through the bot in a channel (staff).')
    @commands.guild_only()
    async def say(self, ctx, message: str, channel: discord.TextChannel = None):
        await self.announce(ctx, channel, message)

    @commands.hybrid_command(help='Publish a branded announcement embed in a channel (staff).')
    @commands.guild_only()
    async def broadcast(self, ctx, title: str, message: str, channel: discord.TextChannel = None):
        await self.announce(ctx, channel, message, title)

    @commands.hybrid_command(extras={'admin_only': True}, name='prefix', help='Change the server text-command prefix (owner or administrator).')
    @admin_or_owner()
    @commands.guild_only()
    async def set_prefix(self, ctx, prefix: str):
        self.bot.core.configure(actor(ctx), {'prefix':prefix})
        await respond(ctx, 'Prefix updated', f'New prefix: `{prefix}`')

    @commands.hybrid_command(extras={'admin_only': True}, help='Update a validated configuration field using JSON (owner or administrator).')
    @admin_or_owner()
    @commands.guild_only()
    async def configure(self, ctx, key: str, *, value: str):
        try:
            data = json.loads(value)
        except ValueError:
            raise DomainError('Use JSON: true, 123, [123], "text", or an object for emojis.')
        self.bot.core.configure(actor(ctx), {key:data})
        await respond(ctx, 'Configuration saved', f'Updated `{key}`.')

    @commands.hybrid_command(extras={'admin_only': True}, help='Show the focused community and shop setup checklist (owner or administrator).')
    @admin_or_owner()
    @commands.guild_only()
    async def setup(self, ctx):
        item = themed_embed('settings', 'NEX CODEX • Server setup', 'Configured bot owners and server administrators can set up this server. Products and shop panels remain restricted to OWNER_IDS.', config=self.bot.core.config(ctx.guild.id))
        item.add_field(name='01 · Welcome & leave', value='Use /welcome and /leave with a channel and template. Templates: {user}, {name}, {server}.', inline=False)
        item.add_field(name='02 · Private support', value='Use /configure to set staff_roles, payment_roles, ticket_category and log_channel. Role lists use JSON arrays of numeric IDs.', inline=False)
        item.add_field(name='03 · Your collection', value='Create drafts with /addproduct, review terms with /productedit, then /productpublish. /createshop posts a permanent browse button.', inline=False)
        item.add_field(name='04 · Manual payments', value='Configure upi_id, qr_url, payee and currency. Reviewers independently verify transactions; screenshots never auto-approve.', inline=False)
        item.add_field(name='05 · Brand details', value='The bundled cyan emojis load automatically at startup. /installemojis optionally overrides them with server emojis. Configure shop_title, shop_description, shop_image and emojis. Emoji slots include welcome, leave, ticket, giveaway, broadcast, product, shop and help.', inline=False)
        await ctx.send(embed=item, ephemeral=True)

    @commands.hybrid_command(extras={'admin_only': True}, help='Check local command setup and channel permissions (owner or administrator).')
    @admin_or_owner()
    @commands.guild_only()
    async def diagnostics(self, ctx):
        from ..bot import prefix
        prefixes = await prefix(self.bot, ctx.message)
        perms = ctx.channel.permissions_for(ctx.guild.me)
        missing = [name.replace('_',' ') for name in ('view_channel','send_messages','embed_links','attach_files','read_message_history') if not getattr(perms,name)]
        item = themed_embed('settings', 'NEX CODEX • Connection check', 'Remote intents and command visibility must also be checked in Discord Developer Portal.', config=self.bot.core.config(ctx.guild.id))
        item.add_field(name='Commands loaded', value=str(len(self.bot.tree.get_commands())))
        item.add_field(name='Text prefix', value=f'`{prefixes[-1]}`')
        item.add_field(name='This channel', value=', '.join(missing) if missing else 'Core permissions available', inline=False)
        item.add_field(name='Registration', value='Invite with bot + applications.commands; SYNC_COMMANDS=true. Optional COMMAND_GUILD_IDS provides direct guild sync.', inline=False)
        await ctx.send(embed=item, ephemeral=True)

    @commands.hybrid_command(extras={'admin_only': True}, help='Install the supplied cyan emoji theme in this server (owner or administrator).')
    @admin_or_owner()
    @commands.guild_only()
    async def installemojis(self, ctx):
        a = actor(ctx)
        a.require_admin()
        self.bot.limiter.check(('emoji-install', ctx.guild.id), 1, 60)
        result = await self.emoji_installer.install(a, ctx.guild)
        detail = f"Created: {result['created']} · Reused: {result['reused']} · Theme slots mapped: {result['mapped']}/14."
        if result['failure']:
            detail += '\n' + result['failure'] + ' Successful mappings were saved.'
        else:
            detail += '\nTheme saved. Repost existing shop panels to refresh their buttons.'
        await ctx.send(embed=themed_embed('settings', 'Emoji setup • ' + ('Partial' if result['failure'] else 'Complete'), detail, config=self.bot.core.config(ctx.guild.id)), ephemeral=True)

    @commands.command(hidden=True)
    @owner_only()
    async def sync(self, ctx):
        registered = await self.bot.publish_commands()
        await respond(ctx, 'Commands synchronized', f'{len(registered)} slash commands registered.')


async def setup(bot):
    await bot.add_cog(Utility(bot))
