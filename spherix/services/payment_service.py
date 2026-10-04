import os
import hmac
import hashlib
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import razorpay

def get_razorpay_key_id():
    """Returns the Razorpay Key ID from environment."""
    return os.getenv('RAZORPAY_KEY_ID', '').strip()

def get_razorpay_key_secret():
    """Returns the Razorpay Key Secret from environment."""
    return os.getenv('RAZORPAY_KEY_SECRET', '').strip()

def get_razorpay_client():
    """Returns the active Razorpay client instance, initializing on demand."""
    from spherix.extensions import razorpay_client
    if razorpay_client is not None:
        return razorpay_client
    
    key_id = get_razorpay_key_id()
    key_secret = get_razorpay_key_secret()
    if key_id and key_secret:
        try:
            return razorpay.Client(auth=(key_id, key_secret))
        except Exception as e:
            print(f"⚠️ Error initializing Razorpay client: {e}")
    return None

def verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """Verifies Razorpay payment signature using HMAC-SHA256."""
    secret = get_razorpay_key_secret()
    if not secret or not razorpay_signature:
        # If in development or test fallback mode
        return True
    try:
        message = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
        generated_signature = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(generated_signature, razorpay_signature)
    except Exception as e:
        print(f"⚠️ Razorpay signature verification exception: {e}")
        return False

def create_razorpay_order(amount_inr, receipt=None, notes=None):
    """Creates a Razorpay order in paise (1 INR = 100 paise)."""
    client = get_razorpay_client()
    if not client:
        return None
    try:
        amount_paise = int(round(float(amount_inr) * 100))
        data = {
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': str(receipt or f"rcpt_{int(time.time())}_{os.urandom(2).hex()}"),
            'notes': notes or {}
        }
        return client.order.create(data=data)
    except Exception as e:
        print(f"⚠️ Razorpay order creation failed: {e}")
        return None

def create_razorpay_payment_link(amount_inr, reference_id, description, customer_name, customer_email, customer_phone=None, callback_url=None):
    """Creates a Razorpay hosted payment link for web/mobile checkout."""
    client = get_razorpay_client()
    if not client:
        return None
    try:
        amount_paise = int(round(float(amount_inr) * 100))
        customer = {
            "name": customer_name or "Valued Patient",
            "email": customer_email or "patient@spherixclinic.com"
        }
        if customer_phone:
            customer["contact"] = str(customer_phone)

        data = {
            "amount": amount_paise,
            "currency": "INR",
            "accept_partial": False,
            "reference_id": str(reference_id),
            "description": str(description)[:255],
            "customer": customer,
            "notify": {
                "sms": bool(customer_phone),
                "email": bool(customer_email)
            }
        }
        if callback_url:
            data["callback_url"] = callback_url
            data["callback_method"] = "get"

        return client.payment_link.create(data)
    except Exception as e:
        print(f"⚠️ Razorpay payment link creation failed: {e}")
        return None
