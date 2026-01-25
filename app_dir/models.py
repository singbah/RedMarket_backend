# full_corrected_models.py
from app_dir import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
from sqlalchemy import event


# Helpers
def generate_sku():
    # Production-ready simple SKU generator (random)
    return "SKU-" + uuid.uuid4().hex[:10].upper()

# BASE MODEL (used only by core tables)
class BaseModel(db.Model):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    update_date = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp()
    )
    is_deleted = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    def save(self):
        db.session.add(self)
        db.session.commit()

    def soft_delete(self):
        self.is_deleted = True
        self.is_active=False
        db.session.commit()
    
    def deactivate(self):
        self.is_active = False
    
    def restore(self):
        self.is_active = True
        self.is_deleted=False
        db.session.commit()

    def hard_delete(self):
        db.session.delete(self)
        db.session.commit()

    def to_dict(self, include_nulls=False):
        data = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if value is None and not include_nulls:
                continue
            data[col.name] = value
        return data

    
    def update_item(self, kwargs: dict):
        try:
            for k, v in kwargs.items():
                if hasattr(self, k):  # safer check
                    setattr(self, k, v)
            db.session.commit()  # commit once after all updates
            return "Done"
        except Exception as e:
            db.session.rollback()
            return str(e)


    @classmethod
    def from_dict(cls, data, allowed=None):
        """Construct model from dict safely.

        - `allowed` is an optional iterable of column names that are permitted.
        - If `allowed` is None, all writable columns except blocked ones are allowed.
        """
        blocked = {"id", "is_deleted", "update_date"}
        columns = set(cls.__table__.columns.keys())
        if allowed is not None:
            columns = columns & set(allowed)
        valid = {k: v for k, v in data.items() if k in columns and k not in blocked}
        return cls(**valid)

# CORE TABLES (inherit BaseModel)
class User(BaseModel):
    __tablename__ = "users"

    username = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    email = db.Column(db.String(100), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(20), nullable=False, unique=True, index=True)
    user_photo = db.Column(db.String(200), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    password = db.Column(db.String(256), nullable=False)

    password_try = db.Column(db.Integer, default=0)
    reset_start_time = db.Column(db.DateTime, nullable=True)
    reset_end_time = db.Column(db.DateTime, nullable=True)


    # Relationships (core cascades and useful backrefs)
    products = db.relationship(
        "Product", backref="admin", cascade="all, delete-orphan", lazy="select"
    )
    orders = db.relationship("Order", backref="user", lazy="select")


    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, password):
        return check_password_hash(self.password,  password)

    @classmethod
    def get_users(cls):
        return [user.to_dict() for user in cls.query.filter_by(is_deleted=False).all()]
    
    @classmethod
    def get_user(cls, user_id):
        user = cls.query.filter_by(id=user_id).first()
        if not user or user.is_deleted:
            return None
        return user.to_dict()

    @classmethod
    def count_users(cls):
        return cls.query.filter_by(is_deleted=False).count()

class OTP(db.Model):
    __tablename__ = "otps"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_otp(self):
        db.session.add(self)
        db.session.commit()
    
    def set_hash_code(self, otp_code):
        self.code_hash = generate_password_hash(otp_code)
    
    def check_hash_code(self, hash_code):
        return check_password_hash(self.code_hash, hash_code)

class Product(BaseModel):
    __tablename__ = "products"

    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    subcategory_id = db.Column(db.Integer, db.ForeignKey("subcategories.id"), nullable=True)

    item_name = db.Column(db.String(150), nullable=False)
    item_sku = db.Column(db.String(100), nullable=True, unique=True, index=True)
    item_description = db.Column(db.Text, nullable=True)
    item_photo = db.Column(db.String(300), nullable=True)
    item_price = db.Column(db.Numeric(10, 2), nullable=False)
    item_stock = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    order_items = db.relationship(
        "OrderItem", backref="product", cascade="all, delete-orphan", lazy="select"
    )
    cart_items = db.relationship(
        "CartItem", backref="product", cascade="all, delete-orphan", lazy="select"
    )

    @classmethod
    def admin_deleted_product(cls, admin_id):
        products = cls.query.filter_by(admin_id=admin_id).all()
        return [product.to_dict() for product in products if product.is_deleted==True]
    
    @classmethod
    def admin_products(cls, admin_id):
        return [product.to_dict() for product in  cls.query.filter_by(admin_id=admin_id).all() if product.is_deleted is not True]
    
    @classmethod
    def get_product(cls, product_id):
        return cls.query.filter_by(id=product_id).first()
        

