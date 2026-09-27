from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_db, make_session_factory
from .schemas import Cancellation, CreateOrder, CustomerOut, OrderOut, OrderPage, OrderStatus, StatusUpdate
from .security import Caller, customer_caller, staff_caller
from .service import cancel_order, create_order, get_or_create_customer, get_owned_order, list_orders, order_out, update_status

session_factory = make_session_factory()
app = FastAPI(title="Order API", version="0.1.0")


@app.get("/health", include_in_schema=False)
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok"}


@app.get("/api/v1/me", response_model=CustomerOut)
def me(caller: Caller = Depends(customer_caller), db: Session = Depends(get_db)) -> CustomerOut:
    with db.begin():
        customer = get_or_create_customer(db, caller.sub)
        return CustomerOut(customer_id=customer.id)


@app.post("/api/v1/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def post_order(
    body: CreateOrder,
    request: Request,
    caller: Caller = Depends(customer_caller),
    db: Session = Depends(get_db),
) -> OrderOut:
    key = request.headers.get("Idempotency-Key", "")
    with db.begin():
        customer = get_or_create_customer(db, caller.sub)
        return create_order(db, customer.id, body, key)


@app.get("/api/v1/orders", response_model=OrderPage)
def get_orders(
    status_filter: OrderStatus | None = Query(None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    caller: Caller = Depends(customer_caller),
    db: Session = Depends(get_db),
) -> OrderPage:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    with db.begin():
        customer = get_or_create_customer(db, caller.sub)
        return list_orders(db, customer.id, status_filter, date_from, date_to, limit, offset)


@app.get("/api/v1/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, caller: Caller = Depends(customer_caller), db: Session = Depends(get_db)) -> OrderOut:
    with db.begin():
        customer = get_or_create_customer(db, caller.sub)
        return order_out(get_owned_order(db, order_id, customer.id))


@app.get("/api/v1/customers/{customer_id}/orders", response_model=OrderPage)
def get_customer_orders(
    customer_id: int,
    status_filter: OrderStatus | None = Query(None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    caller: Caller = Depends(customer_caller),
    db: Session = Depends(get_db),
) -> OrderPage:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    with db.begin():
        customer = get_or_create_customer(db, caller.sub)
        if customer.id != customer_id:
            raise HTTPException(status_code=404, detail="Customer not found")
        return list_orders(db, customer.id, status_filter, date_from, date_to, limit, offset)


@app.patch("/api/v1/orders/{order_id}/status", response_model=OrderOut)
def patch_order_status(
    order_id: int,
    body: StatusUpdate,
    _caller: Caller = Depends(staff_caller),
    db: Session = Depends(get_db),
) -> OrderOut:
    with db.begin():
        return update_status(db, order_id, body.status)


@app.post("/api/v1/orders/{order_id}/cancel", response_model=OrderOut)
def post_cancel(
    order_id: int,
    body: Cancellation,
    caller: Caller = Depends(customer_caller),
    db: Session = Depends(get_db),
) -> OrderOut:
    with db.begin():
        customer = get_or_create_customer(db, caller.sub)
        return cancel_order(db, order_id, customer.id, body.reason)
