from app_dir.models import User, Product
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask import request, jsonify, Blueprint
import datetime, os
from app_dir import allow_files, UPLOAD_FOLDER, db
from werkzeug.utils import secure_filename


product_bp = Blueprint("products", __name__, url_prefix="/product")

@product_bp.route("/get_all_products", methods=['GET'])
def get_all_products():
    products = Product.query.all()
    return jsonify({"products":[product.to_dict() for product in products if not product.is_deleted]})

@product_bp.route("/delete_product", methods=["POST"])
@jwt_required()
def delete_product():
    try:
        admin_id = int(get_jwt_identity())
        product_id = request.json.get("product_id")
    except Exception as e:
        return jsonify({"error":str(e)})
    
    admin = User.query.filter_by(id=admin_id).first()
    product = Product.query.filter_by(id=product_id).first()

    if not admin or not product:
        return jsonify({"error":"Product Or Admin Not Found"}), 404
    
    product.soft_delete()
    return jsonify({"msg":"ok", "success":"Product successfully deleted"})


@product_bp.route("/restore_product", methods=['POST'])
@jwt_required()
def restore_product():
    try:
        admin_id = int(get_jwt_identity())
        product_id = request.json.get("product_id")
    except Exception as e:
        return jsonify({"error":str(e)}), 400
    
    if not product_id:
        return jsonify({"error":"You Didn't Send any Product"}), 404

    admin = User.get_user(admin_id)       
    product = Product.get_product(product_id)

    if not admin or not product:
        return jsonify({"error":"Admin or Product not found"}), 404
    
    product.restore()
    return jsonify({"msg":"Product Restore"}), 200

@product_bp.route("/update_product", methods=['POST'])
def update_product():
    try:
        product_id = request.form.get("id")
        item_name = request.form.get("item_name")
        item_price = request.form.get("item_price")
        item_photo = request.form.get("item_photo")
    except Exception as e:
        print(str(e))
        return jsonify({"error":str(e)}), 400
    
    product = Product.get_product(product_id)
    if not product:
        return jsonify({"error":"Product Not Found", "msg":"Error"}), 404
    
    try:
        data = {"item_name":item_name, "item_photo":item_photo, "item_price":item_price}

        product.update_item(data)
    except Exception as e:
        return jsonify({"error":str(e), "msg":"error"})
    
    return jsonify({"product":product.to_dict()})
    
    
    
    
    