# Auto-generate SKU before insert if not supplied
@event.listens_for(Product, "before_insert")
def set_product_sku(mapper, connection, target):
    if not target.item_sku:
        # Ensure uniqueness: try a few times (very low collision chance with uuid slice)
        for _ in range(5):
            candidate = generate_sku()
            # check DB for existing SKU using the connection to be safe during flush
            existing = connection.execute(
                db.text("SELECT 1 FROM products WHERE item_sku = :sku LIMIT 1"),
                {"sku": candidate}
            ).fetchone()
            if not existing:
                target.item_sku = candidate
                break
        else:
            # fallback to uuid without prefix (very unlikely)
            target.item_sku = uuid.uuid4().hex.upper()


class CartItem(BaseModel):
    __tablename__ = "cart_items"

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)

    # When a User is removed, cart items should be removed too:
    # The cascade is achievable via relationship on User (if needed). Alternatively, manage in code.


class OrderItem(BaseModel):
    __tablename__ = "order_items"

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)


class Order(BaseModel):
    __tablename__ = "orders"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    total_price = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    shipping_address_id = db.Column(db.Integer, db.ForeignKey("addresses.id"), nullable=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey("coupons.id"), nullable=True)

    order_items = db.relationship(
        "OrderItem", backref="order", cascade="all, delete-orphan", lazy="select"
    )
    payment = db.relationship("Payment", backref="order", uselist=False, cascade="all, delete-orphan")


class Payment(BaseModel):
    __tablename__ = "payments"

    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    payment_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    payment_method = db.Column(db.String(50), nullable=False)
    payment_status = db.Column(db.String(50), default="Pending")
    amount = db.Column(db.Numeric(12, 2), nullable=False)

    transactions = db.relationship("Transaction", backref="payment", cascade="all, delete-orphan", lazy="select")


# NON-CORE TABLES (use db.Model directly)
# These tables define their own primary key and do not inherit BaseModel

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(300))
    image = db.Column(db.String(200))

    products = db.relationship("Product", backref="category", lazy="select")
    subcategories = db.relationship("SubCategory", backref="category", lazy="select", cascade="all, delete-orphan")


class SubCategory(db.Model):
    __tablename__ = "subcategories"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    products = db.relationship("Product", backref="subcategory", lazy="select")


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False)
    gateway_transaction_id = db.Column(db.String(200), nullable=False, index=True, unique=False)
    status = db.Column(db.String(50), nullable=True)
    raw_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class ProductReview(db.Model):
    __tablename__ = "product_reviews"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # relationships: backrefs already exist via foreign keys and Product/User definitions


class InventoryLog(db.Model):
    __tablename__ = "inventory_logs"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    previous_stock = db.Column(db.Integer, nullable=False)
    new_stock = db.Column(db.Integer, nullable=False)
    change_type = db.Column(db.String(50), nullable=False)
    note = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())


class Address(db.Model):
    __tablename__ = "addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address_line_1 = db.Column(db.String(200), nullable=False)
    address_line_2 = db.Column(db.String(200), nullable=True)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=True)
    postal_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class Wishlist(db.Model):
    __tablename__ = "wishlist"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class Coupon(db.Model):
    __tablename__ = "coupons"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    discount_type = db.Column(db.String(20), nullable=False)  # percent, fixed
    value = db.Column(db.Numeric(10, 2), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    expiration_date = db.Column(db.DateTime, nullable=False)
    usage_limit = db.Column(db.Integer, default=0)  # 0 = unlimited
    active = db.Column(db.Boolean, default=True)


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

# End of models
