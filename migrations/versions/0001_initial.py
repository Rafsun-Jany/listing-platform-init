"""Initial order schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("consumer_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("unit_price >= 0", name="ck_products_price_nonnegative"),
        sa.CheckConstraint("stock >= 0", name="ck_products_stock_nonnegative"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("cancellation_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending','confirmed','shipped','delivered','cancelled')", name="ck_orders_status"),
        sa.CheckConstraint("total_amount >= 0", name="ck_orders_total_nonnegative"),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("order_id", "product_id", name="uq_order_item_product"),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id")),
        sa.UniqueConstraint("customer_id", "key", name="uq_idempotency_customer_key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_table("orders")
    op.drop_table("products")
    op.drop_table("customers")

