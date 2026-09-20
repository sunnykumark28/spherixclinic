from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user, login_required, logout_user
from spherix.services.database import TEMP_DATA

def patient_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_doctor:
            flash("Access denied. This page is for patients only.", "error")
            return redirect(url_for('login_landing'))
        return f(*args, **kwargs)
    return decorated_function

def doctor_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_doctor:
            flash("Access denied. This page is for doctors only.", "error")
            return redirect(url_for('login_landing'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not hasattr(current_user, 'email') or current_user.email != 'admin@spherixclinic.com':
            flash("You do not have administrative privileges.", "error")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def hospital_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not getattr(current_user, 'is_hospital', False):
            flash("Access denied. This page is for hospital administrators only.", "error")
            return redirect(url_for('login_landing'))
        return f(*args, **kwargs)
    return decorated_function

def staff_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not getattr(current_user, 'is_staff', False):
            flash("Access denied. This page is for hospital staff only.", "error")
            return redirect(url_for('login_landing'))
        return f(*args, **kwargs)
    return decorated_function

def hospital_or_staff_role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            is_hospital = getattr(current_user, 'is_hospital', False)
            is_staff = getattr(current_user, 'is_staff', False)
            
            if is_hospital:
                return f(*args, **kwargs)
            elif is_staff and getattr(current_user, 'role', None) in allowed_roles:
                return f(*args, **kwargs)
            else:
                flash("Access denied. You do not have the required permissions.", "error")
                return redirect(url_for('login_landing'))
        return decorated_function
    return decorator

def staff_role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        @staff_required
        def decorated_function(*args, **kwargs):
            if getattr(current_user, 'role', None) not in allowed_roles:
                flash("Access denied. You do not have permission for this dashboard.", "error")
                return redirect(url_for('staff_dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_common_staff_data(staff_user):
    hospital_name = getattr(staff_user, 'hospital_name', None)
    if not hospital_name:
        return None, None, []

    hospital = next((h for h in TEMP_DATA.get('hospitals', {}).values() if h.name == hospital_name), None)
    activity_logs = []
    if hospital and hasattr(hospital, 'id'):
        activity_logs = [log for log in TEMP_DATA.get('activity_logs', {}).values() if str(log.hospital_id) == str(hospital.id)]
        activity_logs.sort(key=lambda x: x.created_at, reverse=True)
    return hospital_name, hospital, activity_logs
