from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consumer_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="ck_products_price_nonnegative"),
        CheckConstraint("stock >= 0", name="ck_products_stock_nonnegative"),
    )


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", lazy="selectin", order_by="OrderItem.id")
    __table_args__ = (
        CheckConstraint("status IN ('pending','confirmed','shipped','delivered','cancelled')", name="ck_orders_status"),
        CheckConstraint("total_amount >= 0", name="ck_orders_total_nonnegative"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    order: Mapped[Order] = relationship(back_populates="items")
    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_order_item_product"),
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    __table_args__ = (UniqueConstraint("customer_id", "key", name="uq_idempotency_customer_key"),)

