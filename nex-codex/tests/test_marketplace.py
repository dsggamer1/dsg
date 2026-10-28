from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, func
import pytest
from pydantic import ValidationError
from nex.security import Actor, DomainError
from nex.models import Order, Payment, Entitlement, Audit, Product, Hosting
from nex.schemas import ProductInput

RECEIPT = 'https://cdn.discordapp.com/attachments/123/456/synthetic.png'


def submit(market, buyer, paid):
    order = market.order(buyer, paid.id, 'request-1')
    market.submit_payment(buyer, order.id, RECEIPT)
    return order


def test_paid_flow_snapshots_and_delivery(db, market, paid, buyer, owner):
    order = submit(market, buyer, paid)
    with pytest.raises(DomainError):
        market.delivery(buyer, order.id)
    data = ProductInput.model_validate({key: getattr(paid, key) for key in ProductInput.model_fields}).model_dump()
    data.update(price=99900, delivery_value='Changed delivery')
    market.save_product(owner, data, paid.id)
    approved = market.review_payment(Actor(300, 1000, frozenset({30})), order.id, True)
    assert approved.amount == 49900
    assert market.delivery(buyer, order.id)['delivery_value'] == 'Synthetic delivery instructions'
    market.delivered(buyer, order.id)
    market.delivered(buyer, order.id)
    with db.sessions() as s:
        assert s.get(Order, order.id).state == 'delivered'
        assert s.scalar(select(func.count()).select_from(Entitlement)) == 1
        assert s.scalar(select(func.count()).select_from(Audit).where(Audit.action == 'order.delivered')) == 1
        payment = s.scalar(select(Payment))
        assert payment.reviewer_id == 300 and payment.reviewed_at


@pytest.mark.parametrize('reviewer', [Actor(201, 1000), Actor(201, 2000, administrator=True), Actor(200, 1000, administrator=True), Actor(201, 1000, frozenset({20}))])
def test_review_authorization(market, paid, buyer, reviewer):
    order = submit(market, buyer, paid)
    with pytest.raises(DomainError):
        market.review_payment(reviewer, order.id, True)


def test_approval_race_only_one_succeeds(db, market, paid, buyer, owner):
    order = submit(market, buyer, paid)
    def approve(_):
        try:
            market.review_payment(owner, order.id, True)
            return True
        except DomainError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(approve, range(4)))
    assert sum(outcomes) == 1
    with db.sessions() as s:
        assert s.scalar(select(func.count()).select_from(Entitlement)) == 1


def test_idempotent_creation_and_duplicate_order(market, paid, buyer):
    first = market.order(buyer, paid.id, 'request-1')
    assert market.order(buyer, paid.id, 'request-1').id == first.id
    with pytest.raises(DomainError):
        market.order(buyer, paid.id, 'request-2')


def test_concurrent_free_claims(db, market, free, buyer):
    def claim(i):
        try:
            return market.order(buyer, free.id, f'claim-{i}').id
        except DomainError:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(claim, range(4)))
    assert sum(bool(x) for x in outcomes) == 1


def test_reject_requires_reason_and_allows_resubmit(market, paid, buyer, owner):
    order = submit(market, buyer, paid)
    with pytest.raises(DomainError):
        market.review_payment(owner, order.id, False)
    market.review_payment(owner, order.id, False, 'No matching transaction found')
    with pytest.raises(DomainError):
        market.delivery(buyer, order.id)
    market.submit_payment(buyer, order.id, RECEIPT, 'new-reference')
    market.review_payment(owner, order.id, True)
    with pytest.raises(DomainError):
        market.review_payment(owner, order.id, True)
    with pytest.raises(DomainError):
        market.submit_payment(buyer, order.id, RECEIPT)


def test_other_customer_cannot_submit_or_download(market, paid, buyer, owner):
    order = submit(market, buyer, paid)
    other = Actor(777, 1000)
    with pytest.raises(DomainError):
        market.submit_payment(other, order.id, RECEIPT)
    market.review_payment(owner, order.id, True)
    with pytest.raises(DomainError):
        market.delivery(other, order.id)
    with pytest.raises(DomainError):
        market.delivery(Actor(buyer.user_id, 9999), order.id)


def test_missing_payment_setup_and_currency(market, core, paid, buyer, owner):
    core.configure(owner, {'upi_id': ''})
    with pytest.raises(DomainError, match='not configured'):
        market.order(buyer, paid.id, 'one')
    core.configure(owner, {'upi_id': 'synthetic@example', 'currency': 'USD'})
    with pytest.raises(DomainError, match='currencies'):
        market.order(buyer, paid.id, 'two')


def test_confirmation_terms_checked_inside_transaction(market, paid, buyer):
    with pytest.raises(DomainError, match='terms changed'):
        market.order(buyer, paid.id, 'one', expected_terms=(1, paid.currency, paid.terms, paid.name))


def test_manual_refund_revokes_access(market, paid, buyer, owner):
    order = submit(market, buyer, paid)
    market.review_payment(owner, order.id, True)
    with pytest.raises(DomainError):
        market.change_order(owner, order.id, 'cancelled', 'wrong')
    market.change_order(owner, order.id, 'manually_refunded', 'Staff completed external transfer')
    with pytest.raises(DomainError):
        market.delivery(buyer, order.id)


@pytest.mark.parametrize('changes', [{'price': -1}, {'category': 'invalid'}, {'currency': 'usd'}, {'delivery_kind': 'link', 'delivery_value': 'http://example.com'}, {'delivery_kind':'file', 'delivery_value':'../secret'}, {'delivery_kind':'file', 'delivery_value':'/etc/passwd'}, {'category':'hosting', 'delivery_kind':'instructions'}, {'published':True, 'delivery_value':''}])
def test_invalid_product_rejected(market, owner, changes):
    with pytest.raises(ValidationError):
        market.save_product(owner, {'name':'Test product','category':'source', **changes})


def test_product_write_is_staff_scoped(market, paid, buyer):
    with pytest.raises(DomainError):
        market.save_product(buyer, {'name':'Hacked product','category':'source'}, paid.id)
    with pytest.raises(DomainError):
        market.save_product(Actor(500, 999, administrator=True, owner=True), {'name':'Hacked product','category':'source'}, paid.id)


def test_database_reopen_persists(db, market, free, buyer):
    from nex.db import Database
    order = market.order(buyer, free.id, 'persist')
    reopened = Database(str(db.engine.url))
    reopened.initialize()
    with reopened.sessions() as s:
        assert s.get(Order, order.id).user_id == buyer.user_id
    reopened.engine.dispose()
