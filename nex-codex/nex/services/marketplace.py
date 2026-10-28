from datetime import timedelta
from sqlalchemy import select, func
from ..models import Product, Order, Payment, Entitlement, Hosting, Restriction, now
from ..schemas import ProductInput
from ..security import DomainError, safe_https, product_path
from .core import config, audit


class Marketplace:
    def __init__(self, db, product_root):
        self.db, self.product_root = db, product_root

    def save_product(self, actor, data, product_id=None):
        data = ProductInput.model_validate(data).model_dump()
        with self.db.transaction() as s:
            actor.require(config(s, actor.guild_id))
            product = s.get(Product, product_id) if product_id else Product(guild_id=actor.guild_id)
            if product is None or product.guild_id != actor.guild_id:
                raise DomainError('Product not found.')
            if data['published'] and data['delivery_kind'] == 'file':
                product_path(self.product_root, data['delivery_value'])
            for key, value in data.items():
                setattr(product, key, value)
            s.add(product)
            s.flush()
            audit(s, actor, 'product.save', product.id)
            return product

    def browse(self, guild_id=None, category=None, query='', page=1, staff=False):
        with self.db.sessions() as s:
            statement = select(Product)
            if not staff:
                statement = statement.where(Product.published.is_(True), Product.archived.is_(False))
            if guild_id is not None:
                statement = statement.where(Product.guild_id == guild_id)
            if category:
                statement = statement.where(Product.category == category)
            if query:
                statement = statement.where(Product.name.ilike('%' + query[:100] + '%'))
            return list(s.scalars(statement.order_by(Product.created_at.desc()).offset((max(1, page)-1)*12).limit(12)))

    def order(self, actor, product_id, request_key, expected_terms=None):
        if not 1 <= len(request_key) <= 80:
            raise DomainError('Invalid request identifier.')
        with self.db.transaction() as s:
            existing = s.scalar(select(Order).where(Order.guild_id == actor.guild_id, Order.user_id == actor.user_id, Order.request_key == request_key))
            if existing:
                if existing.product_id != product_id:
                    raise DomainError('Request identifier already used.')
                return existing
            p = s.get(Product, product_id)
            if not p or p.guild_id != actor.guild_id or not p.published or p.archived or not p.available:
                raise DomainError('This product is unavailable.')
            if expected_terms is not None and (p.price, p.currency, p.terms, p.name) != expected_terms:
                raise DomainError('Product terms changed. Please confirm the updated product.')
            cfg = config(s, actor.guild_id)
            if p.price and (not cfg['upi_id'] or not cfg['qr_url'] or not cfg['payee']):
                raise DomainError('Payments are not configured. Ask server staff to configure UPI, QR and payee details.')
            if p.price and cfg['currency'] != p.currency:
                raise DomainError('Product and payment currencies do not match. Contact staff.')
            entitlement = s.scalar(select(Entitlement).where(Entitlement.guild_id == actor.guild_id, Entitlement.user_id == actor.user_id, Entitlement.product_id == p.id))
            if entitlement:
                raise DomainError('You already own this product. Use your existing order for delivery.')
            pending = s.scalar(select(Order).where(Order.guild_id == actor.guild_id, Order.user_id == actor.user_id, Order.product_id == p.id, Order.state.not_in(['cancelled', 'manually_refunded'])))
            if pending:
                raise DomainError(f'An order already exists: {pending.id}')
            if p.price == 0:
                restriction = s.scalar(select(Restriction).where(Restriction.guild_id == actor.guild_id, Restriction.user_id == actor.user_id, Restriction.active.is_(True)))
                if restriction:
                    raise DomainError('Free claims restricted. Open a support ticket to request a review.')
                claims = list(s.scalars(select(Order).where(Order.guild_id == actor.guild_id, Order.user_id == actor.user_id, Order.amount == 0, Order.state.not_in(['cancelled', 'manually_refunded'])).order_by(Order.created_at.desc())))
                if len(claims) >= min(cfg['free_claim_limit'], p.claim_limit):
                    raise DomainError('Free claim limit reached. Contact staff for review.')
                if claims and claims[0].created_at + timedelta(seconds=max(cfg['free_claim_cooldown'], p.cooldown_seconds)) > now():
                    raise DomainError('Please wait until your free claim cooldown ends.')
            order = Order(guild_id=actor.guild_id, user_id=actor.user_id, product_id=p.id, amount=p.price, currency=p.currency, request_key=request_key, state='paid' if p.price == 0 else 'pending_payment', snapshot={key: getattr(p, key) for key in ('name', 'terms', 'delivery_kind', 'delivery_value', 'duration_days', 'capacity')})
            s.add(order)
            s.flush()
            if not p.price:
                self._entitle(s, order)
            audit(s, actor, 'order.create', order.id, amount=p.price, free=p.price == 0)
            return order

    @staticmethod
    def _entitle(s, order):
        s.add(Entitlement(guild_id=order.guild_id, user_id=order.user_id, product_id=order.product_id, order_id=order.id))
        if order.snapshot['delivery_kind'] == 'hosting':
            s.add(Hosting(order_id=order.id))

    @staticmethod
    def scoped_order(s, actor, order_id, staff=False):
        order = s.get(Order, order_id)
        if not order or order.guild_id != actor.guild_id:
            raise DomainError('Order not found.')
        if staff:
            actor.require(config(s, actor.guild_id))
        elif order.user_id != actor.user_id:
            raise DomainError('Order not found.')
        return order

    def submit_payment(self, actor, order_id, screenshot, reference=''):
        safe_https(screenshot, attachment=True)
        if len(reference) > 120 or len(screenshot) > 2000:
            raise DomainError('Payment submission is too long.')
        with self.db.transaction() as s:
            order = self.scoped_order(s, actor, order_id)
            if order.state not in ('pending_payment', 'rejected'):
                raise DomainError('This order is not accepting payment submissions.')
            payment = Payment(order_id=order.id, screenshot=screenshot, reference=reference)
            s.add(payment)
            order.state = 'payment_submitted'
            audit(s, actor, 'payment.submit', order.id)
            s.flush()
            return payment

    def review_payment(self, actor, order_id, approve, reason=''):
        with self.db.transaction() as s:
            actor.require(config(s, actor.guild_id), 'payment')
            order = s.get(Order, order_id)
            if not order or order.guild_id != actor.guild_id:
                raise DomainError('Order not found.')
            if order.user_id == actor.user_id:
                raise DomainError('You cannot review your own payment.')
            if order.state not in ('payment_submitted', 'verification_required'):
                raise DomainError('This payment has already been decided or has no submission.')
            if len(reason) > 500 or not approve and not reason.strip():
                raise DomainError('A rejection reason of 1–500 characters is required.')
            payment = s.scalar(select(Payment).where(Payment.order_id == order.id, Payment.state == 'submitted').order_by(Payment.created_at.desc()))
            if not payment:
                raise DomainError('No pending payment submission.')
            payment.state = 'approved' if approve else 'rejected'
            payment.reviewer_id, payment.reviewed_at, payment.reason = actor.user_id, now(), reason
            order.state = 'paid' if approve else 'rejected'
            if approve:
                self._entitle(s, order)
            audit(s, actor, 'payment.approve' if approve else 'payment.reject', order.id, reason=reason)
            return order

    def change_order(self, actor, order_id, state, reason):
        if state not in ('cancelled', 'manually_refunded') or not reason.strip() or len(reason) > 500:
            raise DomainError('Choose cancelled or manually_refunded and provide a reason.')
        with self.db.transaction() as s:
            order = self.scoped_order(s, actor, order_id, staff=True)
            if state == 'cancelled' and order.state not in ('pending_payment', 'rejected', 'payment_submitted', 'verification_required'):
                raise DomainError('Only unpaid orders may be cancelled.')
            if state == 'manually_refunded' and (order.amount == 0 or order.state not in ('paid', 'delivered')):
                raise DomainError('Only paid orders may be recorded as manually refunded.')
            order.state = state
            e = s.scalar(select(Entitlement).where(Entitlement.order_id == order.id))
            if e:
                s.delete(e)
            hosting = s.scalar(select(Hosting).where(Hosting.order_id == order.id))
            if hosting:
                hosting.state = 'cancelled'
            audit(s, actor, 'order.' + state, order.id, reason=reason)

    def delivery(self, actor, order_id):
        with self.db.sessions() as s:
            order = self.scoped_order(s, actor, order_id)
            entitlement = s.scalar(select(Entitlement).where(Entitlement.order_id == order.id, Entitlement.user_id == actor.user_id))
            if order.state not in ('paid', 'delivered') or not entitlement:
                raise DomainError('Delivery requires verified payment and an active entitlement.')
            result = dict(order.snapshot)
            if result['delivery_kind'] == 'file':
                result['path'] = product_path(self.product_root, result['delivery_value'])
            return result

    def delivered(self, actor, order_id):
        with self.db.transaction() as s:
            order = self.scoped_order(s, actor, order_id)
            if order.state == 'delivered':
                return
            if order.state != 'paid':
                raise DomainError('Delivery cannot be completed in this state.')
            order.state, order.delivered_at = 'delivered', now()
            audit(s, actor, 'order.delivered', order.id)
