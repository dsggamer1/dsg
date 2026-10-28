"""Payment removal, safe legacy migration and manual product release boundaries."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import importlib
import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from nex.models import Base, Entitlement, Guild, Order, SchemaVersion
from nex.schemas import GuildConfig
from nex.security import Actor, DomainError
from tests.test_commands_and_storefront import new_bot


async def test_no_payment_commands_services_models_or_configuration(db,core,tmp_path):
    bot=await new_bot(db,tmp_path)
    assert not {'payment','paymentsetup','paymentreview'}.intersection(c.name for c in bot.tree.get_commands())
    assert len(bot.tree.get_commands())==41
    assert 'payments' not in Base.metadata.tables and 'payments' not in inspect(db.engine).get_table_names()
    assert not hasattr(bot.market,'submit_payment') and not hasattr(bot.market,'review_payment')
    keys={'upi_id','qr_url','payee','payment_roles','payment_instructions'}
    assert not keys.intersection(GuildConfig.model_fields)
    assert not keys.intersection(core.config(1000))
    await bot.close()


@pytest.mark.parametrize('key',['upi_id','qr_url','payee','payment_roles','payment_instructions'])
def test_old_config_ignored_and_cannot_be_reenabled(db,core,owner,key):
    with db.transaction() as s:
        row=s.get(Guild,1000)
        row.settings={**row.settings,key: 'obsolete'}
    assert key not in core.config(1000)
    with pytest.raises(ValidationError):core.configure(owner,{key:'obsolete'})


def test_priced_order_needs_no_payment_setup_but_stays_locked(db,market,paid,buyer,owner):
    order=market.order(buyer,paid.code,'no-payment')
    assert order.state=='awaiting_staff'
    with pytest.raises(DomainError):market.delivery(buyer,order.id)
    with db.sessions() as s:assert s.scalar(select(Entitlement)) is None
    market.fulfill(owner,order.id,'Manually completed request')
    assert market.delivery(buyer,order.id)['name']==paid.name
    with pytest.raises(DomainError):market.fulfill(owner,order.id,'Duplicate')


@pytest.mark.parametrize('actor',[Actor(201,1000),Actor(201,1000,administrator=True),Actor(201,1000,frozenset({20})),Actor(100,2000,owner=True)])
def test_unauthorized_release_never_unlocks(market,paid,buyer,actor):
    order=market.order(buyer,paid.id,'protected')
    with pytest.raises(DomainError):market.fulfill(actor,order.id,'Attempt')
    with pytest.raises(DomainError):market.delivery(buyer,order.id)


def test_cancelled_order_cannot_be_released(market,paid,buyer,owner):
    order=market.order(buyer,paid.id,'cancel')
    market.change_order(owner,order.id,'cancelled','Customer withdrew')
    with pytest.raises(DomainError):market.fulfill(owner,order.id,'Too late')
    with pytest.raises(DomainError):market.change_order(owner,order.id,'manually_refunded','Removed action')


def test_schema2_upgrade_preserves_old_access_without_unlocking_pending(db,core,market,owner,buyer):
    from nex.models import Product
    states=['pending_payment','payment_submitted','verification_required','rejected','paid','paid','delivered','manually_refunded']
    ids=[]
    with db.transaction() as s:
        s.get(SchemaVersion,1).version=2
        s.execute(text('CREATE TABLE payments (id TEXT PRIMARY KEY, reference TEXT)'))
        s.execute(text("INSERT INTO payments VALUES ('old', 'preserve historical record')"))
        for i,state in enumerate(states):
            p=Product(guild_id=1000,name=f'Legacy {i}',category='bot',delivery_value='Private content')
            s.add(p);s.flush()
            order=Order(guild_id=1000,user_id=200,product_id=p.id,amount=100,currency='INR',state=state,request_key=str(i),snapshot={'name':p.name,'delivery_kind':'instructions','delivery_value':'Private content'})
            s.add(order);s.flush();ids.append(order.id)
            if i in (4,6):s.add(Entitlement(guild_id=1000,user_id=200,product_id=p.id,order_id=order.id))
    db.initialize();db.initialize()
    with db.sessions() as s:
        assert [s.get(Order,k).state for k in ids]==['awaiting_staff']*4+['ready','awaiting_staff','delivered','cancelled']
        assert s.execute(text('SELECT reference FROM payments')).scalar()=='preserve historical record'
        assert s.get(SchemaVersion,1).version==3
    for i in (0,1,2,3,5,7):
        with pytest.raises(DomainError):market.delivery(buyer,ids[i])
    for i in (4,6):assert market.delivery(buyer,ids[i])['delivery_value']=='Private content'


async def test_purchase_ticket_has_no_payment_details(db,core,paid,buyer,tmp_path):
    bot=await new_bot(db,tmp_path);cog=bot.get_cog('Commerce')
    order=bot.market.order(buyer,paid.id,'ticket-without-payment')
    channel=NS(id=88,mention='<#88>',send=AsyncMock())
    bot.tickets.open=AsyncMock(return_value=(NS(),channel))
    reply=AsyncMock()
    await cog.send_purchase_ticket(NS(id=1000),NS(id=200),buyer,order,reply)
    bot.tickets.open.assert_awaited_once()
    body=str(channel.send.await_args.kwargs['embed'].to_dict())
    assert order.id in body and 'owner releases' in body
    assert not any(x in body for x in ('UPI','QR','/payment','Payee','receipt'))
    await bot.close()


async def test_owner_release_command_confirmation_and_access(db,core,paid,buyer,owner,tmp_path,monkeypatch):
    bot=await new_bot(db,tmp_path);cog=bot.get_cog('Commerce')
    module=importlib.import_module('nex.cogs.commerce')
    monkeypatch.setattr(module,'actor',lambda ctx:owner)
    confirm=AsyncMock(return_value=False);monkeypatch.setattr(module,'confirm',confirm)
    ctx=NS(send=AsyncMock());order=bot.market.order(buyer,paid.id,'release-command')
    await type(cog).orderfulfill.callback(cog,ctx,order.id,reason='Request complete')
    with pytest.raises(DomainError):bot.market.delivery(buyer,order.id)
    confirm.return_value=True
    await type(cog).orderfulfill.callback(cog,ctx,order.id,reason='Request complete')
    assert bot.market.delivery(buyer,order.id)['name']==paid.name
    await bot.close()
