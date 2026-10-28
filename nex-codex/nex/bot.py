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
from .security import DomainError, RateLimiter
from .utils.discord import embed


class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Only controlled event messages are logged; exception payloads may contain tokens/URLs.
        return json.dumps({'level': record.levelname, 'logger': record.name, 'event': record.getMessage()})


async def prefix(bot, message):
    value = bot.core.config(message.guild.id)['prefix'] if message.guild else bot.config.default_prefix
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
        intents.members = intents.message_content = intents.moderation = True
        super().__init__(command_prefix=prefix, intents=intents, help_command=None, allowed_mentions=discord.AllowedMentions.none(), owner_ids=set(self.config.owner_ids))

    async def setup_hook(self):
        self.db.initialize()
        for extension in ('utility', 'moderation', 'commerce', 'community', 'events'):
            await self.load_extension('nex.cogs.' + extension)
        # Global sync is explicit via owner-only !sync to avoid startup rate-limit churn.

    async def on_ready(self):
        logging.getLogger('nex').info('bot.ready')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='your community • /help'))

    async def on_command_error(self, ctx, error):
        error = getattr(error, 'original', error)
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
        await ctx.send(embed=embed('Action unavailable', message, error=True), ephemeral=True)


async def main():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    cfg = settings()
    if not cfg.discord_token:
        raise SystemExit('Set DISCORD_TOKEN in .env before starting the bot.')
    async with NexBot(cfg) as bot:
        await bot.start(cfg.discord_token)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
