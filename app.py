"""
Spherix Clinic - Cross-Border Digital Health Intelligence System
Main Application Entrypoint
"""

import os
import ssl
import subprocess
from spherix import create_app
from spherix.extensions import socketio, login_manager, csrf, limiter, talisman, cors, jwt, oauth, razorpay_client
from spherix.services.database import (
    TEMP_DATA, get_db_connection, save_data, load_data,
    auto_migrate_local_data, migrate_legacy_schema, create_notification, get_temp_data_item
)
from spherix.models import (
    Doctor, Patient, Staff, HospitalStaff, Hospital, BloodDonor, OrganDonor,
    Appointment, PatientVital, LabRequest, OrganRequest, BedBooking,
    Order, Review, Feedback, Message, ActivityLog, Referral, Notification
)
from spherix.config import (
    utcnow, parse_route_id, get_actual_user_id, format_dual_currency,
    convert_currency, get_currency_symbol, generate_user_license_id, BLOG_POSTS
)

# Instantiate Application
app = create_app()
application = app
handler = app

if __name__ == '__main__':
    # SSL/HTTPS Configuration
    ssl_cert = os.getenv('SSL_CERT_PATH', 'ssl/cert.pem')
    ssl_key = os.getenv('SSL_KEY_PATH', 'ssl/key.pem')
    use_ssl = os.getenv('USE_SSL', 'True').lower() == 'true'
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    # Auto-generate self-signed SAN SSL certificate if missing
    if use_ssl and (not os.path.exists(ssl_cert) or not os.path.exists(ssl_key)):
        try:
            os.makedirs(os.path.dirname(ssl_cert) or 'ssl', exist_ok=True)
            print("🔑 Generating development SAN SSL certificate...")
            subprocess.run([
                'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                '-keyout', ssl_key, '-out', ssl_cert, '-days', '3650',
                '-subj', '/C=US/ST=CA/O=SpherixClinic/CN=localhost',
                '-addext', 'subjectAltName = DNS:localhost,DNS:127.0.0.1,IP:127.0.0.1,IP:0.0.0.0'
            ], check=True, capture_output=True)
            os.chmod(ssl_key, 0o600)
            os.chmod(ssl_cert, 0o644)
            print("✅ SSL certificate generated successfully.")
        except Exception as cert_err:
            print(f"⚠️ Could not auto-generate certificate: {cert_err}")

    # Prepare SSL context if certificates exist
    ssl_context = None
    if use_ssl and os.path.exists(ssl_cert) and os.path.exists(ssl_key):
        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(ssl_cert, ssl_key)
            protocol = "HTTPS"
            print(f"🔒 SSL/HTTPS enabled:")
            print(f"   📄 Certificate: {ssl_cert}")
            print(f"   🔑 Private Key: {ssl_key}")
        except Exception as e:
            print(f"⚠️ Failed to load SSL certificates: {e}")
            ssl_context = None
            protocol = "HTTP"
    else:
        protocol = "HTTP"
        if use_ssl:
            print("⚠️ SSL disabled - Running in HTTP mode (certificates not found)")

    print(f"\n🚀 Starting Spherix Clinic Health Intelligence")
    print(f"📍 {protocol} Server: {protocol.lower()}://{host}:{port}")
    print(f"🔐 SSL Encryption: {'Active (TLS 1.2 / TLS 1.3)' if ssl_context else 'Disabled'}")
    print(f"📊 Debug Mode: {'ON' if debug else 'OFF'}")
    print(f"\n✅ Application is ready! Visit: {protocol.lower()}://{host}:{port}\n")

    try:
        if socketio:
            socketio.run(app, debug=debug, host=host, port=port, ssl_context=ssl_context, allow_unsafe_werkzeug=True)
        else:
            app.run(debug=debug, host=host, port=port, ssl_context=ssl_context, allow_unsafe_werkzeug=True)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
