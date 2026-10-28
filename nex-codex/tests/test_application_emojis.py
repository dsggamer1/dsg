"""Automatic startup and application API tests use mocks, not live Discord."""
import asyncio
import importlib
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
import aiohttp
import pytest
from nex.bot import NexBot
from nex.config import Settings
from nex.services.emojis import ApplicationEmojiLoader, BUNDLED_ASSETS, EMOJI_ASSETS
from nex.utils import theme
from nex.utils.storefront import ShopPanel
from tests.test_emoji_installer import Emoji


@pytest.fixture(autouse=True)
def isolated_theme(monkeypatch):
    monkeypatch.setattr(theme, '_APPLICATION_EMOJIS', {})


def application():
    emojis=[]
    async def create(**kwargs):
        assert kwargs['image'].startswith(b'\x89PNG\r\n\x1a\n')
        emoji=Emoji(kwargs['name'],123456789012345678+len(emojis))
        emojis.append(emoji)
        return emoji
    return SimpleNamespace(fetch_application_emojis=AsyncMock(side_effect=lambda:list(emojis)),create_application_emoji=AsyncMock(side_effect=create))


async def test_all_bundled_artwork_automatically_uploads_and_restores_without_duplicates():
    assert len(BUNDLED_ASSETS)==len(set(BUNDLED_ASSETS))==49
    client=application()
    result=await ApplicationEmojiLoader(client).load()
    assert result=={'created':49,'reused':0,'mapped':14,'failure':None}
    assert {call.kwargs['name'] for call in client.create_application_emoji.await_args_list}=={'nex_'+asset for asset in BUNDLED_ASSETS}
    assert theme.emoji_for('welcome')=='<:nex_welcome:123456789012345678>'
    assert theme.emoji_for('shop').startswith('<:nex_cart:')
    panel=ShopPanel()
    assert str(panel.browse.emoji)==theme.emoji_for('shop')
    assert theme.themed_embed('ticket','Support').title.startswith(theme.emoji_for('ticket'))
    panel.stop()
    before={key:theme.emoji_for(key) for key in EMOJI_ASSETS}
    theme.set_application_emojis({})  # Simulate a fresh process; persistence is at Discord.
    result=await ApplicationEmojiLoader(client).load()
    assert result=={'created':0,'reused':49,'mapped':14,'failure':None}
    assert before=={key:theme.emoji_for(key) for key in EMOJI_ASSETS}
    assert client.create_application_emoji.await_count==49
    assert theme.emoji_for('shop',{'emojis':{'shop':'🎉'}})=='🎉'


async def test_startup_loads_before_persistent_views_and_command_registration(db,tmp_path):
    assert Settings(_env_file=None).auto_load_emojis is True
    client=application()
    bot=NexBot(Settings(_env_file=None,product_root=tmp_path,sync_commands=True),db)
    bot.fetch_application_emojis=client.fetch_application_emojis
    bot.create_application_emoji=client.create_application_emoji
    async def sync():
        assert len(bot.tree.get_commands())==43
        assert theme.emoji_for('shop').startswith('<:nex_cart:')
        return []
    bot.tree.sync=AsyncMock(side_effect=sync)
    async with bot:
        await bot.setup_hook()
        assert client.create_application_emoji.await_count==49
        panel=next(v for v in bot.persistent_views if isinstance(v,ShopPanel))
        assert str(panel.browse.emoji)==theme.emoji_for('shop')
        bot.tree.sync.assert_awaited_once()


async def test_disabled_startup_makes_no_emoji_api_calls(db):
    bot=NexBot(Settings(_env_file=None,sync_commands=False,auto_load_emojis=False),db)
    bot.fetch_application_emojis=AsyncMock()
    bot.create_application_emoji=AsyncMock()
    async with bot:
        await bot.setup_hook()
        bot.fetch_application_emojis.assert_not_awaited()
        bot.create_application_emoji.assert_not_awaited()
        assert theme.emoji_for('shop')==theme.DEFAULT_EMOJIS['shop']


