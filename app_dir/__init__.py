from flask import Flask, jsonify, render_template
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_mail import Mail, Message
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import os, datetime, uuid
from dotenv import load_dotenv

# Initilazed extensions
mail = Mail()
migrate = Migrate()
db = SQLAlchemy()
jwt = JWTManager()
load_dotenv()

ALLOWED_FILES_EXTENSIONS = {"jpeg", 'jpg', 'png', 'pdf', 'docx'}
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Helper responses
def json_ok(payload=None, code=200):
    if payload is None:
        payload = {}
    payload["msg"] = "ok"
    return jsonify(payload), code

def json_err(message="An error occurred", code=400):
    return jsonify({"msg": "error", "error": message}), code

def generate_otp(length=4):
    otp = uuid.uuid4().hex[0:4]
    return otp

def allow_files(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_FILES_EXTENSIONS

def send_emails(receiver, otp_code, expires_time=5):
    html_body = render_template(
        "emails/otp.html",
        otp_code=otp_code,
        expires_time=expires_time,
        year = datetime.datetime.utcnow().year

    )
    msgs =  Message(
        subject="Your Otp Code",
        recipients=[receiver],
        html=html_body
    )
    mail.send(msgs)
    
    return 

def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', 'default_secret_key'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///app.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_COOKIE_SECURE=True,
        JWT_COOKIE_SAMESITE="Lax",
        JWT_COOKIE_CSRF_PROTECT=False,
        JWT_SECRET_KEY=os.getenv('SECRET_KEY', 'default_jwt_secret_key'),
        JWT_ACCESS_TOKEN_EXPIRES = datetime.timedelta(days=7),
        JWT_REFRESH_TOKEN_EXPIRES = datetime.timedelta(days=30),
        MAIL_SERVER=os.getenv('MAIL_SERVER', 'smtp.gmail.com'),
        MAIL_PORT=int(os.getenv('MAIL_PORT', 587)),
        MAIL_USE_TLS=True,
        MAIL_USE_SSL=False,
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
        MAIL_DEFAULT_SENDER =os.getenv("MAIL_USERNAME"),
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
        UPLOAD_FOLDER=UPLOAD_FOLDER,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        CORS_HEADERS='Content-Type'
    )

    # Initialize extensions with the app
    CORS(app,
     supports_credentials=True,
     origins=["http://localhost:5173"])  # must match React dev URL exactly
    mail.init_app(app)
    migrate.init_app(app, db)
    db.init_app(app)
    jwt.init_app(app)

    from app_dir.routes import all_bps
    for bp in all_bps:
        app.register_blueprint(bp)

    return app
