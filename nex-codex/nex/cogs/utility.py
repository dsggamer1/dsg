from contextlib import closing
from typing import Literal
import json
import discord
from discord.ext import commands
from ..utils.discord import actor, respond, embed, owner_only, admin_or_owner
from ..utils.theme import themed_embed, emoji_for
from ..utils.help_media import help_file, can_attach
from ..utils.storefront import PersonalView
from ..utils.cards import send_card
from ..utils.guides import GuideView, guide_card
from ..utils.storefront import ShopView
from ..security import DomainError
from ..services.core import audit

HELP_CATEGORIES = {'Utility': ('help', 'Welcome & announcements'), 'Commerce': ('shop', 'Shop & tickets'), 'Community': ('giveaway', 'Giveaways'), 'Moderation': ('settings', 'Moderation & roles')}


def visible_commands(cog, owner, administrator=False):
    return sorted((c for c in cog.get_commands() if not c.hidden and (owner or not c.extras.get('owner_only')) and (owner or administrator or not c.extras.get('admin_only'))), key=lambda c:c.name)


def help_card(bot, owner, administrator, config, section='Home'):
    if section != 'Home':
        cog = bot.get_cog(section)
        key, title = HELP_CATEGORIES[section]
        item = themed_embed(key, title, 'Use slash commands or your server prefix. <Brackets> are required; [brackets] are optional. Staff commands enforce permissions.', config=config)
        for command in visible_commands(cog, owner, administrator):
            access = ' · Owner' if command.extras.get('owner_only') else ' · Admin' if command.extras.get('admin_only') else ''
            item.add_field(name=f'/{command.qualified_name}{access}', value=f'{command.help}\n`{command.name} {command.signature}`'[:190], inline=False)
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


class HelpShortcut(discord.ui.Button):
    def __init__(self, destination, config=None):
        self.destination = destination
        super().__init__(label='Browse shop' if destination=='shop' else 'Setup guide', style=discord.ButtonStyle.secondary, emoji=emoji_for('shop' if destination=='shop' else 'settings',config), row=2)

    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        bot=interaction.client
        cfg=bot.core.config(interaction.guild_id)
        if self.destination=='shop':
            bot.limiter.check(('help_shop',interaction.guild_id,interaction.user.id),5,60)
            view=ShopView(interaction.user.id,bot,interaction.guild_id)
            await send_card(interaction.followup.send,view.card(),key='shop',channel=interaction.channel,view=view,ephemeral=True)
        else:
            permissions=interaction.user.guild_permissions
            if interaction.user.id not in bot.config.owner_ids and not permissions.administrator:
                raise DomainError('A configured bot owner or server Administrator is required.')
            await send_card(interaction.followup.send,guide_card('start',cfg),key='settings',channel=interaction.channel,view=GuideView(interaction.user.id,cfg),ephemeral=True)


