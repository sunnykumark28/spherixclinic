"""
Spherix Diagnostic Network - Enterprise Multi-Tenant Pathology Center Portal
Complete RBAC suite for Pathology Owners, Administrators, Pathologists,
Technicians, Phlebotomists, and Front-Desk Receptionists.
"""

import os
import io
import json
import secrets
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_file, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from spherix.config import (
    COUNTRIES_195, GLOBAL_COUNTRY_FLAGS, GLOBAL_COUNTRY_TIMEZONES,
    format_dual_currency, convert_currency, get_currency_symbol, utcnow
)
from spherix.services.database import TEMP_DATA, save_data
from spherix.services.diagnostic_catalog import (
    DIAGNOSTIC_MASTER_CATEGORIES, MASTER_TESTS_CATALOG, MASTER_PACKAGES_CATALOG,
    get_test_by_code, get_package_by_code
)
from spherix.services.diagnostic_db import (
    get_diagnostic_db, dict_from_row, dict_list_from_rows,
    register_pathology_organization_and_center, authenticate_pathology_staff,
    get_center_analytics_summary, get_diagnostic_order_by_id,
    enter_technician_lab_results, approve_and_release_diagnostic_report,
    update_pathology_center_profile, update_pathology_center_address, update_pathology_staff_profile,
    connect_with_doctor, connect_with_hospital, get_center_doctor_connections, get_center_hospital_connections,
    get_incoming_doctor_prescriptions_and_medicines, respond_hospital_pathology_connection, respond_doctor_pathology_connection,
    get_diagnostic_tests_for_center, toggle_diagnostic_test_visibility, update_diagnostic_test_details,
    add_diagnostic_test
)
from spherix.services.diagnostic_ai import generate_pathologist_ai_summary

pathology_bp = Blueprint('pathology', __name__)

def get_current_pathology_user() -> Optional[Dict[str, Any]]:
    """Helper to retrieve authenticated pathology staff session with full center & location details."""
    staff_id = session.get('pathology_staff_id')
    if not staff_id:
        return None

    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.*, c.center_name, c.branch_name, c.email as center_email, c.phone as center_phone,
           c.address, c.address_name, c.landmark, c.address_additional_info, c.city, c.state_province,
           c.postal_code, c.country, c.latitude, c.longitude, c.timezone, c.currency, c.verification_status,
           c.home_collection_enabled, c.walkin_enabled, c.home_collection_fee, c.home_collection_radius_km,
           c.min_order_amount, c.profile_image as center_logo, c.website as center_website,
           c.emergency_phone, c.operating_hours, c.is_nabl_accredited, c.is_cap_accredited, c.is_iso_certified,
           o.legal_name as org_name, o.website as org_website
    FROM pathology_staff s
    JOIN pathology_centers c ON s.center_id = c.id
    JOIN pathology_organizations o ON s.organization_id = o.id
    WHERE s.id = ? AND s.is_active = 1
    """, (staff_id,))
    staff_row = cursor.fetchone()
    conn.close()

    return dict(staff_row) if staff_row else None

def pathology_login_required(f):
    """Decorator ensuring request has an active pathology staff session."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_pathology_user()
        if not user:
            flash("Please log in to your Pathology Center portal.", "info")
            return redirect(url_for('pathology.pathology_login'))
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# 1. AUTHENTICATION & REGISTRATION
# ==============================================================================

