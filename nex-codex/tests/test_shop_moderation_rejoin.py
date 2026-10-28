from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import importlib
import discord
import pytest
from sqlalchemy import select
from nex.models import Product,Order,RejoinBlock,Moderation
from nex.security import Actor,DomainError,check_hierarchy
from nex.services import rejoin
from tests.test_commands_and_storefront import new_bot


def test_short_ids_rename_preserve_order_ownership(db,market,paid,owner,buyer):
    assert len(paid.code)==8
    order=market.order(buyer,paid.code,'short')
    changed=market.change_code(owner,paid.code,'gaming-bot')
    assert changed.id==paid.id and changed.code=='gaming-bot'
    with db.sessions() as s:
        assert s.get(Order,order.id).product_id==paid.id
        assert market.resolve(s,1000,'gaming-bot').id==paid.id
        assert market.resolve(s,1001,'gaming-bot') is None
    second=market.save_product(owner,{'name':'Other bot','category':'bot','delivery_value':'instructions'})
    with pytest.raises(DomainError):market.change_code(owner,second.code,'gaming-bot')
    with pytest.raises(DomainError):market.change_code(buyer,'gaming-bot','stolen')
    with pytest.raises(DomainError):market.change_code(owner,'gaming-bot','../bad')


async def test_product_suggestions_scope_drafts_and_search(db,core,market,paid,owner,tmp_path):
    draft=market.save_product(owner,{'name':'Draft template','category':'template','delivery_value':'x'})
    bot=await new_bot(db,tmp_path);cog=bot.get_cog('Commerce')
    member=NS(guild_id=1000,user=NS(id=200))
    assert {c.value for c in await cog.product_choices(member,'')}=={paid.code}
    member.user.id=100
    assert {c.value for c in await cog.product_choices(member,'Draft')}=={draft.code}
    member.guild_id=2000
    assert await cog.product_choices(member,'')==[]
    for name in ('product','productedit','productpublish','productid','buy'):
        payload=bot.tree.get_command(name).to_dict(bot.tree)
        assert next(o for o in payload['options'] if o['name']=='product_id')['autocomplete']
    await bot.close()


def member(guild,ident=200,**kwargs):
    return NS(id=ident,bot=False,guild=guild,roles=[],guild_permissions=discord.Permissions(),top_role=1,kick=AsyncMock(),**kwargs)


async def test_optin_rejoin_records_and_enforces_with_exemptions(db,core,owner,tmp_path):
    bot=await new_bot(db,tmp_path);bot._connection.user=NS(id=999)
    guild=NS(id=1000,owner_id=1,me=NS(top_role=10,guild_permissions=discord.Permissions(kick_members=True)))
    user=member(guild)
    rejoin.remember(bot,user,core.config(1000))
    with db.sessions() as s:assert s.scalar(select(RejoinBlock)) is None
    cfg=core.configure(owner,{'restrict_rejoin':True})
    rejoin.remember(bot,user,cfg);rejoin.remember(bot,user,cfg)
    assert await rejoin.enforce(bot,user,cfg) is True
    user.kick.assert_awaited_once()
    guild.me.guild_permissions.kick_members=False
    assert await rejoin.enforce(bot,user,cfg) is None
    assert user.kick.await_count==1
    user.guild_permissions.administrator=True
    assert not await rejoin.enforce(bot,user,cfg)
    user.guild_permissions.administrator=False
    rejoin.clear(bot,owner,user.id)
    assert not await rejoin.enforce(bot,user,cfg)
    for ident in (100,1):
        rejoin.remember(bot,member(guild,ident),cfg)
    staff=member(guild,201);staff.roles=[NS(id=20)]
    rejoin.remember(bot,staff,cfg)
    with db.sessions() as s:assert s.scalar(select(RejoinBlock)) is None
    await bot.close()


@pytest.mark.parametrize('case',['self','owner','bot','moderator_role','bot_role'])
def test_hierarchy_blocks_protected_targets(case):
    guild=NS(owner_id=1);mod=NS(id=2,top_role=10);target=NS(id=3,top_role=1);bot=NS(id=4,top_role=20)
    if case=='self':target.id=2
    if case=='owner':target.id=1
    if case=='bot':target.id=4
    if case=='moderator_role':target.top_role=11
    if case=='bot_role':mod.top_role=30;target.top_role=21
    with pytest.raises(DomainError):check_hierarchy(guild,mod,target,bot)


async def test_kick_rechecks_permission_after_confirmation(db,core,tmp_path,monkeypatch):
    bot=await new_bot(db,tmp_path);cog=bot.get_cog('Moderation')
    module=importlib.import_module('nex.cogs.moderation')
    monkeypatch.setattr(module,'confirm',AsyncMock(return_value=True))
    moderator=NS(id=102,top_role=10,guild_permissions=discord.Permissions(kick_members=False))
    target=NS(id=200,top_role=1,display_name='Synthetic',kick=AsyncMock())
    guild=NS(id=1000,owner_id=1,me=NS(id=999,top_role=20),fetch_member=AsyncMock(side_effect=lambda ident:moderator if ident==102 else target))
    ctx=NS(guild=guild,author=moderator)
    with pytest.raises(DomainError):await type(cog).kick.callback(cog,ctx,target,reason='Synthetic')
    target.kick.assert_not_awaited()
    moderator.guild_permissions.kick_members=True;guild.me.guild_permissions=discord.Permissions(kick_members=True);guild.get_channel=lambda ident:None
    ctx.send=AsyncMock()
    await type(cog).kick.callback(cog,ctx,target,reason='Synthetic')
    target.kick.assert_awaited_once()
    with db.sessions() as s:assert s.scalar(select(Moderation)).action=='kick'
    await bot.close()


