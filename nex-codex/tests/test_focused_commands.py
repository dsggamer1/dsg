"""Focused command contract: Discord calls are mocked, never a live integration."""
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
import pytest
from pydantic import ValidationError
from sqlalchemy import select, func
from nex.models import Audit, Product
from nex.schemas import GuildConfig
from nex.security import Actor, DomainError
from nex.utils.storefront import ShopPanel, ShopView
from nex.utils.theme import themed_embed
from tests.test_commands_and_storefront import new_bot


@pytest.mark.parametrize('who',[Actor(101,1000,administrator=True),Actor(102,1000,frozenset({20,30})),Actor(200,1000)])
def test_nonowners_cannot_change_products_or_configuration(core,market,paid,who):
    with pytest.raises(DomainError,match='Only a bot owner'):
        core.configure(who,{'shop_title':'Unauthorized change'})
    with pytest.raises(DomainError,match='Only a bot owner'):
        market.save_product(who,{'name':'Unauthorized source','category':'source','delivery_value':'x'})
    with pytest.raises(DomainError,match='Only a bot owner'):
        market.save_product(who,{'name':'Unauthorized edit','category':'source','delivery_value':'x'},paid.id)
    assert core.config(1000)['shop_title']=='NEX CODEX • The collection'


@pytest.mark.parametrize('user_id',[101,102,200])
async def test_owner_command_checks_reject_administrator_and_staff(db,core,tmp_path,user_id):
    bot=await new_bot(db,tmp_path)
    names=['welcome','leave','prefix','configure','setup','diagnostics','addproduct','productedit','productpublish','createshop','sync']
    for name in names:
        command=bot.get_command(name)
        ctx=SimpleNamespace(bot=bot,command=command,interaction=None,guild=SimpleNamespace(id=1000),author=SimpleNamespace(id=user_id,guild_permissions=discord.Permissions(administrator=True)))
        with pytest.raises(DomainError,match='Only a bot owner'):
            await command.can_run(ctx)
        if getattr(command,'app_command',None) is not None:
            interaction=SimpleNamespace(client=bot,_baton=ctx)
            with pytest.raises(DomainError,match='Only a bot owner'):
                await command.app_command._check_can_run(interaction)
        ctx.author.id=100
        assert await command.can_run(ctx)
    assert bot.get_command('productadd') is bot.get_command('addproduct')
    await bot.close()


async def test_help_hides_owner_commands_from_members(db,core,tmp_path):
    bot=await new_bot(db,tmp_path)
    cog=bot.get_cog('Utility')
    ctx=SimpleNamespace(guild=SimpleNamespace(id=1000),author=SimpleNamespace(id=200),send=AsyncMock())
    await type(cog).help.callback(cog,ctx)
    card=ctx.send.await_args.kwargs['embed']
    member_text=str(card.to_dict())
    assert '/shop' in member_text and '/ticket' in member_text
    assert '/addproduct' not in member_text and '/configure' not in member_text
    ctx.author.id=100
    await type(cog).help.callback(cog,ctx)
    assert '/addproduct' in str(ctx.send.await_args.kwargs['embed'].to_dict())
    await bot.close()


@pytest.mark.parametrize('kind',['welcome','leave'])
async def test_membership_setup_preview_event_and_disable(db,core,owner,tmp_path,monkeypatch,kind):
    bot=await new_bot(db,tmp_path)
    module=importlib.import_module('nex.cogs.utility')
    monkeypatch.setattr(module,'actor',lambda ctx:owner)
    channel=SimpleNamespace(id=77,guild=SimpleNamespace(id=1000),send=AsyncMock())
    member=SimpleNamespace(id=200,name='Test',display_name='Test',mention='<@200>',guild=SimpleNamespace(id=1000,name='Synthetic server',get_channel=lambda ident:channel if ident==77 else None,get_role=lambda ident:None))
    ctx=SimpleNamespace(guild=member.guild,author=member,send=AsyncMock())
    cog=bot.get_cog('Utility')
    command=getattr(type(cog),kind)
    await command.callback(cog,ctx,channel,True,message='Hello {user} in {server} — {name}')
    assert core.config(1000)[kind+'_channel']==77
    card=ctx.send.await_args.kwargs['embed']
    assert card.description=='Hello <@200> in Synthetic server — Test'
    listener=getattr(bot.get_cog('Events'),'on_member_join' if kind=='welcome' else 'on_member_remove')
    await listener(member)
    assert channel.send.await_args.kwargs['embed'].description==card.description
    await command.callback(cog,ctx,None,False,message='')
    assert core.config(1000)[kind+'_channel'] is None
    await bot.close()


@pytest.mark.parametrize('broadcast',[False,True])
async def test_staff_announcements_validate_send_audit_and_disable_mentions(db,core,tmp_path,monkeypatch,broadcast):
    bot=await new_bot(db,tmp_path)
    module=importlib.import_module('nex.cogs.utility')
    staff=Actor(102,1000,frozenset({20}))
    monkeypatch.setattr(module,'actor',lambda ctx:staff)
    channel=SimpleNamespace(id=77,guild=SimpleNamespace(id=1000),mention='<#77>',send=AsyncMock(return_value=SimpleNamespace(id=987)),permissions_for=lambda member:discord.Permissions(view_channel=True,send_messages=True))
    ctx=SimpleNamespace(guild=channel.guild,channel=channel,author=SimpleNamespace(id=102),send=AsyncMock())
    cog=bot.get_cog('Utility')
    if broadcast:
        await type(cog).broadcast.callback(cog,ctx,'New collection','@everyone <@&20> open the shop',channel)
        assert channel.send.await_args.kwargs['embed'].description.startswith('@everyone')
    else:
        await type(cog).say.callback(cog,ctx,'@everyone <@&20> hello',channel)
        assert channel.send.await_args.args[0].startswith('@everyone')
    allowed=channel.send.await_args.kwargs['allowed_mentions'].to_dict()
    assert allowed.get('parse',[])==[] and not allowed.get('replied_user',False)
    with db.sessions() as s:
        event=s.scalar(select(Audit).where(Audit.target=='987'))
        assert event.actor_id==102 and event.details['channel_id']==77
    monkeypatch.setattr(module,'actor',lambda ctx:Actor(200,1000))
    with pytest.raises(DomainError):
        await cog.announce(ctx,channel,'No permission')
    assert channel.send.await_count==1
    await bot.close()


