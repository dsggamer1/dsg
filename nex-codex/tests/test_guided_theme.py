"""Offline Discord boundaries: setup authorization, mention dispatch and media delivery."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import importlib
import discord
import pytest
from pydantic import ValidationError
from nex.security import Actor, DomainError
from nex.utils.cards import send_card, edit_card, CARD_KEYS
from nex.utils.theme import themed_embed
from nex.utils.guides import GUIDES, guide_card, IntroView, GuideView
from tests.test_commands_and_storefront import new_bot


@pytest.mark.parametrize('key',sorted(CARD_KEYS))
async def test_branded_cards_send_owned_png_and_close_stream(key):
    captured={}
    async def send(**kwargs):
        captured.update(kwargs)
        captured['data']=kwargs['file'].fp.read()
    item=themed_embed('help','Example')
    await send_card(send,item,key=key)
    assert captured['data'].startswith(b'\x89PNG\r\n\x1a\n')
    assert captured['file'].fp.closed and item.image.url=='attachment://nex_card.png'
    assert item.author.name=='NEX CODEX' and item.footer.text.startswith('NEX CODEX')


@pytest.mark.parametrize('case',['custom_image','permission','missing','invalid','explicit_file'])
async def test_card_fallback_preserves_content_and_explicit_media(tmp_path,monkeypatch,case):
    send=AsyncMock();item=themed_embed('help','Content','Do not lose this text')
    channel=NS(guild=NS(me=object()),permissions_for=lambda member:discord.Permissions(attach_files=case!='permission'))
    kwargs={}
    if case=='custom_image':item.set_image(url='https://example.com/shop.png')
    if case=='explicit_file':kwargs['file']=object()
    if case in ('missing','invalid'):
        monkeypatch.setattr('nex.utils.cards.CARD_ROOT',tmp_path)
        if case=='invalid':(tmp_path/'shop.png').write_bytes(b'not PNG')
    await send_card(send,item,key='shop',channel=channel,**kwargs)
    assert send.await_args.kwargs['embed'].description=='Do not lose this text'
    assert ('file' in send.await_args.kwargs)==(case=='explicit_file')
    if case=='custom_image':assert item.image.url=='https://example.com/shop.png'


async def test_media_closes_on_failed_send_and_edits_replace_previous_attachment():
    captured={}
    async def fail(**kwargs):
        captured.update(kwargs)
        raise RuntimeError('Synthetic send failure')
    with pytest.raises(RuntimeError):await send_card(fail,themed_embed('help','Title'),key='shop')
    assert captured['file'].fp.closed
    interaction=NS(channel=None,response=NS(defer=AsyncMock()),edit_original_response=AsyncMock())
    await edit_card(interaction,themed_embed('help','Next'),key='shop',view=None)
    interaction.response.defer.assert_awaited_once()
    assert len(interaction.edit_original_response.await_args.kwargs['attachments'])==1
    assert interaction.edit_original_response.await_args.kwargs['attachments'][0].fp.closed


@pytest.mark.parametrize('section',GUIDES)
def test_guides_fit_and_describe_registered_workflows(section):
    item=guide_card(section)
    assert len(item)<=6000 and len(item.fields)<=25
    assert all(len(f.value)<=1024 for f in item.fields)




async def test_product_category_choices_are_real_registered_options(db,tmp_path):
    bot=await new_bot(db,tmp_path)
    payload=bot.tree.get_command('addproduct').to_dict(bot.tree)
    category=next(o for o in payload['options'] if o['name']=='category')
    assert {c['value'] for c in category['choices']}=={'template','bot'}
    await bot.close()


async def test_mentions_reply_with_personal_shortcuts_and_rate_limit(db,core,tmp_path):
    bot=await new_bot(db,tmp_path);bot._connection.user=NS(id=999)
    bot.get_context=AsyncMock(return_value=NS(valid=False))
    message=NS(guild=NS(id=1000),author=NS(id=200,bot=False,guild_permissions=discord.Permissions()),webhook_id=None,mentions=[NS(id=999)],channel=NS(id=77),reply=AsyncMock())
    events=bot.get_cog('Events')
    for _ in range(3):await events.on_message(message)
    assert message.reply.await_count==2
    sent=message.reply.await_args.kwargs
    assert '/help' in str(sent['embed'].to_dict()) and '!help' in str(sent['embed'].to_dict())
    assert sent['allowed_mentions'].to_dict().get('parse',[])==[] and not sent['mention_author']
    assert isinstance(sent['view'],IntroView) and sent['view'].user_id==200
    sent['view'].stop()
    bot.get_context.return_value=NS(valid=True)
    await events.on_message(message)
    assert message.reply.await_count==2
    await bot.close()


@pytest.mark.parametrize('case',['dm','bot','webhook','not_mentioned'])
async def test_mentions_ignore_unrelated_or_automated_messages(db,tmp_path,case):
    bot=await new_bot(db,tmp_path);bot._connection.user=NS(id=999)
    bot.get_context=AsyncMock()
    message=NS(guild=None if case=='dm' else NS(id=1000),author=NS(bot=case=='bot'),webhook_id=1 if case=='webhook' else None,mentions=[] if case=='not_mentioned' else [NS(id=999)],reply=AsyncMock())
    await bot.get_cog('Events').on_message(message)
    bot.get_context.assert_not_awaited();message.reply.assert_not_awaited()
    await bot.close()


async def test_mention_help_shortcut_opens_actual_animated_help(db,core,tmp_path):
    bot=await new_bot(db,tmp_path)
    view=IntroView(200)
    interaction=NS(client=bot,user=NS(id=200),guild=NS(id=1000),channel=None,response=NS(defer=AsyncMock(),send_message=AsyncMock()),followup=NS(send=AsyncMock()))
    await view.help_button.callback(interaction)
    sent=interaction.followup.send.await_args.kwargs
    assert sent['embed'].image.url=='attachment://nex_help.gif' and sent['view'].user_id==200
    interaction.user.id=201
    assert not await view.interaction_check(interaction)
    view.stop();sent['view'].stop();await bot.close()


async def test_shop_pagination_and_guide_navigation_replace_art(db,core,free,tmp_path):
    from nex.utils.storefront import ShopView
    bot=await new_bot(db,tmp_path)
    interaction=NS(channel=None,response=NS(defer=AsyncMock()),edit_original_response=AsyncMock())
    view=ShopView(200,bot,1000)
    await view.turn(interaction,1)
    sent=interaction.edit_original_response.await_args.kwargs
    assert sent['view'].page==2 and sent['embed'].image.url=='attachment://nex_card.png'
    assert len(sent['attachments'])==1
    guide=GuideView(200)
    menu=guide.children[0];menu._values=['tickets']
    await menu.callback(interaction)
    sent=interaction.edit_original_response.await_args.kwargs
    assert '/ticketsetup' in str(sent['embed'].to_dict())
    assert [o.value for o in menu.options if o.default]==['tickets']
    view.stop();guide.stop();await bot.close()


async def test_help_setup_shortcut_rechecks_management_access(db,core,tmp_path):
    from nex.cogs.utility import HelpShortcut
    bot=await new_bot(db,tmp_path)
    button=HelpShortcut('setup')
    interaction=NS(client=bot,guild_id=1000,user=NS(id=200,guild_permissions=discord.Permissions()),channel=None,response=NS(defer=AsyncMock()),followup=NS(send=AsyncMock()))
    with pytest.raises(DomainError):await button.callback(interaction)
    interaction.followup.send.assert_not_awaited()
    interaction.user.guild_permissions.administrator=True
    await button.callback(interaction)
    assert isinstance(interaction.followup.send.await_args.kwargs['view'],GuideView)
    interaction.followup.send.await_args.kwargs['view'].stop()
    await bot.close()


async def test_setup_command_opens_guide_and_mention_shop_opens_current_catalogue(db,core,owner,free,tmp_path,monkeypatch):
    bot=await new_bot(db,tmp_path)
    module=importlib.import_module('nex.cogs.utility');monkeypatch.setattr(module,'actor',lambda ctx:owner)
    ctx=NS(guild=NS(id=1000),author=NS(id=100),channel=None,send=AsyncMock())
    cog=bot.get_cog('Utility')
    await type(cog).setup.callback(cog,ctx)
    assert isinstance(ctx.send.await_args.kwargs['view'],GuideView)
    assert '/ticketsetup' in str(ctx.send.await_args.kwargs['embed'].to_dict())
    view=IntroView(200)
    interaction=NS(client=bot,guild_id=1000,user=NS(id=200),channel=None,response=NS(defer=AsyncMock()),followup=NS(send=AsyncMock()))
    await view.shop_button.callback(interaction)
    sent=interaction.followup.send.await_args.kwargs
    assert sent['view'].products[0].id==free.id and sent['ephemeral']
    view.stop();sent['view'].stop();ctx.send.await_args.kwargs['view'].stop()
    await bot.close()
