from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from nex.models import Premium, Reward, Review, Giveaway, Entry, Hosting, Order, now
from nex.security import Actor, DomainError, product_path, safe_https, check_hierarchy, RateLimiter
from nex.services.community import Community
from nex.services.tickets import Tickets, ticket_overwrites
from nex.services.automod import Automod
from nex.schemas import GuildConfig


def test_premium_expiry_lifetime_extend_and_auth(db, core, owner, buyer):
    with pytest.raises(DomainError):
        core.premium(buyer, buyer.user_id, 'pro', 30)
    core.premium(owner, buyer.user_id, 'pro', 1)
    assert core.has_premium(1000, 200)
    with db.transaction() as s:
        row = s.scalar(select(Premium))
        row.expires_at = now()-timedelta(seconds=1)
    assert not core.has_premium(1000, 200)
    core.premium(owner, 200, 'pro', 2, extend=True)
    assert core.has_premium(1000, 200)
    core.premium(owner, 200, 'pro', None)
    assert core.has_premium(1000, 200)
    with pytest.raises(DomainError):
        core.premium(owner, 200, 'pro', 1, extend=True)
    core.premium(owner, 200, 'pro', revoke=True)
    assert not core.has_premium(1000, 200)
    with db.sessions() as s:
        assert s.scalar(select(func.count()).select_from(Premium)) == 1


def test_free_claim_limit_restriction_and_cooldown(core, market, free, owner, buyer):
    core.restrict(owner, buyer.user_id, 'Staff review of repeated claim attempts')
    with pytest.raises(DomainError, match='restricted'):
        market.order(buyer, free.id, 'one')
    core.restrict(owner, buyer.user_id, 'Appeal accepted', active=False)
    market.order(buyer, free.id, 'two')
    second = market.save_product(owner, {'name':'Second template', 'category':'template', 'published':True, 'delivery_value':'test', 'cooldown_seconds':0})
    core.configure(owner, {'free_claim_cooldown':3600})
    with pytest.raises(DomainError, match='cooldown'):
        market.order(buyer, second.id, 'three')
    core.configure(owner, {'free_claim_cooldown':0, 'free_claim_limit':1})
    with pytest.raises(DomainError, match='limit'):
        market.order(buyer, second.id, 'four')


def test_referral_eligibility_and_duplicate_reward(db, core, market, free, owner, buyer):
    c = Community(db)
    with pytest.raises(DomainError):
        c.refer(buyer, buyer.user_id)
    with pytest.raises(DomainError, match='disabled'):
        c.refer(buyer, 999)
    core.configure(owner, {'rewards_enabled':True})
    with pytest.raises(DomainError, match='Claim or purchase'):
        c.refer(buyer, 999)
    market.order(buyer, free.id, 'one')
    c.refer(buyer, 999)
    with pytest.raises(DomainError):
        c.refer(buyer, 888)
    with db.sessions() as s:
        assert s.scalar(select(func.sum(Reward.points))) == 10
    with pytest.raises(IntegrityError):
        with db.transaction() as s:
            s.add(Reward(guild_id=1000,user_id=999,points=10,event_key='referral:1000:200'))


def test_review_eligibility_and_duplicate(db, core, market, free, owner, buyer):
    c = Community(db)
    with pytest.raises(DomainError):
        c.review(buyer, free.id, 5, 'Great')
    market.order(buyer, free.id, 'one')
    core.configure(owner, {'reviews_allow_free':False})
    with pytest.raises(DomainError):
        c.review(buyer, free.id, 5, 'Great')
    core.configure(owner, {'reviews_allow_free':True})
    c.review(buyer, free.id, 5, 'Great')
    with pytest.raises(DomainError):
        c.review(buyer, free.id, 5, 'Duplicate')
    with pytest.raises(DomainError):
        c.review(buyer, free.id, 0, '')


def test_private_ticket_permissions_and_duplicates(db, core, buyer):
    default, customer, bot, staff = [object() for _ in range(4)]
    guild = SimpleNamespace(default_role=default)
    overwrites = ticket_overwrites(guild, customer, bot, [staff])
    assert overwrites[default].view_channel is False
    assert overwrites[customer].view_channel is True
    assert overwrites[staff].view_channel is True
    assert overwrites[bot].manage_channels is True
    assert len(overwrites) == 4
    with pytest.raises(DomainError):
        ticket_overwrites(guild, customer, bot, [default])
    with pytest.raises(DomainError):
        ticket_overwrites(guild, customer, bot, [])
    tickets = Tickets(db)
    one = tickets.reserve(buyer, 'support')
    assert tickets.reserve(buyer, 'support').id == one.id
    with pytest.raises(DomainError):
        tickets.reserve(buyer, 'purchase', 'missing')


def test_no_everyone_as_staff(core, owner):
    with pytest.raises(DomainError):
        core.configure(owner, {'staff_roles':[owner.guild_id]})


