import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Customer, IdempotencyRecord, Order, OrderItem, Product, utc_now
from .schemas import CreateOrder, OrderOut, OrderPage


def get_or_create_customer(db: Session, subject: str) -> Customer:
    customer = db.scalar(select(Customer).where(Customer.consumer_sub == subject))
    if customer:
        return customer
    try:
        with db.begin_nested():
            customer = Customer(consumer_sub=subject)
            db.add(customer)
            db.flush()
        return customer
    except IntegrityError:
        customer = db.scalar(select(Customer).where(Customer.consumer_sub == subject))
        if customer is None:
            raise
        return customer


def order_out(order: Order) -> OrderOut:
    created_at = order.created_at if order.created_at.tzinfo else order.created_at.replace(tzinfo=timezone.utc)
    updated_at = order.updated_at if order.updated_at.tzinfo else order.updated_at.replace(tzinfo=timezone.utc)
    return OrderOut(
        order_id=order.id,
        customer_id=order.customer_id,
        status=order.status,
        total_amount=order.total_amount,
        items=[{"product_id": i.product_id, "quantity": i.quantity, "unit_price": i.unit_price} for i in order.items],
        created_at=created_at,
        updated_at=updated_at,
        cancellation_reason=order.cancellation_reason,
    )


def get_owned_order(db: Session, order_id: int, customer_id: int) -> Order:
    order = db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == customer_id))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def create_order(db: Session, customer_id: int, body: CreateOrder, key: str) -> OrderOut:
    if not key or len(key) > 255 or not key.isascii() or not key.isprintable():
        raise HTTPException(status_code=400, detail="A printable ASCII Idempotency-Key of 1-255 characters is required")
    canonical = sorted((item.product_id, item.quantity) for item in body.items)
    request_hash = hashlib.sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest()
    record = IdempotencyRecord(customer_id=customer_id, key=key, request_hash=request_hash)
    try:
        with db.begin_nested():
            db.add(record)
            db.flush()
    except IntegrityError:
        existing = db.scalar(select(IdempotencyRecord).where(
            IdempotencyRecord.customer_id == customer_id, IdempotencyRecord.key == key
        ))
        if existing is None:
            raise
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency-Key was used with a different order")
        if existing.order_id is None:
            raise HTTPException(status_code=409, detail="Order creation is still in progress")
        return order_out(db.get(Order, existing.order_id))

    priced: list[tuple[int, int, Decimal]] = []
    for product_id, quantity in canonical:
        product = db.scalar(
            update(Product)
            .where(Product.id == product_id, Product.active.is_(True), Product.stock >= quantity)
            .values(stock=Product.stock - quantity)
            .returning(Product)
        )
        if product is None:
            raise HTTPException(status_code=409, detail=f"Product {product_id} is unavailable or has insufficient stock")
        priced.append((product_id, quantity, product.unit_price))

    total = sum((price * quantity for _, quantity, price in priced), Decimal("0.00"))
    order = Order(customer_id=customer_id, status="pending", total_amount=total)
    db.add(order)
    db.flush()
    for product_id, quantity, price in priced:
        db.add(OrderItem(order_id=order.id, product_id=product_id, quantity=quantity, unit_price=price))
    db.flush()
    record.order_id = order.id
    db.flush()
    db.refresh(order, attribute_names=["items"])
    return order_out(order)


def list_orders(
    db: Session,
    customer_id: int,
    status: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    limit: int,
    offset: int,
) -> OrderPage:
    filters = [Order.customer_id == customer_id]
    if status:
        filters.append(Order.status == status)
    if date_from:
        filters.append(Order.created_at >= date_from)
    if date_to:
        filters.append(Order.created_at <= date_to)
    total = db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    orders = db.scalars(
        select(Order).where(*filters).order_by(Order.created_at.desc(), Order.id.desc()).limit(limit).offset(offset)
    ).all()
    return OrderPage(items=[order_out(order) for order in orders], total=total, limit=limit, offset=offset)


def update_status(db: Session, order_id: int, new_status: str) -> OrderOut:
    previous = {"confirmed": "pending", "shipped": "confirmed", "delivered": "shipped"}[new_status]
    updated_id = db.scalar(
        update(Order).where(Order.id == order_id, Order.status == previous)
        .values(status=new_status, updated_at=utc_now()).returning(Order.id)
    )
    if updated_id is None:
        if db.get(Order, order_id) is None:
            raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=409, detail=f"Order must be {previous} to become {new_status}")
    db.expire_all()
    return order_out(db.get(Order, updated_id))


def cancel_order(db: Session, order_id: int, customer_id: int, reason: str) -> OrderOut:
    updated_id = db.scalar(
        update(Order)
        .where(Order.id == order_id, Order.customer_id == customer_id, Order.status.in_(["pending", "confirmed"]))
        .values(status="cancelled", cancellation_reason=reason, updated_at=utc_now())
        .returning(Order.id)
    )
    if updated_id is None:
        get_owned_order(db, order_id, customer_id)
        raise HTTPException(status_code=409, detail="Order can no longer be cancelled")
    db.expire_all()
    order = db.get(Order, updated_id)
    for item in order.items:
        db.execute(update(Product).where(Product.id == item.product_id).values(stock=Product.stock + item.quantity))
    return order_out(order)
