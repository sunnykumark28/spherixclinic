import os
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_cors import CORS
from flask_jwt_extended import JWTManager

login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(
    get_remote_address,
    default_limits=["1000 per day", "500 per hour"],
    storage_uri="memory://"
)
talisman = Talisman()
cors = CORS()
jwt = JWTManager()

try:
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth()
except ImportError:
    oauth = None

try:
    from flask_socketio import SocketIO, emit, join_room
    socketio = SocketIO(cors_allowed_origins=[origin.strip() for origin in os.getenv('SOCKETIO_CORS_ALLOWED_ORIGINS', '').split(',') if origin.strip()] or None)
except ImportError:
    socketio = None
    emit = None
    join_room = None

try:
    import razorpay
    key_id = os.getenv('RAZORPAY_KEY_ID', '')
    key_secret = os.getenv('RAZORPAY_KEY_SECRET', '')
    if key_id and key_secret:
        razorpay_client = razorpay.Client(auth=(key_id, key_secret))
    else:
        razorpay_client = None
except ImportError:
    razorpay_client = None
