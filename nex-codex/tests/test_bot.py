import pytest
from nex.bot import NexBot
from nex.config import Settings


async def test_extensions_and_slash_registration_without_discord_network(db,tmp_path):
    config=Settings(_env_file=None,product_root=tmp_path,auto_load_emojis=False, sync_commands=False)
    bot=NexBot(config,db)
    async with bot:
        await bot.setup_hook()
        registered={command.name for command in bot.tree.get_commands()}
        required={'help','welcome','leave','say','broadcast','prefix','configure','setup','diagnostics','installemojis','shop','product','addproduct','productedit','productpublish','createshop','buy','orders','orderfulfill','deliver','ticket','ticketmanage','transcript','orderstate','giveaway','reroll'}
        required.update({'productid','shopsetup','channelsetup','welcomesetup','leavesetup','rejoinallow','ticketsetup','giveawaysetup','kick','ban','warn','timeout','giverole','takerole','warnings'})
        assert required == registered
        assert bot.get_cog('Moderation') is not None
        for command in bot.tree.get_commands():
            payload=command.to_dict(bot.tree)
            assert payload['name'] and payload['description']
        assert len(registered)==len(bot.tree.get_commands())
        assert bot.intents.members and bot.intents.message_content


def test_upgrade_keeps_orders_and_ignores_retired_settings(db, core, owner, market, free, buyer):
    from sqlalchemy import inspect, text
    from nex.models import Guild, Order
    from nex.schemas import GuildConfig
    from pydantic import ValidationError
    order=market.order(buyer,free.id,'upgrade-existing')
    with db.transaction() as session:
        guild=session.get(Guild,1000)
        guild.settings={**guild.settings,'leveling_enabled':True,'rewards_enabled':True,'self_roles':[50],'ai_enabled':True}
        session.execute(text('CREATE TABLE legacy_unused_records (id INTEGER PRIMARY KEY, note TEXT)'))
        session.execute(text("INSERT INTO legacy_unused_records VALUES (1, 'preserve')"))
    db.initialize()
    cfg=core.config(1000)
    assert cfg['staff_roles']==[20] and 'ai_enabled' not in cfg
    core.configure(owner,{'shop_title':'Clean collection'})
    with db.sessions() as session:
        assert session.get(Order,order.id).snapshot['name']==free.name
        assert session.execute(text('SELECT note FROM legacy_unused_records WHERE id=1')).scalar()=='preserve'
    assert 'web_sessions' not in inspect(db.engine).get_table_names()
    with pytest.raises(ValidationError):core.configure(owner,{'ai_enabled':True})
    assert 'ai_enabled' not in GuildConfig.model_fields


def test_bot_dependencies_and_config_have_no_web_or_ai_surface():
    from pathlib import Path
    names={line.split('>')[0].split('[')[0].lower() for line in (Path(__file__).resolve().parents[1]/'requirements.txt').read_text().splitlines()}
    assert not names.intersection({'fastapi','uvicorn','httpx','jinja2','python-multipart'})
    assert not {'session_secret','discord_client_secret','ai_api_key'}.intersection(Settings.model_fields)
