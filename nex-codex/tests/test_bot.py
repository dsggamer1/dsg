import pytest
from nex.bot import NexBot
from nex.config import Settings


async def test_extensions_and_slash_registration_without_discord_network(db,tmp_path):
    config=Settings(_env_file=None,product_root=tmp_path,auto_load_emojis=False, sync_commands=False)
    bot=NexBot(config,db)
    async with bot:
        await bot.setup_hook()
        registered={command.name for command in bot.tree.get_commands()}
        required={'help','welcome','leave','say','broadcast','prefix','configure','setup','diagnostics','installemojis','shop','product','addproduct','productedit','productpublish','createshop','buy','orders','payment','paymentreview','deliver','ticket','ticketmanage','transcript','orderstate','giveaway','reroll'}
        assert required == registered
        assert bot.get_cog('Moderation') is None
        for command in bot.tree.get_commands():
            payload=command.to_dict(bot.tree)
            assert payload['name'] and payload['description']
        assert len(registered)==len(bot.tree.get_commands())
        assert bot.intents.members and bot.intents.message_content
