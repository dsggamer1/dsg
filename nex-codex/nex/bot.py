import asyncio
import logging
import json
import discord
from discord.ext import commands
from pydantic import ValidationError
from .config import settings
from .db import Database
from .services.core import Core
from .services.marketplace import Marketplace
from .services.tickets import Tickets
from .services.community import Community
from .services.emojis import ApplicationEmojiLoader
from .security import DomainError, RateLimiter
from .utils.discord import embed
from .utils.theme import themed_embed
from .models import Guild



class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Only controlled event messages are logged; exception payloads may contain tokens/URLs.
        return json.dumps({'level': record.levelname, 'logger': record.name, 'event': record.getMessage()})


async def prefix(bot, message):
    value = bot.config.default_prefix
    if message.guild:
        with bot.db.sessions() as session:
            row = session.get(Guild, message.guild.id)
            if row and 'prefix' in row.settings:
                value = row.settings['prefix']
    return commands.when_mentioned_or(value)(bot, message)


class NexBot(commands.Bot):
    def __init__(self, cfg=None, db=None):
        self.config = cfg or settings()
        self.db = db or Database(self.config.database_url)
        self.core = Core(self.db)
        self.market = Marketplace(self.db, self.config.product_root)
        self.tickets = Tickets(self.db)
        self.community = Community(self.db)
        self.limiter = RateLimiter()
        self.ticket_locks = {}
        intents = discord.Intents.default()
        intents.members = intents.message_content = True
        super().__init__(command_prefix=prefix, intents=intents, help_command=None, allowed_mentions=discord.AllowedMentions.none(), owner_ids=set(self.config.owner_ids))
        self.before_invoke(self.prepare_command)

    async def setup_hook(self):
        self.db.initialize()
        if self.config.auto_load_emojis:
            await self.load_startup_emojis()
        for extension in ('utility', 'commerce', 'community', 'moderation', 'events'):
            await self.load_extension('nex.cogs.' + extension)
        if self.config.sync_commands:
            await self.publish_commands()

    async def load_startup_emojis(self):
        logger = logging.getLogger('nex')
        logger.info('emojis.application.start')
        try:
            # Prevent optional artwork from indefinitely delaying the gateway login.
            result = await asyncio.wait_for(ApplicationEmojiLoader(self).load(), timeout=180)
        except asyncio.TimeoutError:
            logger.warning('emojis.application.timeout Successful icons remain active; restart to resume. Unicode fallbacks remain available.')
        except discord.MissingApplicationID:
            logger.warning('emojis.application.unavailable Application identity missing; restart with a valid bot token. Unicode fallbacks remain available.')
        else:
            logger.info('emojis.application.loaded created=%s reused=%s mapped=%s', result['created'], result['reused'], result['mapped'])
            if result['failure']:
                logger.warning('emojis.application.partial %s Unicode fallbacks remain available.', result['failure'])

    async def publish_commands(self):
        registered = await self.tree.sync()
        for guild_id in self.config.command_guild_ids:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        logging.getLogger('nex').info('commands.synced count=%s', len(registered))
        return registered

    async def prepare_command(self, ctx):
        # Discord needs an acknowledgment before slow network/file operations finish.
        if ctx.interaction and not ctx.interaction.response.is_done():
            public = {'shop', 'product', 'giveaway'}
            await ctx.defer(ephemeral=ctx.command.name not in public)


    async def on_ready(self):
        logging.getLogger('nex').info('bot.ready')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='your community • /help • /shop'))

    async def on_command_error(self, ctx, error):
        while getattr(error, 'original', None) is not None:
            error = error.original
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, (DomainError, commands.UserInputError, commands.CheckFailure, commands.CommandOnCooldown)):
            message = str(error)
        elif isinstance(error, ValidationError):
            message = 'Invalid configuration. Check field types, limits and allowed values in the documentation.'
        elif isinstance(error, discord.Forbidden):
            message = 'Discord denied this action. Check bot permissions and role hierarchy.'
        elif isinstance(error, discord.HTTPException):
            message = 'Discord could not complete this action. Please retry.'
        else:
            logging.getLogger('nex').error('command.failed type=%s command=%s', type(error).__name__, ctx.command)
            message = 'The action could not be completed. Contact the bot owner.'
        cfg = self.core.config(ctx.guild.id) if ctx.guild else None
        await ctx.send(embed=themed_embed('error', 'Action unavailable', message, config=cfg, error=True), ephemeral=True)


async def main():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    cfg = settings()
    if not cfg.discord_token:
        raise SystemExit('Set DISCORD_TOKEN in .env before starting the bot.')
    try:
        async with NexBot(cfg) as bot:
            await bot.start(cfg.discord_token)
    except discord.PrivilegedIntentsRequired:
        raise SystemExit('Enable Server Members Intent and Message Content Intent in Discord Developer Portal > Bot, then restart.') from None
    except discord.LoginFailure:
        raise SystemExit('Discord rejected DISCORD_TOKEN. Copy the current bot token from Developer Portal > Bot into .env.') from None
    except discord.HTTPException:
        raise SystemExit('Discord connection or command registration failed. Check the bot invite includes applications.commands and retry.') from None


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
