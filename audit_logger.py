import functools
import logging
from flask import request
from flask_login import current_user

# Configure logging
logger = logging.getLogger("medical_audit")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [AUDIT] %(message)s'))
    logger.addHandler(ch)

def log_medical_access(action_name="", target_patient_param=None):
    """
    Decorator to log medical record and patient chat access for HIPAA/clinical auditing.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            user_info = "Anonymous"
            if current_user and getattr(current_user, 'is_authenticated', False):
                user_info = f"User(ID: {getattr(current_user, 'id', 'N/A')}, Email: {getattr(current_user, 'email', 'N/A')})"
                
            target_patient = "None"
            if target_patient_param and target_patient_param in kwargs:
                target_patient = str(kwargs[target_patient_param])
                
            logger.info(f"Clinical Access - Operator: {user_info} | Action: {action_name} | Target Patient: {target_patient} | Route: {request.path}")
            return func(*args, **kwargs)
        return wrapper
    return decorator
