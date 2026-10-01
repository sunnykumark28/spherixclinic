from datetime import datetime
from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user, login_required, logout_user
from spherix.services.database import TEMP_DATA

def patient_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if getattr(current_user, 'is_doctor', False) and getattr(current_user, 'email', '') != 'admin@spherixclinic.com':
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
            user_role = (getattr(current_user, 'role', '') or '').strip()
            match = False
            for r in allowed_roles:
                r_clean = r.strip()
                if user_role.lower() == r_clean.lower():
                    match = True
                    break
                if r_clean == 'Receptionist' and any(alias in user_role.lower() for alias in ['reception', 'appointment', 'front desk']):
                    match = True
                    break
                if r_clean == 'Bed Management' and 'bed' in user_role.lower():
                    match = True
                    break
                if r_clean == 'Blood Donor Management' and 'blood' in user_role.lower():
                    match = True
                    break
                if r_clean == 'Organ Donor Management' and 'organ' in user_role.lower():
                    match = True
                    break
                if r_clean in ['Nurse', 'Nursing'] and 'nurse' in user_role.lower():
                    match = True
                    break
                if r_clean == 'General Staff':
                    # General staff dashboard allows any valid hospital staff member
                    match = True
                    break
            
            if not match:
                flash(f"Access denied. You do not have permission for the {allowed_roles[0] if allowed_roles else ''} dashboard.", "error")
                return redirect(url_for('staff_dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_common_staff_data(staff_user):
    hospital_id = getattr(staff_user, 'hospital_id', None)
    hospital_name = getattr(staff_user, 'hospital_name', None)
    
    hospital = None
    if hospital_id and str(hospital_id) in TEMP_DATA.get('hospitals', {}):
        hospital = TEMP_DATA['hospitals'][str(hospital_id)]
    elif hospital_id:
        hospital = next((h for h in TEMP_DATA.get('hospitals', {}).values() if str(getattr(h, 'id', '')) == str(hospital_id)), None)

    if not hospital and hospital_name:
        hospital_name_clean = hospital_name.strip().lower()
        hospital = next((h for h in TEMP_DATA.get('hospitals', {}).values() if (getattr(h, 'name', '') or '').strip().lower() == hospital_name_clean), None)
        if not hospital:
            hospital = next((h for h in TEMP_DATA.get('hospitals', {}).values() if hospital_name_clean in (getattr(h, 'name', '') or '').strip().lower() or (getattr(h, 'name', '') or '').strip().lower() in hospital_name_clean), None)

    if hospital:
        hospital_name = hospital.name
        if not getattr(staff_user, 'hospital_id', None):
            staff_user.hospital_id = hospital.id
    elif not hospital_name:
        return None, None, []

    activity_logs = []
    if hospital and hasattr(hospital, 'id'):
        activity_logs = [log for log in TEMP_DATA.get('activity_logs', {}).values() if str(getattr(log, 'hospital_id', '')) == str(hospital.id)]
        activity_logs.sort(key=lambda x: getattr(x, 'created_at', None) or datetime.min, reverse=True)
    return hospital_name, hospital, activity_logs