def test_path_traversal_and_symlink_escape(tmp_path):
    root = tmp_path/'products'
    root.mkdir()
    (root/'safe.zip').write_bytes(b'test')
    secret = tmp_path/'secret.zip'
    secret.write_bytes(b'secret')
    (root/'link.zip').symlink_to(secret)
    assert product_path(root, 'safe.zip') == root/'safe.zip'
    for path in ('../secret.zip', str(secret), 'link.zip', 'missing.zip'):
        with pytest.raises(DomainError):
            product_path(root, path)


@pytest.mark.parametrize('url', ['http://example.com','https://localhost/x','https://127.0.0.1/a','https://10.0.0.1/a','https://user:secret@example.com','https://example.com:8443/a','javascript:alert(1)'])
def test_unsafe_urls(url):
    with pytest.raises(ValueError):
        safe_https(url)


def test_screenshot_host_allowlist():
    with pytest.raises(ValueError):
        safe_https('https://attacker.example.com/fake.png', attachment=True)


def test_role_hierarchy():
    guild = SimpleNamespace(owner_id=1)
    moderator = SimpleNamespace(id=2,top_role=10)
    target = SimpleNamespace(id=3,top_role=5)
    bot = SimpleNamespace(id=4,top_role=20)
    check_hierarchy(guild, moderator, target, bot)
    target.top_role = 15
    with pytest.raises(DomainError):
        check_hierarchy(guild, moderator, target, bot)
    target.id = 1
    with pytest.raises(DomainError):
        check_hierarchy(guild, moderator, target, bot)


def test_rate_limiter():
    limiter=RateLimiter()
    limiter.check('x',limit=1)
    with pytest.raises(DomainError):
        limiter.check('x',limit=1)
    limiter.check('y',limit=1)


def test_automod_signals_and_defaults():
    cfg = GuildConfig().model_dump()
    assert cfg['automod_action'] == 'log' and not cfg['security_enabled']
    automod = Automod()
    assert automod.inspect(1,2,'ordinary text',0,cfg) == []
    automod.inspect(1,2,'ordinary text',0,cfg)
    assert 'repeated messages' in automod.inspect(1,2,'ordinary text',0,cfg)
    cfg.update(block_invites=True, blocked_domains=['bad.example'])
    assert 'invite link' in automod.inspect(1,3,'https://discord.gg/example',0,cfg)
    assert 'blocked domain' in automod.inspect(1,3,'https://sub.bad.example/test',0,cfg)
    assert 'blocked domain' not in automod.inspect(1,3,'https://notbad.example/test',0,cfg)


def test_persistent_giveaway_draw_and_reroll(db, core, buyer, owner):
    c=Community(db)
    with db.transaction() as s:
        g=Giveaway(guild_id=1000,channel_id=9,prize='Synthetic prize',winner_count=2,ends_at=now()+timedelta(minutes=1))
        s.add(g)
        s.flush()
    c.enter(buyer,g.id)
    with pytest.raises(DomainError):
        c.enter(buyer,g.id)
    with db.transaction() as s:
        s.get(Giveaway,g.id).ends_at=now()-timedelta(seconds=1)
    outcome=c.draw(g.id)
    assert outcome.winners == [200]
    assert c.draw(g.id).winners == [200]
    with pytest.raises(DomainError):
        c.draw(g.id,buyer)
    assert c.draw(g.id,owner).winners == [200]


def test_xp_cooldown(db,core,owner):
    from nex.models import Level
    core.configure(owner,{'leveling_enabled':True})
    c=Community(db)
    for _ in range(10):
        c.xp(1000,200)
    with db.sessions() as s:
        assert s.scalar(select(Level)).xp == 10


def test_hosting_products_no_longer_available(market, owner):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        market.save_product(owner, {'name':'Hosting removed','category':'hosting','delivery_kind':'hosting','price':100,'published':True})


async def test_existing_ticket_repairs_overwrites(db,core,buyer):
    from unittest.mock import AsyncMock
    from nex.models import Ticket
    roles={20:object(),30:object()}
    customer,bot,default=object(),object(),object()
    channel=SimpleNamespace(id=77,edit=AsyncMock())
    guild=SimpleNamespace(default_role=default,me=bot,get_role=roles.get,get_channel=lambda ident:channel if ident==77 else None,text_channels=[],create_text_channel=AsyncMock())
    tickets=Tickets(db)
    row=tickets.reserve(buyer,'support')
    with db.transaction() as s:
        s.get(Ticket,row.id).channel_id=77
    _,result=await tickets.open(buyer,guild,customer)
    assert result==channel
    overwrites=channel.edit.await_args.kwargs['overwrites']
    assert overwrites[default].view_channel is False
    assert overwrites[customer].view_channel is True
    assert all(overwrites[role].view_channel for role in roles.values())
    assert len(overwrites)==5
    guild.create_text_channel.assert_not_awaited()


def test_legacy_hosting_hidden_and_order_blocked(db,core,market,buyer):
    from nex.models import Product
    with db.transaction() as s:
        p=Product(guild_id=1000,name='Legacy hosting',category='hosting',price=100,published=True,delivery_kind='hosting',delivery_value='')
        s.add(p)
        s.flush()
    assert market.browse(1000)==[]
    with pytest.raises(DomainError,match='unavailable'):
        market.order(buyer,p.id,'legacy-order')
