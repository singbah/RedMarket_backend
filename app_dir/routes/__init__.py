from app_dir.routes.auths import auth_bp
from app_dir.routes.users import user_bp
from app_dir.routes.products_bp import product_bp

all_bps = [auth_bp, user_bp, product_bp]