@pathology_bp.route('/pathology/login', methods=['GET', 'POST'])
def pathology_login():
    """Pathology Staff & Administrator Login."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        staff = authenticate_pathology_staff(email, password)
        if staff:
            session['pathology_staff_id'] = staff['id']
            session['pathology_center_id'] = staff['center_id']
            session['pathology_org_id'] = staff['organization_id']
            session['pathology_role'] = staff['role']
            session['pathology_name'] = staff['full_name']
            session['pathology_center_name'] = staff['center_name']
            session['_user_type'] = 'pathology'

            flash(f"Welcome back, {staff['full_name']} ({staff['role'].replace('_', ' ').title()})", "success")
            
            # Role-specific redirect
            if staff['role'] == 'phlebotomist':
                return redirect(url_for('pathology.phlebotomy_collections'))
            elif staff['role'] == 'receptionist':
                return redirect(url_for('pathology.walkin_queue_view'))
            return redirect(url_for('pathology.pathology_dashboard'))
        else:
            flash("Invalid laboratory credentials or inactive account.", "error")

    return render_template('pathology_login.html')

@pathology_bp.route('/pathology/logout')
def pathology_logout():
    """Clears pathology session."""
    session.pop('pathology_staff_id', None)
    session.pop('pathology_center_id', None)
    session.pop('pathology_org_id', None)
    session.pop('pathology_role', None)
    session.pop('pathology_name', None)
    session.pop('pathology_center_name', None)
    if session.get('_user_type') == 'pathology':
        session.pop('_user_type', None)

    flash("You have been securely logged out from the Pathology Portal.", "info")
    return redirect(url_for('pathology.pathology_login'))

@pathology_bp.route('/pathology/register', methods=['GET', 'POST'])
def pathology_register():
    """5-Step Global Pathology Center Registration Wizard."""
    if request.method == 'POST':
        # 1. Organization
        org_data = {
            "legal_name": request.form.get('legal_name', '').strip(),
            "display_name": request.form.get('display_name', '').strip(),
            "org_type": request.form.get('org_type', 'Clinical Diagnostic Center'),
            "reg_number": request.form.get('reg_number', '').strip(),
            "license_number": request.form.get('license_number', '').strip(),
            "accreditation": request.form.get('accreditation', 'State Health Department'),
            "website": request.form.get('website', '').strip(),
            "email": request.form.get('org_email', '').strip(),
            "phone": request.form.get('org_phone', '').strip(),
            "country": request.form.get('country', 'India'),
            "currency": request.form.get('currency', 'INR'),
            "timezone": request.form.get('timezone', 'IST (UTC+5:30)'),
            "tax_rate_percent": float(request.form.get('tax_rate_percent', 0.0) or 0.0)
        }

        # 2. Location
        center_data = {
            "center_name": request.form.get('center_name', org_data['legal_name']),
            "branch_name": request.form.get('branch_name', 'Main Facility'),
            "email": request.form.get('center_email', org_data['email']),
            "phone": request.form.get('center_phone', org_data['phone']),
            "address": request.form.get('address', '').strip(),
            "city": request.form.get('city', '').strip(),
            "state_province": request.form.get('state_province', '').strip(),
            "postal_code": request.form.get('postal_code', '').strip(),
            "country": org_data['country'],
            "latitude": float(request.form.get('latitude', 0.0) or 0.0),
            "longitude": float(request.form.get('longitude', 0.0) or 0.0),
            "home_collection_enabled": 'home_collection' in request.form,
            "walkin_enabled": 'walkin' in request.form,
            "home_collection_radius_km": float(request.form.get('collection_radius', 25.0) or 25.0),
            "home_collection_fee": float(request.form.get('collection_fee', 150.0) or 150.0),
            "min_order_amount": float(request.form.get('min_order', 200.0) or 200.0)
        }

        # 3. Administrator
        admin_data = {
            "full_name": request.form.get('admin_name', '').strip(),
            "email": request.form.get('admin_email', '').strip(),
            "password": request.form.get('admin_password', ''),
            "phone": request.form.get('admin_phone', org_data['phone']),
            "qualification": request.form.get('admin_qualification', 'Chief Pathologist'),
            "license_number": request.form.get('admin_license', org_data['license_number'])
        }

        # Handle uploaded document files
        documents = []
        if 'license_doc' in request.files:
            f = request.files['license_doc']
            if f and f.filename:
                fname = f"LIC_{secrets.token_hex(4)}_{f.filename}"
                fpath = os.path.join(current_app.root_path, 'uploads', 'diagnostic_reports', fname)
                try:
                    f.save(fpath)
                    documents.append({
                        "doc_type": "Laboratory Operating License",
                        "file_name": fname,
                        "file_path": fpath,
                        "original_name": f.filename,
                        "mime_type": f.content_type,
                        "file_size": os.path.getsize(fpath)
                    })
                except Exception as upload_err:
                    print(f"Document upload notice: {upload_err}")

        success, msg, res_data = register_pathology_organization_and_center(
            org_data=org_data,
            center_data=center_data,
            admin_data=admin_data,
            documents=documents
        )

        if success:
            flash(msg, "success")
            return redirect(url_for('pathology.pathology_login'))
        else:
            flash(msg, "error")

    return render_template('pathology_register.html', countries=COUNTRIES_195)

# ==============================================================================
# 2. PATHOLOGY DASHBOARD & WORKBENCH
# ==============================================================================

@pathology_bp.route('/pathology/dashboard')
@pathology_login_required
def pathology_dashboard():
    """Main Operational Dashboard for Pathology Centers."""
    user = get_current_pathology_user()
    center_id = user['center_id']

    analytics = get_center_analytics_summary(center_id)

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    # Recent Orders
    cursor.execute("""
    SELECT o.*, (SELECT COUNT(*) FROM diagnostic_order_items WHERE order_id = o.id) as item_count
    FROM diagnostic_orders o
    WHERE o.center_id = ?
    ORDER BY o.created_at DESC LIMIT 10
    """, (center_id,))
    recent_orders = dict_list_from_rows(cursor.fetchall())

    # Active Phlebotomists
    cursor.execute("SELECT * FROM pathology_staff WHERE center_id = ? AND role = 'phlebotomist' AND is_active = 1", (center_id,))
    phlebotomists = dict_list_from_rows(cursor.fetchall())

    # Active Samples
    cursor.execute("""
    SELECT s.*, o.order_number, o.patient_name
    FROM sample_records s
    JOIN diagnostic_orders o ON s.order_id = o.id
    WHERE s.center_id = ? AND s.status NOT IN ('COMPLETED', 'REJECTED')
    ORDER BY s.created_at DESC LIMIT 8
    """, (center_id,))
    active_samples = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'pathology_dashboard.html',
        user=user,
        analytics=analytics,
        recent_orders=recent_orders,
        orders=recent_orders,
        phlebotomists=phlebotomists,
        active_samples=active_samples
    )

# ==============================================================================
# 3. ORDERS MANAGEMENT
# ==============================================================================

@pathology_bp.route('/pathology/orders')
@pathology_login_required
def orders_list():
    """All Orders workbench with status filter tabs."""
    user = get_current_pathology_user()
    center_id = user['center_id']
    status_filter = request.args.get('status', 'ALL').upper()
    search = request.args.get('q', '').strip()

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    query = """
    SELECT o.*, (SELECT COUNT(*) FROM diagnostic_order_items WHERE order_id = o.id) as item_count,
           (SELECT status FROM sample_records WHERE order_id = o.id LIMIT 1) as sample_status,
           (SELECT report_number FROM lab_reports WHERE order_id = o.id LIMIT 1) as report_number
    FROM diagnostic_orders o
    WHERE o.center_id = ?
    """
    params = [center_id]

    if status_filter and status_filter != 'ALL':
        query += " AND o.status = ?"
        params.append(status_filter)

    if search:
        query += " AND (o.order_number LIKE ? OR o.patient_name LIKE ? OR o.patient_phone LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    query += " ORDER BY o.created_at DESC"

    cursor.execute(query, params)
    orders = dict_list_from_rows(cursor.fetchall())

    # Fetch Phlebotomists for assignment dropdowns
    cursor.execute("SELECT * FROM pathology_staff WHERE center_id = ? AND role = 'phlebotomist' AND is_active = 1", (center_id,))
    phlebotomists = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'pathology_dashboard.html',
        view_tab='orders',
        user=user,
        orders=orders,
        status_filter=status_filter,
        search_query=search,
        phlebotomists=phlebotomists
    )

@pathology_bp.route('/pathology/orders/<order_id>')
@pathology_login_required
def order_workspace(order_id):
    """Detailed Order Workspace for clinical execution, results, and reporting."""
    user = get_current_pathology_user()
    order = get_diagnostic_order_by_id(order_id)

    if not order or order['center_id'] != user['center_id']:
        flash("Order not found or unauthorized.", "error")
        return redirect(url_for('pathology.orders_list'))

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM pathology_staff WHERE center_id = ? AND role = 'phlebotomist' AND is_active = 1", (user['center_id'],))
    phlebotomists = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'pathology_dashboard.html',
        view_tab='order_detail',
        user=user,
        order=order,
        phlebotomists=phlebotomists
    )

@pathology_bp.route('/pathology/orders/<order_id>/assign-phlebotomist', methods=['POST'])
@pathology_login_required
def assign_phlebotomist(order_id):
    """Assigns phlebotomist to a doorstep collection order."""
    user = get_current_pathology_user()
    phlebotomist_id = request.form.get('phlebotomist_id', '')

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("SELECT full_name FROM pathology_staff WHERE id = ? AND center_id = ?", (phlebotomist_id, user['center_id']))
    phlebo = cursor.fetchone()
    if not phlebo:
        conn.close()
        flash("Selected phlebotomist not found.", "error")
        return redirect(url_for('pathology.order_workspace', order_id=order_id))

    phlebo_name = phlebo['full_name']

    cursor.execute("""
    INSERT OR REPLACE INTO collection_assignments (id, order_id, center_id, phlebotomist_id, phlebotomist_name, status, assigned_at)
    VALUES (?, ?, ?, ?, ?, 'ASSIGNED', CURRENT_TIMESTAMP)
    """, (f"ASG-{order_id}", order_id, user['center_id'], phlebotomist_id, phlebo_name))

    cursor.execute("""
    UPDATE diagnostic_orders SET status = 'COLLECTOR_ASSIGNED', updated_at = CURRENT_TIMESTAMP WHERE id = ?
    """, (order_id,))

    conn.commit()
    conn.close()

    flash(f"Assigned {phlebo_name} to Order #{order_id}", "success")
    return redirect(url_for('pathology.order_workspace', order_id=order_id))

@pathology_bp.route('/pathology/orders/<order_id>/update-status', methods=['POST'])
@pathology_login_required
def update_order_status(order_id):
    """Updates status of an order."""
    user = get_current_pathology_user()
    new_status = request.form.get('status', '').upper()
    notes = request.form.get('notes', '')

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM diagnostic_orders WHERE id = ? AND center_id = ?", (order_id, user['center_id']))
    if not cursor.fetchone():
        conn.close()
        flash("Order not found or unauthorized.", "error")
        return redirect(url_for('pathology.orders_list'))

    cursor.execute("""
    UPDATE diagnostic_orders SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
    """, (new_status, notes, order_id))

    if new_status == 'SAMPLE_RECEIVED':
        cursor.execute("UPDATE sample_records SET status = 'RECEIVED', updated_at = CURRENT_TIMESTAMP WHERE order_id = ?", (order_id,))
    elif new_status == 'PROCESSING':
        cursor.execute("UPDATE sample_records SET status = 'PROCESSING', updated_at = CURRENT_TIMESTAMP WHERE order_id = ?", (order_id,))

    conn.commit()
    conn.close()

    flash(f"Order status updated to {new_status}", "success")
    return redirect(url_for('pathology.order_workspace', order_id=order_id))

# ==============================================================================
# 4. PHLEBOTOMIST FIELD DASHBOARD
# ==============================================================================

@pathology_bp.route('/pathology/collections')
@pathology_login_required
def phlebotomy_collections():
    """Mobile/Field Dashboard for Phlebotomists."""
    user = get_current_pathology_user()
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    # Filter assignments for logged in phlebotomist
    query = """
    SELECT a.*, o.order_number, o.patient_name, o.patient_phone, o.patient_address,
           o.scheduled_date, o.scheduled_slot, o.total_amount, o.currency, o.payment_status,
           (SELECT sample_code FROM sample_records WHERE order_id = o.id LIMIT 1) as sample_code
    FROM collection_assignments a
    JOIN diagnostic_orders o ON a.order_id = o.id
    WHERE a.center_id = ?
    """
    params = [user['center_id']]
    if user['role'] == 'phlebotomist':
        query += " AND (a.phlebotomist_id = ? OR a.phlebotomist_id IS NULL)"
        params.append(user['id'])

    query += " ORDER BY o.scheduled_date ASC, a.created_at DESC"

    cursor.execute(query, params)
    assignments = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'pathology_dashboard.html',
        view_tab='collections',
        user=user,
        assignments=assignments
    )

@pathology_bp.route('/pathology/collections/<assignment_id>/action', methods=['POST'])
@pathology_login_required
def phlebotomist_action(assignment_id):
    """Phlebotomist workflow: ON_THE_WAY, ARRIVED, PATIENT_VERIFIED, SAMPLE_COLLECTED."""
    user = get_current_pathology_user()
    action = request.form.get('action', '').upper()
    notes = request.form.get('notes', '')

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("SELECT order_id FROM collection_assignments WHERE id = ? AND center_id = ?", (assignment_id, user['center_id']))
    asg = cursor.fetchone()
    if not asg:
        conn.close()
        flash("Assignment not found.", "error")
        return redirect(url_for('pathology.phlebotomy_collections'))

    order_id = asg['order_id']

    if action == 'START_JOURNEY':
        cursor.execute("UPDATE collection_assignments SET status = 'ON_THE_WAY' WHERE id = ?", (assignment_id,))
    elif action == 'ARRIVED':
        cursor.execute("UPDATE collection_assignments SET status = 'ARRIVED', arrived_at = CURRENT_TIMESTAMP WHERE id = ?", (assignment_id,))
    elif action == 'SAMPLE_COLLECTED':
        cursor.execute("UPDATE collection_assignments SET status = 'SAMPLE_COLLECTED', collected_at = CURRENT_TIMESTAMP WHERE id = ?", (assignment_id,))
        cursor.execute("UPDATE diagnostic_orders SET status = 'SAMPLE_COLLECTED', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order_id,))
        cursor.execute("""
        UPDATE sample_records SET status = 'COLLECTED', collected_by = ?, collected_at = CURRENT_TIMESTAMP WHERE order_id = ?
        """, (user['full_name'], order_id))

    conn.commit()
    conn.close()

    flash(f"Collection status updated to {action}", "success")
    return redirect(url_for('pathology.phlebotomy_collections'))

# ==============================================================================
# 5. LAB RESULTS ENTRY & PATHOLOGIST AUTHORIZATION
# ==============================================================================

@pathology_bp.route('/pathology/results/<order_id>', methods=['GET', 'POST'])
@pathology_login_required
def lab_results_entry(order_id):
    """Lab Technician test result entry interface."""
    user = get_current_pathology_user()
    order = get_diagnostic_order_by_id(order_id)

    if not order or order['center_id'] != user['center_id']:
        flash("Order not found or unauthorized.", "error")
        return redirect(url_for('pathology.orders_list'))

    if request.method == 'POST':
        param_names = request.form.getlist('param_name[]')
        param_values = request.form.getlist('param_val[]')
        param_units = request.form.getlist('param_unit[]')
        param_ranges = request.form.getlist('param_range[]')
        param_flags = request.form.getlist('param_flag[]')
        test_names = request.form.getlist('test_name[]')
        tech_notes = request.form.get('technician_notes', '')

        results_list = []
        for i in range(len(param_names)):
            if param_names[i].strip():
                results_list.append({
                    "test_name": test_names[i] if i < len(test_names) else "Diagnostic Test",
                    "parameter_name": param_names[i].strip(),
                    "result_value": param_values[i].strip() if i < len(param_values) else "",
                    "unit": param_units[i].strip() if i < len(param_units) else "",
                    "reference_range": param_ranges[i].strip() if i < len(param_ranges) else "",
                    "abnormal_flag": param_flags[i].strip() if i < len(param_flags) else "NORMAL"
                })

        success, msg = enter_technician_lab_results(
            order_id=order_id,
            technician_id=user['id'],
            technician_name=user['full_name'],
            results_list=results_list,
            notes=tech_notes
        )

        if success:
            flash("Test observations saved and queued for Pathologist Review.", "success")
            return redirect(url_for('pathology.order_workspace', order_id=order_id))
        else:
            flash(f"Error saving results: {msg}", "error")

    # Build default parameters from master tests if results not yet entered
    preset_params = []
    if not order['results']:
        for itm in order['items']:
            t = get_test_by_code(itm.get('item_code'))
            if t and t.get('parameters'):
                for p in t['parameters']:
                    preset_params.append({
                        "test_name": t['name'],
                        "parameter_name": p['name'],
                        "result_value": "",
                        "unit": p.get('unit', ''),
                        "reference_range": p.get('ref_general', 'Normal'),
                        "abnormal_flag": "NORMAL"
                    })

    return render_template(
        'pathology_dashboard.html',
        view_tab='result_entry',
        user=user,
        order=order,
        preset_params=preset_params
    )

@pathology_bp.route('/pathology/reports')
@pathology_login_required
def reports_workbench():
    """Pathologist authorization and released reports desk."""
    user = get_current_pathology_user()
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    # Pending Authorization (Status: REPORT_PENDING)
    cursor.execute("""
    SELECT o.*, (SELECT COUNT(*) FROM lab_results WHERE order_id = o.id) as result_count
    FROM diagnostic_orders o
    WHERE o.center_id = ? AND o.status = 'REPORT_PENDING'
    ORDER BY o.updated_at ASC
    """, (user['center_id'],))
    pending_approval = dict_list_from_rows(cursor.fetchall())

    # Released Reports
    cursor.execute("""
    SELECT r.*, o.order_number, o.patient_name, o.scheduled_date
    FROM lab_reports r
    JOIN diagnostic_orders o ON r.order_id = o.id
    WHERE r.center_id = ?
    ORDER BY r.released_at DESC LIMIT 50
    """, (user['center_id'],))
    released_reports = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'pathology_dashboard.html',
        view_tab='reports',
        user=user,
        pending_approval=pending_approval,
        released_reports=released_reports
    )

@pathology_bp.route('/pathology/reports/<order_id>/release', methods=['POST'])
@pathology_login_required
def release_report(order_id):
    """Pathologist digital sign-off and public release of diagnostic report."""
    user = get_current_pathology_user()
    summary = request.form.get('summary', 'Specimen analyzed using standard verified protocols. Results within normal limits.')
    interpretation = request.form.get('interpretation', 'No acute biological abnormality detected.')
    is_correction = request.form.get('is_correction') == '1'
    correction_reason = request.form.get('correction_reason')

    success, msg, rep_data = approve_and_release_diagnostic_report(
        order_id=order_id,
        pathologist_id=user['id'],
        pathologist_name=user['full_name'],
        summary=summary,
        interpretation=interpretation,
        is_correction=is_correction,
        correction_reason=correction_reason
    )

    if success:
        flash(f"Report {rep_data['report_number']} ({rep_data['version']}) released successfully.", "success")
        return redirect(url_for('pathology.reports_workbench'))
    else:
        flash(f"Release failed: {msg}", "error")
        return redirect(url_for('pathology.order_workspace', order_id=order_id))

@pathology_bp.route('/api/pathology/generate-ai-summary', methods=['POST'])
@pathology_login_required
def api_generate_pathology_ai_summary():
    """Generates an AI-assisted impression and summary for lab results using Groq."""
    user = get_current_pathology_user()
    order_id = request.json.get('order_id') if request.is_json else request.form.get('order_id')

    if not order_id:
        return jsonify({"success": False, "error": "Order ID is required"}), 400

    order = get_diagnostic_order_by_id(order_id)
    if not order or order['center_id'] != user['center_id']:
        return jsonify({"success": False, "error": "Order not found or unauthorized"}), 404

    results = order.get('results', [])
    if not results:
        return jsonify({"success": False, "error": "No laboratory results entered yet for this order."}), 400

    patient_meta = {
        "name": order.get('patient_name'),
        "gender": order.get('patient_gender', 'Adult'),
        "age": order.get('patient_age', 'Adult')
    }

    ai_draft = generate_pathologist_ai_summary(results, patient_meta)
    return jsonify({
        "success": True,
        "summary": ai_draft.get('summary', ''),
        "interpretation": ai_draft.get('interpretation', '')
    })

# ==============================================================================
# 6. DOCTOR REFERRALS & DISCOVERY
# ==============================================================================

@pathology_bp.route('/pathology/doctors')
@pathology_bp.route('/pathology/hospitals', endpoint='hospitals_discovery')
@pathology_login_required
def doctors_discovery():
    """Discover regional doctors and hospitals, view incoming referrals, and manage partnerships."""
    user = get_current_pathology_user()
    country = request.args.get('country', user['country']).strip()
    specialty = request.args.get('specialty', '').strip()
    search = request.args.get('q', '').strip().lower()
    sub_tab = request.args.get('tab', 'doctors').strip() # 'doctors', 'hospitals', 'referrals'

    # 1. Doctors from Spherix Master TEMP_DATA
    all_doctors = list(TEMP_DATA.get('doctors', {}).values())
    filtered_doctors = all_doctors

    if country and country != 'All':
        filtered_doctors = [d for d in filtered_doctors if getattr(d, 'country', '').lower() == country.lower()]
    if specialty:
        filtered_doctors = [d for d in filtered_doctors if specialty.lower() in getattr(d, 'specialization', '').lower() or specialty.lower() in getattr(d, 'department', '').lower()]
    if search:
        filtered_doctors = [d for d in filtered_doctors if search in f"{getattr(d, 'first_name', '')} {getattr(d, 'last_name', '')}".lower() or search in getattr(d, 'hospital_name', '').lower()]

    # 2. Hospitals from Spherix Master TEMP_DATA
    all_hospitals = list(TEMP_DATA.get('hospitals', {}).values())
    filtered_hospitals = all_hospitals
    if search:
        filtered_hospitals = [h for h in filtered_hospitals if search in getattr(h, 'name', '').lower() or search in getattr(h, 'address', '').lower()]

    # 3. Existing Connections & Incoming referrals + medicines
    doctor_conns = get_center_doctor_connections(user['center_id'])
    hospital_conns = get_center_hospital_connections(user['center_id'])

    doctor_conn_map = {str(c['doctor_id']): c for c in doctor_conns}
    hospital_conn_map = {str(c['hospital_id']): c for c in hospital_conns}

    connected_doctor_ids = {str(c['doctor_id']) for c in doctor_conns if c['status'] == 'ACCEPTED'}
    connected_hospital_ids = {str(c['hospital_id']) for c in hospital_conns if c['status'] == 'ACCEPTED'}

    incoming_referrals = get_incoming_doctor_prescriptions_and_medicines(user['center_id'])

    return render_template(
        'pathology_dashboard.html',
        view_tab='doctors',
        sub_tab=sub_tab,
        user=user,
        doctors=filtered_doctors,
        hospitals=filtered_hospitals,
        doctor_conns=doctor_conns,
        hospital_conns=hospital_conns,
        doctor_conn_map=doctor_conn_map,
        hospital_conn_map=hospital_conn_map,
        connected_doctor_ids=connected_doctor_ids,
        connected_hospital_ids=connected_hospital_ids,
        incoming_referrals=incoming_referrals,
        selected_country=country,
        countries=COUNTRIES_195
    )

@pathology_bp.route('/pathology/connect/doctor', methods=['POST'])
@pathology_login_required
def connect_doctor_action():
    """Connect with a Doctor to receive digital diagnostic referrals."""
    user = get_current_pathology_user()
    doctor_id = request.form.get('doctor_id')
    notes = request.form.get('notes', 'Direct pathology network partnership agreement')
    partnership_type = request.form.get('partnership_type', 'ROUTINE_DIAGNOSTICS')

    if not doctor_id:
        flash("Doctor selection is required.", "error")
        return redirect(url_for('pathology.doctors_discovery'))

    doc_obj = TEMP_DATA.get('doctors', {}).get(doctor_id)
    doc_name = f"Dr. {doc_obj.first_name} {doc_obj.last_name}" if doc_obj else None
    hosp_id = getattr(doc_obj, 'hospital_id', None) if doc_obj else None
    hosp_name = getattr(doc_obj, 'hospital_name', None) if doc_obj else None

    success, msg = connect_with_doctor(
        center_id=user['center_id'],
        doctor_id=doctor_id,
        notes=notes,
        partnership_type=partnership_type,
        requested_by='PATHOLOGY',
        doctor_name=doc_name,
        center_name=user.get('center_name'),
        hospital_id=hosp_id,
        hospital_name=hosp_name
    )
    if success:
        flash(msg, "success")
    else:
        flash(f"Connection failed: {msg}", "error")
    return redirect(url_for('pathology.doctors_discovery', tab='doctors'))

@pathology_bp.route('/pathology/connect/hospital', methods=['POST'])
@pathology_login_required
def connect_hospital_action():
    """Connect with a Hospital for laboratory diagnostic services."""
    user = get_current_pathology_user()
    hospital_id = request.form.get('hospital_id')
    doctor_id = request.form.get('doctor_id')
    notes = request.form.get('notes', 'Hospital diagnostic testing tie-up agreement')
    partnership_type = request.form.get('partnership_type', 'SPECIALIZED_TESTING')

    if not hospital_id:
        flash("Hospital selection is required.", "error")
        return redirect(url_for('pathology.doctors_discovery', tab='hospitals'))

    hosp_obj = TEMP_DATA.get('hospitals', {}).get(hospital_id)
    hosp_name = getattr(hosp_obj, 'name', None) if hosp_obj else None

    doc_name = None
    if doctor_id:
        doc_obj = TEMP_DATA.get('doctors', {}).get(doctor_id)
        doc_name = f"Dr. {doc_obj.first_name} {doc_obj.last_name}" if doc_obj else None

    success, msg = connect_with_hospital(
        center_id=user['center_id'],
        hospital_id=hospital_id,
        doctor_id=doctor_id,
        notes=notes,
        partnership_type=partnership_type,
        requested_by='PATHOLOGY',
        doctor_name=doc_name,
        hospital_name=hosp_name,
        center_name=user.get('center_name')
    )
    if success:
        flash(msg, "success")
    else:
        flash(f"Hospital tie-up failed: {msg}", "error")
    return redirect(url_for('pathology.doctors_discovery', tab='hospitals'))

@pathology_bp.route('/pathology/connection/<conn_id>/respond', methods=['POST'])
@pathology_login_required
def respond_connection_action(conn_id):
    """Pathology center responds (accept/reject) to an incoming hospital/doctor connection request."""
    user = get_current_pathology_user()
    action = request.form.get('action', 'accept')
    notes = request.form.get('notes')
    conn_type = request.form.get('conn_type', 'hospital') # 'hospital' or 'doctor'

    if conn_type == 'hospital':
        from spherix.services.diagnostic_db import respond_hospital_pathology_connection
        success, msg, data = respond_hospital_pathology_connection(conn_id, actor_role='pathology', action=action, notes=notes)
    else:
        from spherix.services.diagnostic_db import respond_doctor_pathology_connection
        success, msg, data = respond_doctor_pathology_connection(conn_id, action=action, notes=notes)

    if success:
        flash(msg, "success")
    else:
        flash(f"Response failed: {msg}", "error")
    return redirect(url_for('pathology.doctors_discovery', tab='hospitals' if conn_type == 'hospital' else 'doctors'))

# ==============================================================================
# 7. SETTINGS & PROFILE MANAGEMENT
# ==============================================================================

@pathology_bp.route('/pathology/settings')
@pathology_login_required
def pathology_settings():
    """Pathology Center Profile, Address & Staff Settings."""
    user = get_current_pathology_user()
    active_subtab = request.args.get('tab', 'profile').strip()

    return render_template(
        'pathology_dashboard.html',
        view_tab='settings',
        settings_tab=active_subtab,
        user=user,
        countries=COUNTRIES_195
    )

@pathology_bp.route('/pathology/settings/profile', methods=['POST'])
@pathology_login_required
def update_profile_settings():
    """Saves center profile details, operating hours, home collection and profile image."""
    user = get_current_pathology_user()
    
    # Check for image upload
    profile_image_path = None
    if 'profile_image' in request.files:
        f = request.files['profile_image']
        if f and f.filename:
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'diagnostic_reports')
            os.makedirs(upload_dir, exist_ok=True)
            fname = f"LOGO_{secrets.token_hex(4)}_{f.filename.replace(' ', '_')}"
            fpath = os.path.join(upload_dir, fname)
            f.save(fpath)
            profile_image_path = f"/static/uploads/diagnostic_reports/{fname}"

    data = {
        "center_name": request.form.get('center_name', user['center_name']),
        "branch_name": request.form.get('branch_name', user['branch_name']),
        "legal_name": request.form.get('legal_name', user['org_name']),
        "email": request.form.get('email', user['email']),
        "phone": request.form.get('phone', user['center_phone']),
        "website": request.form.get('website', user.get('center_website')),
        "emergency_phone": request.form.get('emergency_phone', user.get('emergency_phone')),
        "operating_hours": request.form.get('operating_hours', user.get('operating_hours', '07:00 AM - 08:00 PM')),
        "is_nabl_accredited": 'is_nabl_accredited' in request.form,
        "is_cap_accredited": 'is_cap_accredited' in request.form,
        "is_iso_certified": 'is_iso_certified' in request.form,
        "home_collection_enabled": 'home_collection_enabled' in request.form,
        "walkin_enabled": 'walkin_enabled' in request.form,
        "home_collection_radius_km": float(request.form.get('home_collection_radius_km') or 25.0),
        "home_collection_fee": float(request.form.get('home_collection_fee') or 150.0),
        "min_order_amount": float(request.form.get('min_order_amount') or 200.0),
        "profile_image": profile_image_path
    }

    success, msg = update_pathology_center_profile(user['center_id'], data)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return redirect(url_for('pathology.pathology_settings', tab='profile'))

@pathology_bp.route('/pathology/settings/address', methods=['POST'])
@pathology_login_required
def update_address_settings():
    """Saves center address name, location coordinates, landmark, and directions."""
    user = get_current_pathology_user()

    address_data = {
        "address_name": request.form.get('address_name', 'Main Facility Address').strip(),
        "address": (request.form.get('address') or request.form.get('address_line') or '').strip(),
        "landmark": request.form.get('landmark', '').strip(),
        "address_additional_info": request.form.get('address_additional_info', '').strip(),
        "city": request.form.get('city', '').strip(),
        "state_province": request.form.get('state_province', request.form.get('state', '')).strip(),
        "postal_code": request.form.get('postal_code', '').strip(),
        "country": request.form.get('country', 'India').strip(),
        "latitude": float(request.form.get('latitude', 0.0) or 0.0),
        "longitude": float(request.form.get('longitude', 0.0) or 0.0),
        "timezone": request.form.get('timezone', 'IST (UTC+5:30)').strip()
    }

    success, msg = update_pathology_center_address(user['center_id'], address_data)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return redirect(url_for('pathology.pathology_settings', tab='address'))

@pathology_bp.route('/pathology/settings/staff', methods=['POST'])
@pathology_login_required
def update_staff_settings():
    """Saves administrator profile info and avatar image."""
    user = get_current_pathology_user()

    staff_image_path = None
    if 'profile_image' in request.files:
        f = request.files['profile_image']
        if f and f.filename:
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'diagnostic_reports')
            os.makedirs(upload_dir, exist_ok=True)
            fname = f"STAFF_{secrets.token_hex(4)}_{f.filename.replace(' ', '_')}"
            fpath = os.path.join(upload_dir, fname)
            f.save(fpath)
            staff_image_path = f"/static/uploads/diagnostic_reports/{fname}"

    staff_data = {
        "full_name": request.form.get('full_name', user['full_name']).strip(),
        "email": request.form.get('email', user['email']).strip(),
        "phone": request.form.get('phone', user.get('phone', '')).strip(),
        "qualification": request.form.get('qualification', user.get('qualification', '')).strip(),
        "license_number": request.form.get('license_number', user.get('license_number', '')).strip(),
        "bio": request.form.get('bio', user.get('bio', '')).strip(),
        "profile_image": staff_image_path
    }

    success, msg = update_pathology_staff_profile(user['id'], staff_data)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return redirect(url_for('pathology.pathology_settings', tab='staff'))

# ==============================================================================
# 8. TESTS & PACKAGES MANAGEMENT
# ==============================================================================

@pathology_bp.route('/pathology/tests')
@pathology_login_required
def tests_management():
    """Manage test catalog, promotional discounts, offer prices, and public visibility."""
    user = get_current_pathology_user()
    category_filter = request.args.get('category', '').strip()
    status_filter = request.args.get('status', '').strip() # 'public', 'hidden', ''
    search_q = request.args.get('q', '').strip().lower()

    tests = get_diagnostic_tests_for_center(user['center_id'])

    if category_filter:
        tests = [t for t in tests if t.get('category_name') == category_filter or t.get('category_id') == category_filter]
    if status_filter == 'public':
        tests = [t for t in tests if (t.get('is_active') == 1 and (t.get('is_public') is None or t.get('is_public') == 1))]
    elif status_filter == 'hidden':
        tests = [t for t in tests if (t.get('is_active') == 0 or t.get('is_public') == 0)]
    if search_q:
        tests = [t for t in tests if search_q in (t.get('test_name') or '').lower() or search_q in (t.get('test_code') or '').lower() or search_q in (t.get('description') or '').lower()]

    return render_template(
        'pathology_dashboard.html',
        view_tab='tests_management',
        user=user,
        tests=tests,
        categories=DIAGNOSTIC_MASTER_CATEGORIES,
        selected_category=category_filter,
        selected_status=status_filter,
        search_query=search_q
    )

@pathology_bp.route('/pathology/tests/<test_id>/toggle-visibility', methods=['POST'])
@pathology_login_required
def toggle_test_visibility_action(test_id):
    """Toggle public visibility for a test in the center catalog."""
    user = get_current_pathology_user()
    success, msg, new_state = toggle_diagnostic_test_visibility(test_id, user['center_id'])
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return redirect(url_for('pathology.tests_management'))

@pathology_bp.route('/pathology/tests/<test_id>/update', methods=['POST'])
@pathology_login_required
def update_test_pricing_action(test_id):
    """Updates custom center pricing, discount percentage, promotional badge, and pre-test instructions."""
    user = get_current_pathology_user()
    form_data = request.form.to_dict()
    
    success, msg = update_diagnostic_test_details(test_id, user['center_id'], form_data)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return redirect(url_for('pathology.tests_management'))

@pathology_bp.route('/pathology/tests/add', methods=['POST'])
@pathology_login_required
def add_diagnostic_test_action():
    """Adds a new test to the center's diagnostic test catalog."""
    user = get_current_pathology_user()
    form_data = request.form.to_dict()
    success, msg, new_test_id = add_diagnostic_test(user['center_id'], form_data)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return redirect(url_for('pathology.tests_management'))

