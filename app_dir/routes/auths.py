from flask import Blueprint, request, current_app
from app_dir.models import User, OTP
from app_dir import allow_files, UPLOAD_FOLDER, json_err, json_ok, generate_otp, send_emails, db
from werkzeug.utils import secure_filename
import os, datetime
from flask_jwt_extended import get_jwt_identity, create_access_token, create_refresh_token, jwt_required, set_refresh_cookies

auth_bp = Blueprint("auths", __name__, url_prefix="/auths")
MAX_OTP_ATTEMPTS = 5

# REGISTER ROUTE
@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        username = request.form.get("username")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        user_photo = request.files.get("photo")
    except Exception as e:
        return json_err(str(e), 400)

    # Validate fields
    if not all([username, email, phone, password]):
        print(username, email, phone, password)
        return json_err("All fields required", 400)

    if not user_photo or not allow_files(user_photo.filename):
        print(username, email, phone, password)
        return json_err("Valid user photo required", 404)

    if User.query.filter_by(email=email).first() or User.query.filter_by(phone=phone).first():
        return json_err("User Exist with Email or Password", 400)

    # Save photo
    filename = secure_filename(user_photo.filename)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{filename}"
    image_path = os.path.join(UPLOAD_FOLDER)
    os.makedirs(image_path, exist_ok=True)

    file_path = os.path.join(image_path, filename)
    user_photo.save(file_path)

    relative_path = f"uploads/{filename}"

    # Create User

    new_user = User(
        username=username,
        email=email,
        phone=phone,
        user_photo=relative_path
    )

    new_user.set_password(password)
    new_user.save()

    return json_ok({"user": new_user.to_dict()}, 200)


# LOGIN ROUTE
@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")
    except Exception as e:
        return json_err(str(e), 400)

    if not all([email, password]):
        return json_err("All fields required", 400)

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return json_err("Wrong email or password", 400)

    # Generate tokens
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    resp, status_code = json_ok({
                        "user": user.to_dict(user.password),
                        "access_token": access_token
                    }, 200)
    
    set_refresh_cookies(resp, refresh_token)

    return resp, status_code

# FORGOT PASSWORD AND SEND OTP CODE
@auth_bp.route("/forgot_password", methods=['POST'])
def forgot_password():
    try:
        email = request.json.get("email")
    except Exception as e:
        return json_err(str(e), 400)
    
    if not email:
        return json_err("You need to enter your email", 404)
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return json_err("Email not found", 404)
    
    otp_code = generate_otp()

    set_otp_code = OTP(
        email=user.email,
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    )

    set_otp_code.set_hash_code(otp_code)
    set_otp_code.set_otp()

    try:
        send_emails(user.email, otp_code, "Five 5")
    except Exception as e:
        return json_err(str(e), 400)
    return json_ok({"email":user.email}, 200)

# Check OTP
@auth_bp.route("/check_otp", methods=['POST'])
def check_otp():
    try:
        otp_code = request.json.get("otp_code")
        email = request.json.get("email")
    except Exception as e:
        return json_err(str(e))

    if not all([email, otp_code]):
        return json_err("OTP or email not found")
    
    otp = OTP.query.filter_by(
        email=email, used=False
        ).order_by(
            OTP.created_at.desc()
            ).first()
    
    if not otp:
       return  json_err("OTP not found or already used. please request new one", 404)
    
    if datetime.datetime.utcnow() > otp.expires_at:
        return json_err("OTP Code Expired. Request new one")
    
    if otp.attempts >= MAX_OTP_ATTEMPTS:
        return json_err("Too Many attempts Please requests New Code")
    
    if not otp.check_hash_code(otp_code):
        otp.attempts += 1
        db.session.commit()
        remaining = MAX_OTP_ATTEMPTS - otp.attempts
        return json_err(f"Wrong OTP. Attempts left: {remaining}", 400)

    otp.used = True
    db.session.commit()

    user = User.query.filter_by(email=email).first()

    if not user:
        return json_err("User not exist or error Please Try again", 404)
    

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    return json_ok({"user":user.to_dict(),
                    "access_token":access_token,
                    "refresh_token":refresh_token}, 200)
   
# CHANGE PASSWORD ROUTE 
@auth_bp.route("/change_password", methods=['POST'])
@jwt_required(refresh=True)
def change_password():
    try:
        current_user_id  = int(get_jwt_identity())
        new_password = request.json.get("new_password")
    except Exception as e:
        return json_err(str(e), 400)
    
    if not new_password:
        return json_err("Password can't be empty string")
    
    user = User.query.filter_by(id=current_user_id).first()
    if not user:
        return json_err("Can't find user", 404)
    
    user.set_password(new_password)
    user.save()

    return json_ok({"user":user.to_dict()})

@auth_bp.route("/refresh_user", methods=['POST'])
@jwt_required(refresh=True)
def refresh_user():
    user_id = int(get_jwt_identity())
    user = User.query.filter_by(id=user_id).first()
    new_access_token = create_access_token(identity=str(user_id))
    return json_ok({"access":new_access_token, "user":user.to_dict()})