async def test_announcements_cannot_bypass_channel_permissions_or_report_failed_send(db,core,tmp_path,monkeypatch):
    bot=await new_bot(db,tmp_path)
    module=importlib.import_module('nex.cogs.utility')
    monkeypatch.setattr(module,'actor',lambda ctx:Actor(102,1000,frozenset({20})))
    channel=SimpleNamespace(id=77,guild=SimpleNamespace(id=1000),send=AsyncMock(),permissions_for=lambda member:discord.Permissions.none())
    ctx=SimpleNamespace(guild=channel.guild,author=SimpleNamespace(id=102),send=AsyncMock())
    cog=bot.get_cog('Utility')
    with pytest.raises(DomainError,match='view and send'):
        await cog.announce(ctx,channel,'Private channel')
    channel.send.assert_not_awaited()
    channel.permissions_for=lambda member:discord.Permissions(view_channel=True,send_messages=True)
    channel.send.side_effect=discord.Forbidden(SimpleNamespace(status=403,reason='Forbidden'),'Missing permissions')
    with pytest.raises(discord.Forbidden):
        await cog.announce(ctx,channel,'Failed send')
    ctx.send.assert_not_awaited()
    with db.sessions() as s:
        assert s.scalar(select(func.count()).select_from(Audit).where(Audit.action=='say.send'))==0
    await bot.close()


async def test_owner_posts_persistent_shop_and_every_buyer_gets_private_view(db,core,owner,free,tmp_path,monkeypatch):
    bot=await new_bot(db,tmp_path)
    module=importlib.import_module('nex.cogs.commerce')
    monkeypatch.setattr(module,'actor',lambda ctx:owner)
    channel=SimpleNamespace(id=77,guild=SimpleNamespace(id=1000),mention='<#77>',send=AsyncMock(return_value=SimpleNamespace(id=987)))
    ctx=SimpleNamespace(guild=channel.guild,channel=channel,send=AsyncMock())
    cog=bot.get_cog('Commerce')
    await type(cog).createshop.callback(cog,ctx,channel)
    panel=channel.send.await_args.kwargs['view']
    assert panel.is_persistent() and panel.browse.custom_id=='nex:shop:browse'
    # A newly constructed view dispatches the same component after process restart.
    restored=ShopPanel()
    for user_id in (200,201):
        interaction=SimpleNamespace(guild_id=1000,client=bot,user=SimpleNamespace(id=user_id),response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
        await restored.browse.callback(interaction)
        args=interaction.followup.send.await_args.kwargs
        assert args['ephemeral'] and isinstance(args['view'],ShopView) and args['view'].user_id==user_id
        args['view'].stop()
    monkeypatch.setattr(module,'actor',lambda ctx:Actor(101,1000,administrator=True))
    with pytest.raises(DomainError):
        await type(cog).createshop.callback(cog,ctx,channel)
    assert channel.send.await_count==1
    await bot.close()


@pytest.mark.parametrize('value',['👋','🎉','<:nex_shop:123456789012345678>','<a:nex_glow:123456789012345678>'])
def test_emoji_config_and_embed_rendering(core,owner,value):
    cfg=core.configure(owner,{'emojis':{'welcome':value,'shop':value}})
    assert themed_embed('welcome','Welcome',config=cfg).title.startswith(value)
    assert core.config(1000)['emojis']['shop']==value


@pytest.mark.parametrize('data',[{'unknown':'🎉'},{'shop':'https://example.com'},{'welcome':'@everyone'},{'shop':'<:bad:99999999999999999999>'},{'ticket':'hello'},{'shop':'x'*100}])
def test_invalid_emojis_are_rejected(data):
    with pytest.raises(ValidationError):
        GuildConfig(emojis=data)


async def test_persistent_giveaway_button_acknowledges_and_records_one_entry(db,core,tmp_path):
    from datetime import timedelta
    from nex.models import Giveaway, Entry, now
    bot=await new_bot(db,tmp_path)
    module=importlib.import_module('nex.cogs.community')
    with db.transaction() as s:
        row=Giveaway(guild_id=1000,channel_id=77,prize='Synthetic template',winner_count=1,ends_at=now()+timedelta(hours=1))
        s.add(row)
        s.flush()
    view=module.GiveawayEntry({'emojis':{'giveaway':'🎁'}})
    assert view.is_persistent() and str(view.enter.emoji)=='🎁'
    interaction=SimpleNamespace(client=bot,guild_id=1000,user=SimpleNamespace(id=200),message=SimpleNamespace(embeds=[SimpleNamespace(footer=SimpleNamespace(text=f'NEX CODEX • {row.id}'))]),response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
    await view.enter.callback(interaction)
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    assert 'saved' in interaction.followup.send.await_args.args[0]
    await view.enter.callback(interaction)
    assert 'already recorded' in interaction.followup.send.await_args.args[0]
    with db.sessions() as s:
        assert s.scalar(select(func.count()).select_from(Entry))==1
    await bot.close()
