"""Help media and component tests mock Discord; image encoding is checked separately."""
from contextlib import closing
import hashlib
import importlib
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
import pytest
from nex.utils.help_media import HELP_FILES, help_file
from tests.test_commands_and_storefront import new_bot


@pytest.mark.parametrize('section',HELP_FILES)
def test_each_help_file_is_a_bounded_gif(section):
    file=help_file(section)
    assert file.filename=='nex_help.gif'
    with closing(file):
        data=file.fp.read()
        assert data.startswith(b'GIF89a')
        assert struct.unpack('<HH',data[6:10])==(900,820)
        assert len(data)<4*1024*1024
    assert file.fp.closed


async def test_help_sends_home_animation_with_live_commands(db,core,tmp_path):
    bot=await new_bot(db,tmp_path)
    cog=bot.get_cog('Utility')
    captured={}
    async def send(**kwargs):
        captured.update(kwargs)
        captured['bytes']=kwargs['file'].fp.read()
    ctx=SimpleNamespace(guild=SimpleNamespace(id=1000),author=SimpleNamespace(id=200),send=AsyncMock(side_effect=send))
    await type(cog).help.callback(cog,ctx)
    assert captured['ephemeral']
    assert captured['embed'].image.url=='attachment://nex_help.gif'
    assert captured['bytes'].startswith(b'GIF89a')
    assert captured['file'].fp.closed
    assert '/shop' in str(captured['embed'].to_dict())
    assert '/addproduct' not in str(captured['embed'].to_dict())
    assert captured['view'].user_id==200
    assert next(child for child in captured['view'].children if isinstance(child, discord.ui.Select)).options[0].value=='Home'
    await bot.close()


async def test_category_changes_defer_then_replace_art_and_return_home(db,core,tmp_path):
    bot=await new_bot(db,tmp_path)
    module=importlib.import_module('nex.cogs.utility')
    menu=module.HelpSelect(bot,owner=True,config=core.config(1000))
    captures=[]
    events=[]
    async def edit(**kwargs):
        events.append('edit')
        captures.append((kwargs['embed'],hashlib.sha256(kwargs['attachments'][0].fp.read()).hexdigest()))
    interaction=SimpleNamespace(response=SimpleNamespace(defer=AsyncMock(side_effect=lambda:events.append('defer'))),edit_original_response=AsyncMock(side_effect=edit))
    sections=[*module.HELP_CATEGORIES,'Home']
    for section in sections:
        menu._values=[section]
        await menu.callback(interaction)
        assert captures[-1][0].image.url=='attachment://nex_help.gif'
        assert [o.value for o in menu.options if o.default]==[section]
    assert events==['defer','edit']*5
    assert len({checksum for _,checksum in captures})==5
    assert 'Command center' in captures[-1][0].title
    assert len(captures[-1][0])<6000
    await bot.close()


async def test_help_controls_belong_to_invoking_user():
    from nex.cogs.utility import HelpView
    view=HelpView(200)
    interaction=SimpleNamespace(user=SimpleNamespace(id=201),response=SimpleNamespace(send_message=AsyncMock()))
    assert not await view.interaction_check(interaction)
    assert '/help' in interaction.response.send_message.await_args.args[0]
    assert interaction.response.send_message.await_args.kwargs['ephemeral']
    interaction.user.id=200
    assert await view.interaction_check(interaction)
    view.stop()


@pytest.mark.parametrize('case',['missing','invalid','permission'])
async def test_missing_assets_or_attach_permission_keep_help_usable(db,core,tmp_path,monkeypatch,case):
    bot=await new_bot(db,tmp_path)
    module=importlib.import_module('nex.cogs.utility')
    member=SimpleNamespace(id=999)
    guild=SimpleNamespace(id=1000,me=member)
    channel=SimpleNamespace(permissions_for=lambda who:discord.Permissions(attach_files=case!='permission'))
    if case!='permission':
        monkeypatch.setattr('nex.utils.help_media.HELP_ROOT',tmp_path)
        if case=='invalid':(tmp_path/'home.gif').write_bytes(b'not a gif')
    ctx=SimpleNamespace(guild=guild,channel=channel,author=SimpleNamespace(id=200),send=AsyncMock())
    cog=bot.get_cog('Utility')
    await type(cog).help.callback(cog,ctx)
    sent=ctx.send.await_args.kwargs
    assert 'file' not in sent and not sent['embed'].image.url
    menu=next(child for child in sent['view'].children if isinstance(child, discord.ui.Select))
    menu._values=['Home']
    interaction=SimpleNamespace(response=SimpleNamespace(defer=AsyncMock()),edit_original_response=AsyncMock())
    await menu.callback(interaction)
    assert interaction.edit_original_response.await_args.kwargs['attachments']==[]
    assert '/shop' in str(interaction.edit_original_response.await_args.kwargs['embed'].to_dict())
    sent['view'].stop()
    await bot.close()


async def test_buttons_and_dropdown_share_navigation(db,core,tmp_path):
    from nex.cogs.utility import HelpView, HelpSelect
    bot=await new_bot(db,tmp_path)
    view=HelpView(200)
    menu=HelpSelect(bot,media_enabled=False)
    view.add_item(menu)
    view.update_navigation('Home',menu.options)
    interaction=SimpleNamespace(response=SimpleNamespace(defer=AsyncMock()),edit_original_response=AsyncMock())
    assert view.previous.disabled and view.home.disabled and not view.next_page.disabled
    for section in ['Utility','Commerce','Community','Moderation']:
        await view.next_page.callback(interaction)
        assert view.current_section==section
        assert [o.value for o in menu.options if o.default]==[section]
        assert interaction.edit_original_response.await_args.kwargs['view'] is view
    assert view.next_page.disabled
    await view.previous.callback(interaction)
    assert view.current_section=='Community' and not view.next_page.disabled
    await view.home.callback(interaction)
    assert view.current_section=='Home' and view.previous.disabled and view.home.disabled
    menu._values=['Moderation']
    await menu.callback(interaction)
    assert view.current_section=='Moderation' and view.next_page.disabled
    view.stop()
    await bot.close()


@pytest.mark.parametrize('deleted',[False,True])
async def test_expired_menu_disables_controls_even_if_message_deleted(deleted):
    from nex.cogs.utility import HelpView
    view=HelpView(200)
    message=SimpleNamespace(edit=AsyncMock())
    if deleted:
        message.edit.side_effect=discord.NotFound(SimpleNamespace(status=404,reason='Not Found'), 'Deleted')
    view.message=message
    await view.on_timeout()
    assert all(child.disabled for child in view.children)
    message.edit.assert_awaited_once_with(view=view)
    view.stop()
