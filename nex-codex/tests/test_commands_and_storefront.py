"""Command and component tests use Discord mocks; no real account or token is used."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import discord
import pytest
from sqlalchemy import select
from nex.bot import NexBot, prefix
from nex.config import Settings
from nex.models import Guild, Order, Product
from nex.security import Actor, DomainError
from nex.utils.discord import price_minor, safe_role
from nex.utils.storefront import ShopView, CheckoutView
from nex.cogs.commerce import Commerce


async def new_bot(db, tmp_path):
    bot = NexBot(Settings(_env_file=None, product_root=tmp_path, auto_load_emojis=False, sync_commands=False, owner_ids=[100]), db)
    await bot._async_setup_hook()
    await bot.setup_hook()
    return bot


async def test_startup_automatically_registers_commands(db, tmp_path):
    bot = NexBot(Settings(_env_file=None, product_root=tmp_path, auto_load_emojis=False, sync_commands=True, command_guild_ids=[1000]), db)
    bot.tree.sync = AsyncMock(return_value=[])
    async with bot:
        await bot.setup_hook()
        assert bot.tree.sync.await_count == 2
        assert bot.tree.sync.await_args_list[0].kwargs == {}
        assert bot.tree.sync.await_args_list[1].kwargs['guild'].id == 1000
        assert bot.tree.get_command('hosting') is None
        assert bot.tree.get_command('addproduct') is not None
        assert bot.tree.get_command('setup') is not None
        assert bot.tree.get_command('diagnostics') is not None


async def test_prefix_respects_environment_then_guild_override(db, tmp_path):
    bot = NexBot(Settings(_env_file=None, default_prefix='?', auto_load_emojis=False, sync_commands=False), db)
    bot._connection.user = SimpleNamespace(id=999)
    message = SimpleNamespace(guild=SimpleNamespace(id=1000))
    assert (await prefix(bot, message))[-1] == '?'
    with db.transaction() as session:
        session.add(Guild(id=1000, settings={'prefix':'$'}))
    assert (await prefix(bot, message))[-1] == '$'
    await bot.close()


@pytest.mark.parametrize('name,private', [('help',True),('ticket',True),('deliver',True),('paymentreview',True),('broadcast',True),('giveaway',False),('shop',False)])
async def test_slower_slash_commands_are_acknowledged(db,name,private):
    bot = NexBot(Settings(_env_file=None, auto_load_emojis=False, sync_commands=False), db)
    ctx = SimpleNamespace(interaction=SimpleNamespace(response=SimpleNamespace(is_done=lambda:False)),command=SimpleNamespace(name=name),defer=AsyncMock())
    await bot.prepare_command(ctx)
    ctx.defer.assert_awaited_once_with(ephemeral=private)
    ctx.interaction.response.is_done=lambda:True
    await bot.prepare_command(ctx)
    assert ctx.defer.await_count == 1
    await bot.close()


async def test_real_prefix_help_invocation(db,tmp_path,monkeypatch):
    from discord.ext import commands
    bot = await new_bot(db,tmp_path)
    bot._connection.user=discord.ClientUser(state=bot._connection,data={'id':'999','username':'NEX','discriminator':'0','avatar':None,'bot':True})
    channel=SimpleNamespace(id=77,guild=None)
    message=discord.Message(state=bot._connection,channel=channel,data={'id':'555','type':0,'content':'!help','author':{'id':'200','username':'Test','discriminator':'0','avatar':None},'attachments':[],'embeds':[],'mentions':[],'mention_roles':[],'pinned':False,'tts':False,'edited_timestamp':None})
    send=AsyncMock()
    monkeypatch.setattr(commands.Context,'send',send)
    ctx=await bot.get_context(message)
    assert ctx.command.name == 'help'
    await ctx.command.invoke(ctx)
    assert send.await_count==1
    assert send.await_args.kwargs['embed'].title.endswith('Command center')
    await bot.close()


async def test_storefront_checkout_creates_one_free_order(db,core,market,free,buyer,tmp_path):
    bot=await new_bot(db,tmp_path)
    view=ShopView(buyer.user_id,bot,buyer.guild_id)
    assert view.products and view.previous.disabled and view.next_page.disabled
    assert len(view.card()) <= 6000
    product_select=next(c for c in view.children if isinstance(c,discord.ui.Select))
    assert product_select.options[0].value==free.code
    checkout=CheckoutView(buyer.user_id,free)
    message=SimpleNamespace(edit=AsyncMock())
    interaction=SimpleNamespace(id=9999,guild_id=1000,client=bot,user=SimpleNamespace(id=200),response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()),message=message)
    await checkout.confirm_order.callback(interaction)
    with db.sessions() as session:
        order=session.scalar(select(Order))
        assert order.state=='paid' and order.amount==0
    # Discord redelivery of the same interaction must be idempotent.
    await checkout.confirm_order.callback(interaction)
    with db.sessions() as session:
        assert len(list(session.scalars(select(Order)))) == 1
    assert checkout.confirm_order.disabled
    await bot.close()


async def test_another_user_cannot_operate_checkout(free):
    view=CheckoutView(200,free)
    interaction=SimpleNamespace(user=SimpleNamespace(id=999),response=SimpleNamespace(send_message=AsyncMock()))
    assert not await view.interaction_check(interaction)
    interaction.response.send_message.assert_awaited_once()
    view.stop()


async def test_changed_terms_block_button_checkout(db,core,market,paid,buyer,tmp_path):
    bot=await new_bot(db,tmp_path)
    view=CheckoutView(buyer.user_id,paid)
    with db.transaction() as session:
        session.get(Product,paid.id).price=1
    interaction=SimpleNamespace(id=10000,guild_id=1000,client=bot,user=SimpleNamespace(id=200),response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
    with pytest.raises(DomainError,match='terms changed'):
        await view.confirm_order.callback(interaction)
    with db.sessions() as session:
        assert session.scalar(select(Order)) is None
    view.stop()
    await bot.close()


async def test_failed_discord_delivery_does_not_mark_delivered(db,core,market,free,buyer,tmp_path,monkeypatch):
    bot=await new_bot(db,tmp_path)
    order=market.order(buyer,free.id,'delivery-check')
    ctx=SimpleNamespace(guild=SimpleNamespace(id=1000),author=SimpleNamespace(send=AsyncMock(side_effect=discord.Forbidden(SimpleNamespace(status=403,reason='Forbidden'), 'DM closed'))))
    import importlib
    module=importlib.import_module("nex.cogs.commerce")
    monkeypatch.setattr(module,'actor',lambda ctx:buyer)
    with pytest.raises(discord.Forbidden):
        await type(bot.get_cog('Commerce')).deliver.callback(bot.get_cog('Commerce'),ctx,order.id)
    with db.sessions() as session:
        assert session.get(Order,order.id).state=='paid'
        assert session.get(Order,order.id).delivered_at is None
    await bot.close()


async def test_discord_staff_product_management(db,core,owner,tmp_path,monkeypatch):
    bot=await new_bot(db,tmp_path)
    import importlib
    module=importlib.import_module("nex.cogs.commerce")
    monkeypatch.setattr(module,'actor',lambda ctx:owner)
    ctx=SimpleNamespace(guild=SimpleNamespace(id=1000),send=AsyncMock())
    cog=bot.get_cog('Commerce')
    command_type=type(cog)
    await command_type.productadd.callback(cog,ctx,'Premium template','template','499.00','Delivery instructions','Built for communities')
    with db.sessions() as session:
        p=session.scalar(select(Product))
        assert p.price==49900 and not p.published
    await command_type.productedit.callback(cog,ctx,p.id,'terms',value='One server license')
    await command_type.productpublish.callback(cog,ctx,p.id,True)
    with db.sessions() as session:
        p=session.get(Product,p.id)
        assert p.published and p.terms=='One server license'
    monkeypatch.setattr(module,'actor',lambda ctx:Actor(200,1000))
    with pytest.raises(DomainError):
        await command_type.productpublish.callback(cog,ctx,p.id,False)
    await bot.close()


@pytest.mark.parametrize('value,result',[('499.00',49900),('0',0),('12.5',1250),('1e2',10000)])
def test_price_input_is_exact(value,result):
    assert price_minor(value)==result


@pytest.mark.parametrize('value',['NaN','Infinity','-1','0.001','1000001','free'])
def test_price_input_rejects_unsafe_values(value):
    with pytest.raises(DomainError):
        price_minor(value)


@pytest.mark.parametrize('changes',[{'auto_role':20}])
def test_configuration_cannot_self_assign_staff_roles(core,owner,changes):
    with pytest.raises(DomainError,match='Staff and payment'):
        core.configure(owner,changes)


def test_staff_role_rejected_even_without_discord_permission_bits():
    role=SimpleNamespace(id=30)
    with pytest.raises(DomainError,match='Staff and payment'):
        safe_role(None,None,role,[30])




async def test_help_and_storefront_payloads_fit_discord_limits(db,core,tmp_path):
    import importlib
    bot=await new_bot(db,tmp_path)
    module=importlib.import_module('nex.cogs.utility')
    ctx=SimpleNamespace(send=AsyncMock(),author=SimpleNamespace(id=100),guild=SimpleNamespace(id=1000))
    cog=bot.get_cog('Utility')
    await type(cog).help.callback(cog,ctx)
    card=ctx.send.await_args.kwargs['embed']
    assert len(card)<=6000 and len(card.fields)<=25
    select=module.HelpSelect(bot, owner=True)
    interaction=SimpleNamespace(response=SimpleNamespace(defer=AsyncMock()),edit_original_response=AsyncMock())
    for option in select.options:
        select._values=[option.value]
        await select.callback(interaction)
        card=interaction.edit_original_response.await_args.kwargs['embed']
        assert len(card)<=6000 and len(card.fields)<=25
        assert all(len(field.value)<=1024 for field in card.fields)
    for command in bot.tree.get_commands():
        payload=command.to_dict(bot.tree)
        assert 1 <= len(payload['description']) <= 100
        assert len(payload.get('options',[]))<=25
    await bot.close()