async def test_paid_checkout_automatically_creates_private_ticket(db,core,paid,tmp_path):
    from nex.utils.storefront import CheckoutView
    bot=await new_bot(db,tmp_path);commerce=bot.get_cog('Commerce')
    commerce.send_purchase_ticket=AsyncMock()
    user=NS(id=200)
    interaction=NS(id=987,guild_id=1000,guild=NS(id=1000),user=user,client=bot,response=NS(defer=AsyncMock()),followup=NS(send=AsyncMock()),message=NS(edit=AsyncMock()))
    view=CheckoutView(200,paid)
    await view.confirm_order.callback(interaction)
    commerce.send_purchase_ticket.assert_awaited_once()
    order=commerce.send_purchase_ticket.await_args.args[3]
    assert order.amount==49900 and order.state=='awaiting_staff'
    view.stop();await bot.close()


async def test_member_events_enforce_saved_rejoin_before_welcome(db,core,owner,tmp_path):
    bot=await new_bot(db,tmp_path);bot._connection.user=NS(id=999)
    core.configure(owner,{'restrict_rejoin':True})
    guild=NS(id=1000,owner_id=1,me=NS(top_role=10,guild_permissions=discord.Permissions(kick_members=True)),get_channel=lambda ident:None)
    user=member(guild,display_name='Synthetic')
    events=bot.get_cog('Events');events.log=AsyncMock()
    await events.on_member_remove(user)
    await events.on_member_join(user)
    user.kick.assert_awaited_once()
    assert events.log.await_args.args[1]=='Rejoin restriction'
    await bot.close()


async def test_role_controls_block_privileged_roles_before_discord_write(db,core,tmp_path):
    bot=await new_bot(db,tmp_path);cog=bot.get_cog('Moderation')
    moderator=NS(id=102,top_role=50,guild_permissions=discord.Permissions(manage_roles=True))
    target=NS(id=200,top_role=10,add_roles=AsyncMock(),remove_roles=AsyncMock())
    guild=NS(id=1000,owner_id=1,me=NS(id=999,top_role=60,guild_permissions=discord.Permissions(manage_roles=True)),fetch_member=AsyncMock(side_effect=lambda ident:moderator if ident==102 else target),get_channel=lambda ident:None)
    class Role(int):pass
    role=Role(25);role.id=77;role.guild=guild;role.managed=False;role.is_default=lambda:False;role.permissions=discord.Permissions(administrator=True)
    ctx=NS(guild=guild,author=moderator,send=AsyncMock())
    with pytest.raises(DomainError):await cog.role_change(ctx,target,role,True)
    target.add_roles.assert_not_awaited()
    role.permissions=discord.Permissions()
    await cog.role_change(ctx,target,role,True)
    target.add_roles.assert_awaited_once()
    await cog.role_change(ctx,target,role,False)
    target.remove_roles.assert_awaited_once()
    await bot.close()


async def test_setup_permissions_and_saved_destinations(db,core,owner,tmp_path,monkeypatch):
    bot=await new_bot(db,tmp_path);cog=bot.get_cog('Utility')
    module=importlib.import_module('nex.cogs.utility');monkeypatch.setattr(module,'actor',lambda ctx:owner)
    guild=NS(id=1000,me=NS(guild_permissions=discord.Permissions(kick_members=True)))
    channel=NS(id=77,guild=guild,mention='<#77>')
    role=NS(id=21,guild=guild,is_default=lambda:False)
    ctx=NS(guild=guild,author=NS(id=100),send=AsyncMock())
    await type(cog).ticketsetup.callback(cog,ctx,channel,role)
    await type(cog).giveawaysetup.callback(cog,ctx,channel)
    await type(cog).channelsetup.callback(cog,ctx,'logs',channel)
    await type(cog).leavesetup.callback(cog,ctx,channel,True,message='Bye {name}')
    cfg=core.config(1000)
    assert cfg['ticket_category']==77 and 21 in cfg['staff_roles'] and cfg['giveaway_channel']==77 and cfg['log_channel']==77 and cfg['restrict_rejoin']
    monkeypatch.setattr(module,'actor',lambda ctx:Actor(101,1000,administrator=True))
    with pytest.raises(DomainError):await type(cog).channelsetup.callback(cog,ctx,'shop',channel)
    await bot.close()


async def test_discord_autocomplete_dispatch_uses_bound_cog(db,core,paid,tmp_path):
    bot=await new_bot(db,tmp_path)
    interaction=NS(guild_id=1000,user=NS(id=200),response=NS(is_done=lambda:False,autocomplete=AsyncMock()))
    await bot.tree.get_command('productpublish')._invoke_autocomplete(interaction,'product_id',NS(product_id=''))
    assert interaction.response.autocomplete.await_args.args[0][0].value==paid.code
    await bot.close()