@pathology_bp.route('/pathology/walkins')
@pathology_login_required
def walkin_queue_view():
    """Front-desk Receptionist Walk-in Token Calling Desk."""
    user = get_current_pathology_user()
    today_str = date.today().strftime("%Y-%m-%d")

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT w.*, o.order_number, o.patient_name, o.patient_phone, o.total_amount, o.currency, o.payment_status,
           (SELECT GROUP_CONCAT(item_name, ', ') FROM diagnostic_order_items WHERE order_id = o.id) as prescribed_tests
    FROM walkin_queue w
    JOIN diagnostic_orders o ON w.order_id = o.id
    WHERE w.center_id = ? AND w.appointment_date = ?
    ORDER BY w.token_number ASC
    """, (user['center_id'], today_str))
    queue_items = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'pathology_dashboard.html',
        view_tab='walkin_queue',
        user=user,
        queue_items=queue_items
    )

@pathology_bp.route('/pathology/walkins/<queue_id>/call', methods=['POST'])
@pathology_login_required
def walkin_call_token(queue_id):
    """Calls a token to a specific Phlebotomy chair (Chair 1, 2, 3) and announces it."""
    user = get_current_pathology_user()
    chair = request.form.get('chair', 'Phlebotomy Chair 1')

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE walkin_queue 
    SET status = 'CALLED', called_at = CURRENT_TIMESTAMP
    WHERE id = ? AND center_id = ?
    """, (queue_id, user['center_id']))

    conn.commit()
    conn.close()

    flash(f"Called Token to {chair}", "success")
    return redirect(url_for('pathology.walkin_queue_view'))

