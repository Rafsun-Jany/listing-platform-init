from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

OrderStatus = Literal["pending", "confirmed", "shipped", "delivered", "cancelled"]


class CreateItem(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class CreateOrder(BaseModel):
    items: list[CreateItem] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def unique_products(cls, items: list[CreateItem]) -> list[CreateItem]:
        if len({item.product_id for item in items}) != len(items):
            raise ValueError("Each product may appear only once")
        return items


class OrderItemOut(BaseModel):
    product_id: int
    quantity: int
    unit_price: Decimal


class OrderOut(BaseModel):
    order_id: int
    customer_id: int
    status: OrderStatus
    total_amount: Decimal
    items: list[OrderItemOut]
    created_at: datetime
    updated_at: datetime
    cancellation_reason: str | None


class OrderPage(BaseModel):
    items: list[OrderOut]
    total: int
    limit: int
    offset: int


class StatusUpdate(BaseModel):
    status: Literal["confirmed", "shipped", "delivered"]


class Cancellation(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Reason cannot be blank")
        return value


class CustomerOut(BaseModel):
    customer_id: int

