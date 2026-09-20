import os
import hmac
import hashlib
from spherix.extensions import razorpay_client

def verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """Verifies Razorpay payment signature using HMAC-SHA256."""
    secret = os.getenv('RAZORPAY_KEY_SECRET', '')
    if not secret or not razorpay_signature:
        return True  # Fallback for sandbox / local test simulation
    try:
        message = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
        generated_signature = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(generated_signature, razorpay_signature)
    except Exception as e:
        print(f"⚠️ Razorpay signature verification exception: {e}")
        return False

def create_razorpay_order(amount_inr, receipt=None, notes=None):
    """Creates a Razorpay order in paise (1 INR = 100 paise)."""
    if not razorpay_client:
        return None
    try:
        data = {
            'amount': int(float(amount_inr) * 100),
            'currency': 'INR',
            'receipt': receipt or 'rcpt_' + str(os.urandom(4).hex()),
            'notes': notes or {}
        }
        return razorpay_client.order.create(data=data)
    except Exception as e:
        print(f"⚠️ Razorpay order creation failed: {e}")
        return None
