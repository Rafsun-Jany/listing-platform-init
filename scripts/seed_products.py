"""Seed disposable pilot products without overwriting existing stock or prices."""

from decimal import Decimal

from order_api.database import make_session_factory
from order_api.models import Product


def main() -> None:
    factory = make_session_factory()
    with factory.begin() as session:
        for product_id, name, price in (
            (501, "Pilot Product 501", Decimal("50.00")),
            (502, "Pilot Product 502", Decimal("25.50")),
        ):
            if session.get(Product, product_id) is None:
                session.add(Product(id=product_id, name=name, unit_price=price, stock=100, active=True))


if __name__ == "__main__":
    main()