async def test_partial_upload_applies_successes_and_restart_resumes():
    client=application()
    create=client.create_application_emoji.side_effect
    async def fail_second(**kwargs):
        if client.create_application_emoji.await_count==2:
            raise discord.HTTPException(SimpleNamespace(status=500,reason='Synthetic'),'Synthetic failure')
        return await create(**kwargs)
    client.create_application_emoji.side_effect=fail_second
    result=await ApplicationEmojiLoader(client).load()
    assert result['created']==result['mapped']==1 and result['failure']
    assert theme.emoji_for('welcome').startswith('<:nex_welcome:')
    assert theme.emoji_for('leave')==theme.DEFAULT_EMOJIS['leave']
    client.create_application_emoji.side_effect=create
    result=await ApplicationEmojiLoader(client).load()
    assert result=={'created':48,'reused':1,'mapped':14,'failure':None}


@pytest.mark.parametrize('error',[discord.Forbidden(SimpleNamespace(status=403,reason='Forbidden'),'PRIVATE_SENTINEL'),aiohttp.ServerDisconnectedError('PRIVATE_SENTINEL')])
async def test_fetch_denial_keeps_bot_commands_available_without_leaking_payload(db,caplog,error):
    bot=NexBot(Settings(_env_file=None,sync_commands=False),db)
    bot.fetch_application_emojis=AsyncMock(side_effect=error)
    bot.create_application_emoji=AsyncMock()
    with caplog.at_level(logging.INFO,logger='nex'):
        async with bot:
            await bot.setup_hook()
            assert len(bot.tree.get_commands())==43
            bot.create_application_emoji.assert_not_awaited()
    assert theme.emoji_for('help')==theme.DEFAULT_EMOJIS['help']
    assert 'emojis.application.partial' in caplog.text
    assert 'PRIVATE_SENTINEL' not in caplog.text


@pytest.mark.parametrize('invalid',[False,True])
async def test_missing_or_invalid_bundled_asset_is_reported(tmp_path,monkeypatch,invalid):
    module=importlib.import_module('nex.services.emojis')
    monkeypatch.setattr(module,'ASSET_ROOT',tmp_path)
    if invalid:
        (tmp_path/'nex_welcome.png').write_bytes(b'not an image')
    client=application()
    result=await ApplicationEmojiLoader(client).load()
    assert result['failure'] and result['mapped']==result['created']==0
    client.create_application_emoji.assert_not_awaited()


async def test_full_application_uses_existing_then_reports_capacity():
    client=application()
    existing=[Emoji('nex_welcome',123456789012345678)]
    existing.extend(Emoji(f'other_{i}',123456789012345679+i) for i in range(1999))
    client.fetch_application_emojis.side_effect=None
    client.fetch_application_emojis.return_value=existing
    result=await ApplicationEmojiLoader(client).load()
    assert result['reused']==result['mapped']==1 and 'capacity' in result['failure']
    client.create_application_emoji.assert_not_awaited()
    assert theme.emoji_for('welcome')==str(existing[0])


async def test_startup_timeout_keeps_partial_mapping_and_finishes_setup(db,monkeypatch,caplog):
    original_wait_for=asyncio.wait_for
    async def short_wait(awaitable,timeout):
        assert timeout==180
        return await original_wait_for(awaitable,timeout=0.01)
    monkeypatch.setattr('nex.bot.asyncio.wait_for',short_wait)
    client=application()
    create=client.create_application_emoji.side_effect
    async def slow_second(**kwargs):
        if client.create_application_emoji.await_count==2:
            await asyncio.sleep(3600)
        return await create(**kwargs)
    bot=NexBot(Settings(_env_file=None,sync_commands=False),db)
    bot.fetch_application_emojis=client.fetch_application_emojis
    bot.create_application_emoji=AsyncMock(side_effect=slow_second)
    client.create_application_emoji=bot.create_application_emoji
    with caplog.at_level(logging.WARNING,logger='nex'):
        async with bot:
            await bot.setup_hook()
            assert len(bot.tree.get_commands())==43
    assert theme.emoji_for('welcome').startswith('<:nex_welcome:')
    assert 'emojis.application.timeout' in caplog.text


async def test_missing_application_identity_reports_fallback(db,caplog):
    bot=NexBot(Settings(_env_file=None,sync_commands=False),db)
    bot.fetch_application_emojis=AsyncMock(side_effect=discord.MissingApplicationID())
    with caplog.at_level(logging.WARNING,logger='nex'):
        async with bot:
            await bot.setup_hook()
            assert len(bot.tree.get_commands())==43
    assert 'emojis.application.unavailable' in caplog.text
    assert theme.emoji_for('shop')==theme.DEFAULT_EMOJIS['shop']