@pathology_bp.route('/pathology/walkins/<queue_id>/complete', methods=['POST'])
@pathology_login_required
def walkin_complete_token(queue_id):
    """Marks a walk-in token as completed after successful phlebotomy draw."""
    user = get_current_pathology_user()

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("SELECT order_id FROM walkin_queue WHERE id = ? AND center_id = ?", (queue_id, user['center_id']))
    q = cursor.fetchone()
    if q:
        order_id = q['order_id']
        cursor.execute("UPDATE walkin_queue SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP WHERE id = ?", (queue_id,))
        cursor.execute("UPDATE diagnostic_orders SET status = 'SAMPLE_COLLECTED', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order_id,))
        cursor.execute("UPDATE sample_records SET status = 'COLLECTED', collected_by = ?, collected_at = CURRENT_TIMESTAMP WHERE order_id = ?", (user['full_name'], order_id))
        conn.commit()

    conn.close()
    flash("Walk-in sample collection completed.", "success")
    return redirect(url_for('pathology.walkin_queue_view'))

@pathology_bp.route('/pathology/orders/<order_id>/accession-specimen', methods=['POST'])
@pathology_login_required
def accession_specimen(order_id):
    """Specimen Accessioning desk with Vacutainer assignment & Specimen Quality Inspection."""
    user = get_current_pathology_user()
    vacutainer_type = request.form.get('vacutainer_type', 'Lavender Top (EDTA)')
    specimen_quality = request.form.get('specimen_quality', 'Satisfactory / Normal')
    barcode_input = request.form.get('barcode_data', '').strip()
    rejection_reason = request.form.get('rejection_reason', '')
    status = request.form.get('status', 'RECEIVED')

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM diagnostic_orders WHERE id = ? AND center_id = ?", (order_id, user['center_id']))
    if not cursor.fetchone():
        conn.close()
        flash("Order not found or unauthorized.", "error")
        return redirect(url_for('pathology.orders_list'))

    # Update sample record
    sample_code = barcode_input if barcode_input else f"LPL-SMP-{secrets.token_hex(4).upper()}"
    cursor.execute("""
    UPDATE sample_records
    SET container_type = ?,
        status = ?,
        rejection_reason = ?,
        received_by = ?,
        received_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE order_id = ?
    """, (vacutainer_type, status, rejection_reason if status == 'REJECTED' else None, user['full_name'], order_id))

    # Log tracking event
    cursor.execute("SELECT id FROM sample_records WHERE order_id = ?", (order_id,))
    s_row = cursor.fetchone()
    if s_row:
        event_id = f"TRK-{secrets.token_hex(6).upper()}"
        notes = f"Vacutainer: {vacutainer_type} | Quality: {specimen_quality}"
        if rejection_reason:
            notes += f" | Rejection: {rejection_reason}"
        cursor.execute("""
        INSERT INTO sample_tracking_events (id, sample_id, status, location, notes, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (event_id, s_row['id'], status, f"{user['center_name']} - Accessioning Bench", notes, user['full_name']))

    conn.commit()
    conn.close()

    flash(f"Specimen accessioned successfully. Tube: {vacutainer_type} | Integrity: {specimen_quality}", "success")
    return redirect(url_for('pathology.order_workspace', order_id=order_id))

@pathology_bp.route('/pathology/collections/<assignment_id>/log-temperature', methods=['POST'])
@pathology_login_required
def log_coldchain_temperature(assignment_id):
    """Logs phlebotomist ice-box cold chain temperature compliance (2°C - 8°C)."""
    user = get_current_pathology_user()
    try:
        temp_val = float(request.form.get('temperature_c', 4.0))
    except (ValueError, TypeError):
        temp_val = 4.0
    
    compliance = "COMPLIANT" if (2.0 <= temp_val <= 8.0) else "EXCURSION_ALERT"
    notes = request.form.get('temp_notes', f"Phlebotomy Box Temp: {temp_val}°C ({compliance})")

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE collection_assignments
    SET notes = CASE WHEN notes IS NULL OR notes = '' THEN ? ELSE notes || ' | ' || ? END
    WHERE id = ? AND center_id = ?
    """, (f"ColdChain: {temp_val}°C ({compliance})", f"ColdChain: {temp_val}°C ({compliance})", assignment_id, user['center_id']))

    conn.commit()
    conn.close()

    if compliance == "COMPLIANT":
        flash(f"Cold-chain temperature logged: {temp_val}°C — COMPLIANT (2°C to 8°C Standard)", "success")
    else:
        flash(f"Cold-chain temperature excursion logged: {temp_val}°C — ALERT: Outside 2°C-8°C range!", "warning")

    return redirect(url_for('pathology.phlebotomy_collections'))

# ==============================================================================
# 9. GLOBAL DASHBOARD SEARCH API
# ==============================================================================

@pathology_bp.route('/api/pathology/search')
@pathology_login_required
def api_pathology_search():
    """Global multi-entity search across orders, patients, test codes, and referrals."""
    user = get_current_pathology_user()
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({"success": True, "results": []})

    center_id = user['center_id']
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    results = []

    # 1. Search Diagnostic Orders & Patients
    cursor.execute("""
    SELECT o.id, o.order_number, o.patient_name, o.patient_phone, o.status, o.total_amount,
           (SELECT sample_code FROM sample_records WHERE order_id = o.id LIMIT 1) as sample_code
    FROM diagnostic_orders o
    WHERE o.center_id = ? AND (
        o.order_number LIKE ? OR o.patient_name LIKE ? OR o.patient_phone LIKE ?
    )
    LIMIT 6
    """, (center_id, f"%{q}%", f"%{q}%", f"%{q}%"))
    order_rows = cursor.fetchall()
    for row in order_rows:
        results.append({
            "title": f"Order #{row['order_number']} — {row['patient_name']}",
            "subtitle": f"Phone: {row['patient_phone']} &bull; Status: {row['status'].replace('_', ' ')}",
            "url": url_for('pathology.order_workspace', order_id=row['id']),
            "category": "Order",
            "icon": "fas fa-file-waveform",
            "badge_bg": "bg-indigo-100 text-indigo-700",
            "pill_class": "bg-indigo-50 text-indigo-700"
        })

    # 2. Search Samples by Barcode
    cursor.execute("""
    SELECT s.id, s.sample_code, s.sample_type, s.container_type, s.status, o.id as order_id, o.patient_name
    FROM sample_records s
    JOIN diagnostic_orders o ON s.order_id = o.id
    WHERE s.center_id = ? AND s.sample_code LIKE ?
    LIMIT 4
    """, (center_id, f"%{q}%"))
    sample_rows = cursor.fetchall()
    for row in sample_rows:
        results.append({
            "title": f"Barcode {row['sample_code']} — {row['patient_name']}",
            "subtitle": f"{row['sample_type']} &bull; {row['container_type']}",
            "url": url_for('pathology.order_workspace', order_id=row['order_id']),
            "category": "Sample Barcode",
            "icon": "fas fa-barcode",
            "badge_bg": "bg-amber-100 text-amber-800",
            "pill_class": "bg-amber-50 text-amber-800"
        })

    # 3. Search Diagnostic Test Catalog
    cursor.execute("""
    SELECT id, test_name, test_code, category_name, price
    FROM diagnostic_tests
    WHERE (center_id = ? OR center_id IS NULL) AND (test_name LIKE ? OR test_code LIKE ?)
    LIMIT 4
    """, (center_id, f"%{q}%", f"%{q}%"))
    test_rows = cursor.fetchall()
    for row in test_rows:
        results.append({
            "title": f"{row['test_name']} ({row['test_code']})",
            "subtitle": f"Category: {row['category_name']} &bull; ₹{row['price']:.0f}",
            "url": url_for('pathology.tests_management'),
            "category": "Test Catalog",
            "icon": "fas fa-flask",
            "badge_bg": "bg-teal-100 text-teal-800",
            "pill_class": "bg-teal-50 text-teal-800"
        })

    conn.close()
    return jsonify({"success": True, "results": results})
