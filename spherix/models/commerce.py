from datetime import datetime
from spherix.config import utcnow

class Review:
    def __init__(self, id, doctor_id, patient_id, patient_name, rating, comment=None, **kwargs):
        self.id = id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.rating = int(rating) if rating is not None else 5
        self.comment = comment
        self.created_at = kwargs.get('created_at', utcnow())

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
        if isinstance(dt, str):
            try:
                self.created_at = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except ValueError:
                self.created_at = utcnow()
        else:
            self.created_at = dt

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
        
        created_at_val = kwargs.get('created_at', utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = utcnow()
        self.created_at = created_at_val

    @property
    def doctor(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('doctors', {}).get(self.doctor_id)

    @property
    def patient(self):
        from spherix.services.database import TEMP_DATA
        return TEMP_DATA.get('patients', {}).get(self.patient_id)


class Order:
    def __init__(self, id, patient_id, items, total_price, shipping_address, order_date, status='Processing'):
        self.id = id
        self.patient_id = patient_id
        self.items = items
        self.total_price = total_price
        self.shipping_address = shipping_address
        self.order_date = order_date
        self.status = status


class ActivityLog:
    def __init__(self, id, hospital_id, user_name, action, details, **kwargs):
        self.id = id
        self.hospital_id = hospital_id
        self.user_name = user_name
        self.action = action
        self.details = details
        
        created_at_val = kwargs.get('created_at', utcnow())
        if isinstance(created_at_val, str):
            try:
                created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
            except ValueError:
                created_at_val = utcnow()
        self.created_at = created_at_val


class Referral:
    def __init__(self, id, patient_id, referring_doctor_id, referred_doctor_id, reason, status='pending', **kwargs):
        self.id = id
        self.patient_id = patient_id
        self.referring_doctor_id = referring_doctor_id
        self.referred_doctor_id = referred_doctor_id
        self.reason = reason
        self.status = status
        self.created_at = kwargs.get('created_at', utcnow())

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
        self.created_at = kwargs.get('created_at', utcnow())
