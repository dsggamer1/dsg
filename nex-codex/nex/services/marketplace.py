from datetime import timedelta
from sqlalchemy import select, func, or_
from ..models import Product, Order, Entitlement, Hosting, Restriction, now
from ..schemas import ProductInput
from ..security import DomainError, product_path
from .core import config, audit


class Marketplace:
    def __init__(self, db, product_root):
        self.db, self.product_root = db, product_root

    @staticmethod
    def resolve(session, guild_id, identifier):
        return session.scalar(select(Product).where(Product.guild_id==guild_id, or_(Product.id==identifier,Product.code==identifier.lower())))

    def change_code(self, actor, identifier, new_code):
        import re
        actor.require_owner()
        new_code=new_code.lower().strip()
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,15}',new_code):
            raise DomainError('Use 3–16 lowercase letters, numbers, hyphens or underscores.')
        with self.db.transaction() as s:
            product=self.resolve(s,actor.guild_id,identifier)
            if not product:
                raise DomainError('Product not found.')
            duplicate=s.scalar(select(Product).where(Product.guild_id==actor.guild_id,Product.code==new_code,Product.id!=product.id))
            if duplicate:
                raise DomainError('This product ID is already in use.')
            old=product.code
            product.code=new_code
            audit(s,actor,'product.id',product.id,old=old,new=new_code)
            return product

    def save_product(self, actor, data, product_id=None):
        actor.require_owner()
        data = ProductInput.model_validate(data).model_dump()
        with self.db.transaction() as s:
            actor.require_owner()
            product = self.resolve(s, actor.guild_id, product_id) if product_id else Product(guild_id=actor.guild_id)
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
        if not 1 <= page <= 10000:
            raise DomainError('Choose a page from 1 to 10000.')
        with self.db.sessions() as s:
            statement = select(Product).where(Product.category.in_(['template', 'bot']))
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
            p = self.resolve(s, actor.guild_id, product_id)
            if not p:
                raise DomainError('This product is unavailable.')
            product_id = p.id
            existing = s.scalar(select(Order).where(Order.guild_id == actor.guild_id, Order.user_id == actor.user_id, Order.request_key == request_key))
            if existing:
                if existing.product_id != product_id:
                    raise DomainError('Request identifier already used.')
                return existing
            p = s.get(Product, product_id)
            if not p or p.category not in ('template', 'bot') or p.guild_id != actor.guild_id or not p.published or p.archived or not p.available:
                raise DomainError('This product is unavailable.')
            if expected_terms is not None and (p.price, p.currency, p.terms, p.name) != expected_terms:
                raise DomainError('Product terms changed. Please confirm the updated product.')
            cfg = config(s, actor.guild_id)
            entitlement = s.scalar(select(Entitlement).where(Entitlement.guild_id == actor.guild_id, Entitlement.user_id == actor.user_id, Entitlement.product_id == p.id))
            if entitlement:
                raise DomainError('You already own this product. Use your existing order for delivery.')
            pending = s.scalar(select(Order).where(Order.guild_id == actor.guild_id, Order.user_id == actor.user_id, Order.product_id == p.id, Order.state.not_in(['cancelled'])))
            if pending:
                raise DomainError(f'An order already exists: {pending.id}')
            if p.price == 0:
                restriction = s.scalar(select(Restriction).where(Restriction.guild_id == actor.guild_id, Restriction.user_id == actor.user_id, Restriction.active.is_(True)))
                if restriction:
                    raise DomainError('Free claims restricted. Open a support ticket to request a review.')
                claims = list(s.scalars(select(Order).where(Order.guild_id == actor.guild_id, Order.user_id == actor.user_id, Order.amount == 0, Order.state.not_in(['cancelled'])).order_by(Order.created_at.desc())))
                if len(claims) >= min(cfg['free_claim_limit'], p.claim_limit):
                    raise DomainError('Free claim limit reached. Contact staff for review.')
                if claims and claims[0].created_at + timedelta(seconds=max(cfg['free_claim_cooldown'], p.cooldown_seconds)) > now():
                    raise DomainError('Please wait until your free claim cooldown ends.')
            order = Order(guild_id=actor.guild_id, user_id=actor.user_id, product_id=p.id, amount=p.price, currency=p.currency, request_key=request_key, state='ready' if p.price == 0 else 'awaiting_staff', snapshot={key: getattr(p, key) for key in ('name', 'terms', 'delivery_kind', 'delivery_value')})
            s.add(order)
            s.flush()
            if not p.price:
                self._entitle(s, order)
            audit(s, actor, 'order.create', order.id, amount=p.price, free=p.price == 0)
            return order

    @staticmethod
    def _entitle(s, order):
        s.add(Entitlement(guild_id=order.guild_id, user_id=order.user_id, product_id=order.product_id, order_id=order.id))

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



    def fulfill(self, actor, order_id, reason):
        actor.require_owner()
        if not reason.strip() or len(reason) > 500:
            raise DomainError('Provide a reason of 1–500 characters.')
        with self.db.transaction() as s:
            order = s.get(Order, order_id)
            if not order or order.guild_id != actor.guild_id:
                raise DomainError('Order not found.')
            if order.snapshot.get('delivery_kind') == 'hosting':
                raise DomainError('Hosting is no longer offered.')
            if order.state != 'awaiting_staff':
                raise DomainError('Only orders awaiting staff can be released; this order is already handled.')
            self._entitle(s, order)
            order.state = 'ready'
            audit(s, actor, 'order.release', order.id, reason=reason.strip())
            return order

    def change_order(self, actor, order_id, state, reason):
        if state != 'cancelled' or not reason.strip() or len(reason) > 500:
            raise DomainError('Choose cancelled and provide a reason of 1–500 characters.')
        with self.db.transaction() as s:
            order = self.scoped_order(s, actor, order_id, staff=True)
            if order.state == 'cancelled':
                raise DomainError('This order is already cancelled.')
            order.state = state
            e = s.scalar(select(Entitlement).where(Entitlement.order_id == order.id))
            if e:
                s.delete(e)
            hosting = s.scalar(select(Hosting).where(Hosting.order_id == order.id))
            if hosting:
                hosting.state = 'cancelled'
            audit(s, actor, 'order.cancelled', order.id, reason=reason)

    def delivery(self, actor, order_id):
        with self.db.sessions() as s:
            order = self.scoped_order(s, actor, order_id)
            entitlement = s.scalar(select(Entitlement).where(Entitlement.order_id == order.id, Entitlement.user_id == actor.user_id))
            if order.state not in ('ready', 'delivered') or not entitlement:
                raise DomainError('Delivery requires released product access and an active entitlement.')
            result = dict(order.snapshot)
            if result['delivery_kind'] == 'hosting':
                raise DomainError('Hosting is no longer offered. Contact staff about this historical order.')
            if result['delivery_kind'] == 'file':
                result['path'] = product_path(self.product_root, result['delivery_value'])
            return result

    def delivered(self, actor, order_id):
        with self.db.transaction() as s:
            order = self.scoped_order(s, actor, order_id)
            if order.state == 'delivered':
                return
            if order.state != 'ready':
                raise DomainError('Delivery cannot be completed in this state.')
            order.state, order.delivered_at = 'delivered', now()
            audit(s, actor, 'order.delivered', order.id)
