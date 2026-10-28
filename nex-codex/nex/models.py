"""Portable schema. Discord snowflakes use BIGINT, monetary values use integer minor units."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def uid():
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class Guild(Base):
    __tablename__ = 'guilds'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class Product(Base):
    __tablename__ = 'products'
    __table_args__ = (CheckConstraint('price >= 0'), CheckConstraint('claim_limit >= 1'))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    code: Mapped[str] = mapped_column(String(16), default=lambda: uid()[:8])
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default='')
    category: Mapped[str] = mapped_column(String(20))
    price: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default='INR')
    thumbnail: Mapped[str] = mapped_column(Text, default='')
    terms: Mapped[str] = mapped_column(Text, default='')
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    delivery_kind: Mapped[str] = mapped_column(String(20), default='instructions')
    delivery_value: Mapped[str] = mapped_column(Text, default='')
    claim_limit: Mapped[int] = mapped_column(Integer, default=10)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=86400)
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    capacity: Mapped[str] = mapped_column(String(200), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Order(Base):
    __tablename__ = 'orders'
    __table_args__ = (CheckConstraint('amount >= 0'), UniqueConstraint('guild_id', 'user_id', 'request_key'))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'))
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    state: Mapped[str] = mapped_column(String(30), default='pending_payment', index=True)
    request_key: Mapped[str] = mapped_column(String(80))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)


class Ticket(Base):
    __tablename__ = 'tickets'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    category: Mapped[str] = mapped_column(String(30))
    order_id: Mapped[str | None] = mapped_column(ForeignKey('orders.id'), unique=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    active_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    state: Mapped[str] = mapped_column(String(20), default='creating')
    staff_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'), index=True)
    screenshot: Mapped[str] = mapped_column(Text)
    reference: Mapped[str] = mapped_column(String(120), default='')
    state: Mapped[str] = mapped_column(String(20), default='submitted')
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(500), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Entitlement(Base):
    __tablename__ = 'entitlements'
    __table_args__ = (UniqueConstraint('guild_id', 'user_id', 'product_id'),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'))
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Hosting(Base):
    """Historical order cleanup only; no hosting sales or provisioning."""
    __tablename__ = 'hosting'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id'), unique=True)
    state: Mapped[str] = mapped_column(String(20), default='queued')
    notes: Mapped[str] = mapped_column(Text, default='')
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)


class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    actor_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(60), index=True)
    target: Mapped[str] = mapped_column(String(120), default='')
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Restriction(Base):
    __tablename__ = 'restrictions'
    __table_args__ = (UniqueConstraint('guild_id', 'user_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Giveaway(Base):
    __tablename__ = 'giveaways'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    prize: Mapped[str] = mapped_column(String(200))
    winner_count: Mapped[int] = mapped_column(Integer)
    ends_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    state: Mapped[str] = mapped_column(String(20), default='open')
    winners: Mapped[list] = mapped_column(JSON, default=list)
    announced: Mapped[bool] = mapped_column(Boolean, default=False)


class Entry(Base):
    __tablename__ = 'entries'
    __table_args__ = (UniqueConstraint('giveaway_id', 'user_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    giveaway_id: Mapped[str] = mapped_column(ForeignKey('giveaways.id'))
    user_id: Mapped[int] = mapped_column(BigInteger)


class Heartbeat(Base):
    __tablename__ = 'heartbeat'
    name: Mapped[str] = mapped_column(String(20), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class SchemaVersion(Base):
    __tablename__ = 'schema_version'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer)

Index('ix_entitlement_customer', Entitlement.guild_id, Entitlement.user_id)


class Moderation(Base):
    __tablename__ = 'moderation'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    moderator_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class RejoinBlock(Base):
    __tablename__ = 'rejoin_blocks'
    __table_args__ = (UniqueConstraint('guild_id', 'user_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


Index('uq_product_guild_code', Product.guild_id, Product.code, unique=True)
