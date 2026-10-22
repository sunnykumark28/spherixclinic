from datetime import datetime
from spherix.config import utcnow, ensure_safe_date

class Review:
    def __init__(self, id, doctor_id, patient_id, patient_name, rating, comment=None, **kwargs):
        self.id = id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.rating = int(rating) if rating is not None else 5
        self.comment = comment
        self.created_at = ensure_safe_date(kwargs.get('created_at', utcnow()))

    @property
    def doctor(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('doctors', {}).get(self.doctor_id)


class Feedback:
    def __init__(self, id, patient_id, patient_name, rating, comments=None, **kwargs):
        self.id = int(id or 0)
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.rating = int(rating) if rating is not None else 5
        self.comments = comments
        self.feedback_target = kwargs.get('feedback_target', 'web_application')
        self.target_id = kwargs.get('target_id')
        self.target_name = kwargs.get('target_name')
        dt = kwargs.get('created_at', utcnow())
        self.created_at = ensure_safe_date(dt)

    @property
    def patient(self):
        from spherix.services.database import TEMP_DATA
        p = TEMP_DATA.get('patients', {}).get(self.patient_id)
        if not p:
            for pid, patient_obj in TEMP_DATA.get('patients', {}).items():
                if str(pid) == str(self.patient_id):
                    return patient_obj
        return p


class Message:
    def __init__(self, id, doctor_id, patient_id, sender, content, **kwargs):
        self.id = id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.sender = sender
        self.content = content
        self.attachment_url = kwargs.get('attachment_url')
        self.is_read = bool(kwargs.get('is_read', False))
        self.created_at = ensure_safe_date(kwargs.get('created_at', utcnow()))

    @property
    def doctor(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('doctors', {}).get(self.doctor_id)

    @property
    def doctor_name(self):
        doc = self.doctor
        if doc:
            return getattr(doc, 'name', f"Dr. {getattr(doc, 'first_name', '')} {getattr(doc, 'last_name', '')}").strip()
        if str(self.doctor_id) == 'support':
            return "Spherix Care Team"
        return "Specialist Doctor"

    @property
    def patient(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('patients', {}).get(self.patient_id)


class Order:
    def __init__(self, id, patient_id, items, total_price, shipping_address, order_date, status='Processing', prescription=None, payment_method='cod', **kwargs):
        self.id = id
        self.patient_id = patient_id
        self.items = items
        self.total_price = total_price
        self.shipping_address = shipping_address
        self.order_date = ensure_safe_date(order_date)
        self.status = status
        self.prescription = prescription or kwargs.get('prescription')
        self.payment_method = payment_method or kwargs.get('payment_method', 'cod')
        self.tracking_code = kwargs.get('tracking_code', f"TRK-{id}-1MG")

    @property
    def total_amount(self):
        return getattr(self, 'total_price', 0)

    @property
    def shipping_dict(self):
        """Returns normalized dictionary for shipping address components."""
        addr = getattr(self, 'shipping_address', None)
        if isinstance(addr, dict):
            return addr
        if isinstance(addr, str) and addr.strip():
            try:
                import json
                parsed = json.loads(addr)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
            try:
                import ast
                parsed = ast.literal_eval(addr)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
            return {
                "name": "",
                "phone": "",
                "address": addr,
                "city": "",
                "state": "",
                "pincode": "",
                "landmark": ""
            }
        return {}

    @property
    def recipient_name(self):
        return self.shipping_dict.get('name') or ''

    @property
    def recipient_phone(self):
        return self.shipping_dict.get('phone') or ''

    @property
    def recipient_street(self):
        return self.shipping_dict.get('address') or ''

    @property
    def recipient_landmark(self):
        return self.shipping_dict.get('landmark') or ''

    @property
    def recipient_city(self):
        return self.shipping_dict.get('city') or ''

    @property
    def recipient_state(self):
        return self.shipping_dict.get('state') or ''

    @property
    def recipient_pincode(self):
        return self.shipping_dict.get('pincode') or ''

    @property
    def formatted_shipping_address(self):
        """Returns clean human-readable arranged address string instead of raw dict."""
        d = self.shipping_dict
        if not d:
            raw = str(getattr(self, 'shipping_address', '') or '')
            return raw if raw and not raw.startswith('{') else 'Registered Address on File'
        parts = []
        if d.get('address'):
            parts.append(str(d.get('address')).strip())
        if d.get('landmark'):
            parts.append(f"Near {str(d.get('landmark')).strip()}")
        city_state = []
        if d.get('city'):
            city_state.append(str(d.get('city')).strip())
        if d.get('state'):
            city_state.append(str(d.get('state')).strip())
        if city_state:
            parts.append(", ".join(city_state))
        if d.get('pincode'):
            parts.append(f"PIN: {d.get('pincode')}")
        return ", ".join(parts) if parts else 'Registered Address on File'

    @property
    def parsed_items(self):
        """Returns standardized list of items in the order."""
        raw_items = getattr(self, 'items', None)
        if not raw_items:
            return []
        if isinstance(raw_items, str):
            try:
                import json
                raw_items = json.loads(raw_items)
            except Exception:
                try:
                    import ast
                    raw_items = ast.literal_eval(raw_items)
                except Exception:
                    raw_items = [{'name': raw_items, 'quantity': 1, 'price': self.total_price}]
        
        result = []
        if isinstance(raw_items, list):
            for itm in raw_items:
                if isinstance(itm, dict):
                    qty = itm.get('quantity') or itm.get('qty') or 1
                    price = itm.get('price') or itm.get('unit_price') or 0
                    result.append({
                        'name': itm.get('name') or itm.get('medicine_name') or 'Medicine Item',
                        'quantity': qty,
                        'price': price,
                        'subtotal': round(float(qty) * float(price), 2),
                        'image_url': itm.get('image_url') or '/static/images/medicine_placeholder.png'
                    })
                elif isinstance(itm, str):
                    result.append({
                        'name': itm,
                        'quantity': 1,
                        'price': self.total_price,
                        'subtotal': self.total_price,
                        'image_url': '/static/images/medicine_placeholder.png'
                    })
        return result

    def to_dict(self):
        """Returns serialized representation for modal and API consumption."""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'total_price': self.total_price,
            'total_amount': self.total_amount,
            'order_date': str(self.order_date or ''),
            'status': self.status,
            'payment_method': self.payment_method,
            'tracking_code': self.tracking_code,
            'prescription': self.prescription,
            'recipient_name': self.recipient_name,
            'recipient_phone': self.recipient_phone,
            'recipient_street': self.recipient_street,
            'recipient_landmark': self.recipient_landmark,
            'recipient_city': self.recipient_city,
            'recipient_state': self.recipient_state,
            'recipient_pincode': self.recipient_pincode,
            'formatted_address': self.formatted_shipping_address,
            'items': self.parsed_items
        }


class ActivityLog:
    def __init__(self, id, hospital_id, user_name, action, details, **kwargs):
        self.id = id
        self.hospital_id = hospital_id
        self.user_name = user_name
        self.action = action
        self.details = details
        self.created_at = ensure_safe_date(kwargs.get('created_at', utcnow()))


class Referral:
    def __init__(self, id, patient_id, referring_doctor_id, referred_doctor_id, reason, status='pending', **kwargs):
        self.id = id
        self.patient_id = patient_id
        self.referring_doctor_id = referring_doctor_id
        self.referred_doctor_id = referred_doctor_id
        self.reason = reason
        self.status = status
        self.created_at = ensure_safe_date(kwargs.get('created_at', utcnow()))

    @property
    def patient(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('patients', {}).get(self.patient_id)

    @property
    def referring_doctor(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('doctors', {}).get(self.referring_doctor_id)

    @property
    def referred_doctor(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('doctors', {}).get(self.referred_doctor_id)


class Notification:
    def __init__(self, id, user_id, user_type, message, link=None, status='unread', **kwargs):
        self.id = id
        self.user_id = user_id
        self.user_type = user_type
        self.message = message
        self.link = link
        self.status = status
        self.created_at = ensure_safe_date(kwargs.get('created_at', utcnow()))
