from app_dir.models import User, Product, CartItem
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask import request, jsonify, Blueprint
import datetime, os
from app_dir import allow_files, UPLOAD_FOLDER
from werkzeug.utils import secure_filename

ERROR = {"msg":"error"}
SUCCESS = {"msg":"success"}

user_bp = Blueprint("users", __name__, url_prefix="/user")

@user_bp.route("/me", methods=['GET'])
@jwt_required()
def get_user():
    try:
        current_user_id = int(get_jwt_identity())
    except Exception as e:
        return jsonify({"status":"error", "msg":str(e)}), 400
    user = User.query.filter_by(id=current_user_id).first()
    if not user:
        return jsonify({"status":"error", "msg":"User Not Found"}), 404
    return jsonify({"status":"Ok", "user":user.to_dict()}), 200

@user_bp.route("/admin_login", methods=['GET'])
@jwt_required()
def admin_login():
    try:
        user_id = int(get_jwt_identity())
    except Exception as e:
        return jsonify({"error":str(e)}), 400
    
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({"error":"User Not Found"}), 404
    
    user.is_admin = True
    user.save()
    return jsonify({"user":user.to_dict(), "msg":"ok"}), 200


@user_bp.route("/add_product", methods=['POST'])
def add_product():
    try:
        item_name = request.form.get("item_name")
        item_photo = request.files.get("item_photo")
        item_price = request.form.get("item_price")
        item_stock = request.form.get("item_stock")
        user_id = request.form.get("user_id")
    except Exception as e:
        return jsonify({"error":str(e)}), 400

    if not all([item_name, item_photo, item_price, item_stock]):
        return jsonify({"error":"All fields require"})
    
    user = User.query.filter_by(id=int(user_id)).first()
    if not user:
        print(user_id)
        return jsonify({"error":"Admin Not Found", "msg":"error"}), 404
    
    # Validate image
    if not item_photo or not allow_files(item_photo.filename):
        return jsonify({"error":"Upload a valid product photo", "msg":"error"}), 404
    
    if item_photo and allow_files(item_photo.filename):
        try:
            filename = secure_filename(item_photo.filename)
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
            filename = f"{timestamp}_{user.id}_{filename}"
            image_path = os.path.join(UPLOAD_FOLDER)
            os.makedirs(image_path, exist_ok=True)
            file_path = os.path.join(image_path, filename )
            item_photo.save(file_path)
            
            relative_path = f"uploads/{filename}"
        except Exception as e:
            return jsonify({"error":str(e)})

    # Save new product
    new_product = Product(
        item_name=item_name,
        item_price=item_price,
        item_photo=relative_path,
        item_stock=item_stock,
        admin_id = user.id
    )
    new_product.save()
    return jsonify({"product":new_product.to_dict(), "msg":"ok"}), 200
    
@user_bp.route("/get_admin_products", methods=['GET'])
@jwt_required()
def get_admin_products():
    try:
        current_user = int(get_jwt_identity())
    except Exception as e:
        return jsonify({"error":str(e), "msg":"err"}), 400
    
    admin = User.query.filter_by(id=current_user).first()
    if not admin:
        return jsonify({"error":"User not found"}), 404
    
    product = Product.admin_products(admin.id)
    deleted_products = Product.admin_deleted_product(admin.id)

    return jsonify({"products":product,
                    "deleted_product":deleted_products,
                    "msg":"ok"})

@user_bp.route("/add_to_cart", methods=['POST'])
@jwt_required()
def add_to_cart():
    try:
        admin_id = int(get_jwt_identity())
        product_id = request.json.get("id")
        quantity = request.json.get("quantity")
    except Exception as e:
        return jsonify({"error":str(e)}), 400
    
    admin = User.query.filter_by(id=admin_id).first()
    product = Product.query.filter_by(id=product_id).first()

    if not admin:
        return jsonify({"error":"Admin Not found"}), 404
    
    if not product:
        return jsonify({"error":"Product not found"}), 404
    
    items_on_cart = CartItem.query.all()
    for item in items_on_cart:
        if item.product_id == product_id and item.user_id == admin.id:
            return jsonify({"error":"Product already on cart", "msg":"error"}), 400
    
    cart_item = CartItem(
        product_id=product_id,
        quantity=quantity,
        user_id=admin.id
    )
    cart_item.save()
    item = cart_item.to_dict()
    return jsonify({"item":item, 'msg':"success"}), 200

@user_bp.route("/get_cart_item", methods=['GET'])
@jwt_required()
def get_cart_item():
    try:
        user_id = int(get_jwt_identity())
    except Exception as e:
        return jsonify({"error":str(e), "msg":"error"}), 400
    
    user = User.get_user(user_id)
    if not user:
        return jsonify({"error":"User Not Found", "msg":"error"}), 404

    cart_items = CartItem.query.filter_by(user_id=user.get("id")).all()

    if not cart_items:
        return jsonify({"error":"No Item On Cart", "msg":"error"}), 404

    return jsonify({"cart_items":[item.to_dict() for item in cart_items]})    

@user_bp.route("/clear_cart", methods=['GET'])
@jwt_required()
def clear_cart():
    pass


