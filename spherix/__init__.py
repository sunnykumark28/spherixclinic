import os
import sys
from datetime import datetime, timezone

from flask import Flask, session, request, redirect, url_for, flash, jsonify, current_app, send_from_directory
from flask_login import current_user, logout_user
from werkzeug.exceptions import RequestEntityTooLarge

from spherix.config import (
    SECRET_KEY, COUNTRIES_195, GLOBAL_COUNTRY_FLAGS, GLOBAL_COUNTRY_TIMEZONES,
    GLOBAL_CURRENCY_RATES, GLOBAL_CURRENCY_SYMBOLS, format_dual_currency,
    convert_currency, get_currency_symbol, parse_route_id, utcnow, search_countries
)
from spherix.models import Notification
from spherix.services.database import TEMP_DATA, load_data, get_db_connection, save_data
from spherix.extensions import (
    login_manager, csrf, limiter, talisman, cors, jwt, oauth, socketio
)
from spherix.routes import ALL_BLUEPRINTS

def create_app(config_object=None):
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'),
        static_url_path='/static'
    )

    # Configuration
    app.secret_key = SECRET_KEY
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    app.config['JWT_DECODE_AUDIENCE'] = None
    app.config['JWT_IDENTITY_CLAIM'] = 'sub'
    app.config['JWT_VERIFY_SUB'] = False

    if config_object:
        app.config.from_object(config_object)

    # Initialize Extensions
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_landing'

    # CSRF Protection
    app.config['WTF_CSRF_CHECK_DEFAULT'] = False
    csrf.init_app(app)

    # Limiter
    limiter.init_app(app)

    # CORS
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    # JWT
    jwt.init_app(app)

    # Talisman CSP (allow necessary inline styles, fonts, CDN scripts)
    csp = {
        'default-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https:", "http:", "data:", "blob:"],
        'img-src': ["'self'", "data:", "blob:", "https:", "http:"],
        'font-src': ["'self'", "https:", "http:", "data:"],
        'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https:", "http:"],
        'style-src': ["'self'", "'unsafe-inline'", "https:", "http:"]
    }
    talisman.init_app(app, content_security_policy=csp, force_https=False)

    # SocketIO
    if socketio:
        socketio.init_app(app)

    # OAuth Setup
    if oauth:
        oauth.init_app(app)
        google_client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
        google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
        if google_client_id and google_client_secret:
            oauth.register(
                name='google',
                client_id=google_client_id,
                client_secret=google_client_secret,
                server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                client_kwargs={'scope': 'openid email profile'}
            )

        # Apple OAuth Setup
        apple_client_id = os.getenv('APPLE_CLIENT_ID', '').strip()
        if apple_client_id:
            try:
                from spherix.services.apple_auth import generate_apple_client_secret
                apple_secret = generate_apple_client_secret()
                oauth.register(
                    name='apple',
                    client_id=apple_client_id,
                    client_secret=apple_secret,
                    server_metadata_url='https://appleid.apple.com/.well-known/openid-configuration',
                    client_kwargs={
                        'scope': 'name email',
                        'response_type': 'code id_token',
                        'response_mode': 'form_post'
                    }
                )
            except Exception as e:
                print(f"⚠️ Apple OAuth registration notice: {e}")

    # Flask-Login user_loader
    @login_manager.user_loader
    def load_user(user_id):
        if not user_id:
            return None
        try:
            user_id_str = str(user_id)
            if '-' in user_id_str:
                role, id_val = user_id_str.split('-', 1)
            else:
                role = 'doctor'
                id_val = user_id_str

            collection_map = {
                'doctor': 'doctors',
                'patient': 'patients',
                'staff': 'staff',
                'hospital': 'hospitals',
                'blood_donor': 'blood_donors',
                'organ_donor': 'organ_donors'
            }
            collection_name = collection_map.get(role, 'doctors')
            collection = TEMP_DATA.get(collection_name, {})

            if id_val in collection:
                return collection[id_val]
            try:
                int_id = int(str(id_val).split('/')[-1]) if '/' in str(id_val) else int(id_val)
                if int_id in collection:
                    return collection[int_id]
            except (ValueError, TypeError):
                pass
            try:
                p_id = parse_route_id(id_val)
                if p_id in collection:
                    return collection[p_id]
            except Exception:
                pass
            for k, v in collection.items():
                if str(k) == str(id_val) or str(getattr(v, 'id', '')) == str(id_val):
                    return v

            for col_name in collection_map.values():
                c = TEMP_DATA.get(col_name, {})
                if id_val in c:
                    return c[id_val]
                for k, v in c.items():
                    if str(k) == str(id_val) or str(getattr(v, 'id', '')) == str(id_val):
                        return v
        except Exception:
            return None
        return None

    # Before Request Check
    @app.before_request
    def check_blocked_status():
        if current_user and current_user.is_authenticated:
            if getattr(current_user, 'is_blocked', False):
                excluded_endpoints = ['static', 'auth.login_landing', 'auth.logout', 'login_landing', 'logout']
                if request.endpoint and request.endpoint not in excluded_endpoints:
                    logout_user()
                    flash("Your account has been blocked by the administrator.", "error")
                    return redirect(url_for('auth.login_landing'))

    @app.after_request
    def add_security_and_cache_headers(response):
        # Prevent browser caching on admin, dashboards, and auth endpoints to ensure immediate logout enforcement
        path = request.path.lower()
        if any(prefix in path for prefix in ['/admin', '/doctor', '/patient', '/staff', '/hospital', '/blood-donor', '/organ-donor', '/dashboard', '/logout']):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # Error handler for payload too large
    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(error):
        try:
            flash('Uploaded file is too large. Please use an image smaller than 200 MB.', 'error')
        except Exception:
            pass
        return redirect(request.referrer or url_for('clinical_ai.symptoms'))

    # Context Processors
    @app.context_processor
    def inject_cart():
        cart = session.get('cart', [])
        cart_item_count = 0
        total_price = 0
        normalized_cart = []
        for item in cart:
            quantity = int(item.get('quantity', 0) or 0)
            try:
                price_value = float(item.get('price', 0))
            except (TypeError, ValueError):
                price_value = 0.0

            normalized_cart.append({
                'name': item.get('name'),
                'quantity': quantity,
                'price': price_value
            })
            cart_item_count += quantity
            total_price += quantity * price_value

        session['cart'] = normalized_cart
        return dict(
            cart=normalized_cart,
            cart_item_count=cart_item_count,
            cart_total_price=round(total_price, 2)
        )

    @app.context_processor
    def inject_notifications():
        if current_user.is_authenticated:
            user_id = str(current_user.id)
            if getattr(current_user, 'email', '') == 'admin@spherixclinic.com':
                role = 'admin'
            else:
                role_parts = current_user.get_id().split('-')
                role = role_parts[0] if role_parts else 'patient'

            all_notifs = list(TEMP_DATA.get('notifications', {}).values())
            user_notifs = [n for n in all_notifs if str(n.user_id) == user_id]

            unread_count = sum(1 for n in user_notifs if n.status == 'unread')
            user_notifs.sort(key=lambda x: x.created_at, reverse=True)

            return dict(
                notifications=user_notifs,
                unread_notifications_count=unread_count
            )
        return dict(
            notifications=[],
            unread_notifications_count=0
        )

    @app.context_processor
    def inject_globals():
        current_time = datetime.now()
        return dict(
            now=current_time,
            today=current_time,
            global_doctors=TEMP_DATA.get('doctors', {}),
            all_countries_195=COUNTRIES_195,
            global_country_flags=GLOBAL_COUNTRY_FLAGS,
            global_country_timezones=GLOBAL_COUNTRY_TIMEZONES,
            format_dual_currency=format_dual_currency,
            convert_currency=convert_currency,
            get_currency_symbol=get_currency_symbol
        )

    # Register essential Python builtins into Jinja environment
    app.jinja_env.globals.update(
        hasattr=hasattr,
        getattr=getattr,
        setattr=setattr,
        isinstance=isinstance,
        type=type,
        len=len,
        str=str,
        int=int,
        float=float,
        dict=dict,
        list=list,
        min=min,
        max=max,
        round=round
    )

    # Markdown template filter
    import markdown
    @app.template_filter('markdown')
    def render_markdown_filter(text):
        return markdown.markdown(text or '', extensions=['fenced_code', 'tables', 'nl2br'])

    # Serve favicon at root
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, '..', 'static'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
        )

    # Dynamic URL resolution fallback for unprefixed template endpoints
    def url_build_error_handler(error, endpoint, values):
        for rule in current_app.url_map.iter_rules():
            if rule.endpoint.endswith('.' + endpoint) or rule.endpoint == endpoint:
                return url_for(rule.endpoint, **values)
        return None

    app.url_build_error_handlers.append(url_build_error_handler)

    # Register Blueprints
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    try:
        from api import api_bp
        csrf.exempt(api_bp)
        app.register_blueprint(api_bp)
    except Exception as e:
        print(f"⚠️ api_bp could not be loaded: {e}")

    # Initial Data Load
    load_data()

    return app