class Utility(commands.Cog):
    """Focused community controls and owner configuration."""
    def __init__(self, bot):
        self.bot = bot
        from ..services.emojis import EmojiInstaller
        self.emoji_installer = EmojiInstaller(bot.core)

    @commands.hybrid_command(help='Browse the actual shop, ticket, giveaway and announcement commands.')
    async def help(self, ctx):
        await self.send_help(ctx.author, ctx.guild, getattr(ctx, 'channel', None), ctx.send)

    async def send_help(self, author, guild, channel, send):
        from types import SimpleNamespace
        owner = author.id in self.bot.config.owner_ids
        administrator = bool(guild and getattr(getattr(author, 'guild_permissions', None), 'administrator', False))
        cfg = self.bot.core.config(guild.id) if guild else None
        media_enabled = can_attach(SimpleNamespace(guild=guild, channel=channel))
        view = HelpView(author.id, cfg)
        menu = HelpSelect(self.bot, owner, cfg, administrator, media_enabled)
        view.add_item(menu)
        view.update_navigation('Home', menu.options)
        if guild:
            view.add_item(HelpShortcut('shop', cfg))
            if owner or administrator:
                view.add_item(HelpShortcut('setup', cfg))
        item = help_card(self.bot, owner, administrator, cfg)
        file = help_file('Home') if media_enabled else None
        if file:
            with closing(file):
                item.set_image(url='attachment://nex_help.gif')
                view.message = await send(embed=item, view=view, file=file, ephemeral=True)
        else:
            view.message = await send(embed=item, view=view, ephemeral=True)

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
        await send_card(ctx.send, item, key=kind, channel=getattr(ctx, 'channel', None), ephemeral=True)

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
            sent = await send_card(channel.send, themed_embed('broadcast', title, message, config=self.bot.core.config(ctx.guild.id)), key='broadcast', channel=channel, allowed_mentions=discord.AllowedMentions.none())
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
        actor(ctx).require_admin()
        cfg = self.bot.core.config(ctx.guild.id)
        await send_card(ctx.send, guide_card('start', cfg), key='settings', channel=ctx.channel, view=GuideView(ctx.author.id,cfg), ephemeral=True)


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

    @commands.hybrid_command(extras={'owner_only': True}, help='Set shop channel/branding and publish the persistent panel (owner).')
    @owner_only()
    @commands.guild_only()
    async def shopsetup(self,ctx,channel:discord.TextChannel,title:str='NEX CODEX • Shop',description:str='Explore templates and bots.',image:str=''):
        a=actor(ctx);a.require_owner()
        if channel.guild.id!=ctx.guild.id:raise DomainError('Choose a channel in this server.')
        self.bot.core.configure(a,{'shop_channel':channel.id,'shop_title':title,'shop_description':description,'shop_image':image})
        commerce=self.bot.get_cog('Commerce')
        await type(commerce).createshop.callback(commerce,ctx,channel)

    @commands.hybrid_command(extras={'admin_only': True}, help='Set the channel for welcome, leave, logs, giveaways or shop (shop requires owner).')
    @admin_or_owner()
    @commands.guild_only()
    async def channelsetup(self,ctx,kind:Literal['welcome','leave','logs','giveaway','shop'],channel:discord.TextChannel):
        a=actor(ctx);a.require_admin()
        if kind=='shop':a.require_owner()
        if channel.guild.id!=ctx.guild.id:raise DomainError('Choose a channel in this server.')
        key={'logs':'log_channel','giveaway':'giveaway_channel'}.get(kind,kind+'_channel')
        self.bot.core.configure(a,{key:channel.id})
        await respond(ctx,'Channel saved',f'**{kind.title()}** → {channel.mention}')

    @commands.hybrid_command(extras={'admin_only': True}, help='Configure welcome channel and message template.')
    @admin_or_owner()
    @commands.guild_only()
    async def welcomesetup(self,ctx,channel:discord.TextChannel,*,message:str='Welcome {user} to {server}!'):
        await self.membership_message(ctx,'welcome',channel,message,True)

    @commands.hybrid_command(extras={'admin_only': True}, help='Set leave message and optional kick-on-rejoin restriction; default disabled.')
    @admin_or_owner()
    @commands.guild_only()
    async def leavesetup(self,ctx,channel:discord.TextChannel=None,restrict_rejoin:bool=False,*,message:str=''):
        a=actor(ctx);a.require_admin()
        if restrict_rejoin and not ctx.guild.me.guild_permissions.kick_members:
            raise DomainError('Give the bot Kick Members permission before enabling rejoin restriction.')
        if channel and channel.guild.id!=ctx.guild.id:raise DomainError('Choose a channel in this server.')
        changes={'restrict_rejoin':restrict_rejoin}
        if channel:changes['leave_channel']=channel.id
        if message:changes['leave_message']=message
        self.bot.core.configure(a,changes)
        await respond(ctx,'Leave setup saved','Kick on rejoin: **'+('Enabled' if restrict_rejoin else 'Disabled')+'**. Only departures recorded while enabled are tracked. Owners/admins/configured staff/bots are exempt. Use /rejoinallow to remove a block.')

    @commands.hybrid_command(extras={'admin_only': True}, help='Remove a saved leave/rejoin restriction by Discord user ID.')
    @admin_or_owner()
    @commands.guild_only()
    async def rejoinallow(self,ctx,user_id:str):
        if not user_id.isdecimal() or not 0<int(user_id)<2**63:raise DomainError('Use a numeric Discord user ID.')
        from ..services.rejoin import clear
        clear(self.bot,actor(ctx),int(user_id))
        await respond(ctx,'Rejoin allowed',f'Removed the saved restriction for `{user_id}`.')

    @commands.hybrid_command(extras={'admin_only': True}, help='Configure private ticket category and staff role.')
    @admin_or_owner()
    @commands.guild_only()
    async def ticketsetup(self,ctx,category:discord.CategoryChannel,staff_role:discord.Role):
        a=actor(ctx);a.require_admin()
        if category.guild.id!=ctx.guild.id or staff_role.guild.id!=ctx.guild.id or staff_role.is_default():
            raise DomainError('Choose a category and a non-everyone staff role in this server.')
        cfg=self.bot.core.config(ctx.guild.id)
        self.bot.core.configure(a,{'ticket_category':category.id,'staff_roles':list(dict.fromkeys([*cfg['staff_roles'],staff_role.id]))})
        await respond(ctx,'Tickets configured','Support and purchase tickets will be private to customers and configured staff.')

    @commands.hybrid_command(extras={'admin_only': True}, help='Set the channel used for new giveaways.')
    @admin_or_owner()
    @commands.guild_only()
    async def giveawaysetup(self,ctx,channel:discord.TextChannel):
        if channel.guild.id!=ctx.guild.id:raise DomainError('Choose a channel in this server.')
        self.bot.core.configure(actor(ctx),{'giveaway_channel':channel.id})
        await respond(ctx,'Giveaway channel saved',f'New /giveaway events will be posted in {channel.mention}.')

    @commands.command(hidden=True)
    @owner_only()
    async def sync(self, ctx):
        registered = await self.bot.publish_commands()
        await respond(ctx, 'Commands synchronized', f'{len(registered)} slash commands registered.')


async def setup(bot):
    await bot.add_cog(Utility(bot))
