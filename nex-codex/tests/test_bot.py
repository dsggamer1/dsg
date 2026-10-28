import pytest
from nex.bot import NexBot
from nex.config import Settings


async def test_extensions_and_slash_registration_without_discord_network(db,tmp_path):
    config=Settings(_env_file=None,product_root=tmp_path)
    bot=NexBot(config,db)
    async with bot:
        await bot.setup_hook()
        registered={command.name for command in bot.tree.get_commands()}
        required={'help','ban','unban','kick','timeout','untimeout','warn','history','purge','shop','buy','payment','paymentreview','deliver','ticket','ticketmanage','premium','review','giveaway','reroll','leaderboard','referral','remind','roles','configure','ask'}
        assert required <= registered
        for command in bot.tree.get_commands():
            payload=command.to_dict(bot.tree)
            assert payload['name'] and payload['description']
        assert len(registered)==len(bot.tree.get_commands())
        assert bot.intents.members and bot.intents.message_content
