"""
Spherix Insurance Blueprint - Financial Protection Division of Spherix Clinic
Patient & Public Life Insurance Marketplace, Plan Comparison, 6-Step Multi-Stage Application Wizard,
Underwriting Status Sync, Cryptographic Policy Issuance, Policy Documents, Premium Payments,
Claims Assistance, and Comprehensive Insurance Administration Console.
"""

import os
import json
import secrets
import hashlib
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, jsonify,
    session, current_app, send_file, abort
)
from flask_login import current_user, login_required

from spherix.routes.decorators import patient_required, admin_required
from spherix.services.insurance_db import (
    get_insurance_db, dict_from_row, dict_list_from_rows,
    calculate_life_insurance_quotation, save_insurance_quotation,
    create_or_update_insurance_application, submit_insurance_application,
    get_patient_insurance_applications, get_insurance_application_by_id,
    get_patient_insurance_policies, get_patient_policy_by_id,
    create_claim_assistance_request, get_patient_claims,
    get_patient_insurance_payments, log_insurance_audit,
    PRODUCT_ID_ALIASES
)
from spherix.services.insurance_integration import get_insurer_adapter

insurance_bp = Blueprint('insurance', __name__)

# ==============================================================================
# 1. PUBLIC & PATIENT MARKETPLACE / OVERVIEW
# ==============================================================================

@insurance_bp.route('/insurance', endpoint='insurance_public')
@insurance_bp.route('/services/insurance', endpoint='insurance_services')
@insurance_bp.route('/patient/insurance', endpoint='insurance_home')
@insurance_bp.route('/patient/insurance/hub', endpoint='insurance_hub')
def insurance_home():
    """Main Life Insurance Portal & Financial Protection Marketplace."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    # Fetch featured products
    cursor.execute("""
    SELECT p.*, ip.brand_name as partner_name, ip.legal_name as partner_legal_name,
           ip.irda_reg_no, ip.logo_url as partner_logo, ip.claim_settlement_ratio
    FROM insurance_products p
    JOIN insurance_partners ip ON p.partner_id = ip.id
    WHERE p.is_active = 1
    ORDER BY p.is_featured DESC, p.created_at ASC
    """)
    products = dict_list_from_rows(cursor.fetchall())
    for pr in products:
        pr['key_benefits'] = json.loads(pr.get('key_benefits') or '[]')
        pr['exclusions'] = json.loads(pr.get('exclusions') or '[]')

    # Fetch partners
    cursor.execute("SELECT * FROM insurance_partners WHERE is_active = 1 ORDER BY claim_settlement_ratio DESC")
    partners = dict_list_from_rows(cursor.fetchall())

    # Patient statistics if authenticated
    patient_stats = {'active_policies': 0, 'applications': 0, 'total_coverage': 0.0}
    recent_policies = []
    if current_user and current_user.is_authenticated and getattr(current_user, 'is_patient', False):
        pat_id = str(current_user.id)
        cursor.execute("SELECT COUNT(*) as c, COALESCE(SUM(sum_insured), 0) as s FROM patient_insurance_policies WHERE patient_id = ? AND status = 'ACTIVE'", (pat_id,))
        p_row = cursor.fetchone()
        if p_row:
            patient_stats['active_policies'] = p_row['c']
            patient_stats['total_coverage'] = float(p_row['s'])

        cursor.execute("SELECT COUNT(*) as c FROM insurance_applications WHERE patient_id = ? AND status NOT IN ('ACTIVE', 'REJECTED', 'CANCELLED')", (pat_id,))
        a_row = cursor.fetchone()
        if a_row:
            patient_stats['applications'] = a_row['c']

        cursor.execute("""
        SELECT pol.*, p.product_name, ip.brand_name as partner_name
        FROM patient_insurance_policies pol
        JOIN insurance_products p ON pol.product_id = p.id
        JOIN insurance_partners ip ON pol.partner_id = ip.id
        WHERE pol.patient_id = ?
        ORDER BY pol.policy_start_date DESC LIMIT 3
        """, (pat_id,))
        recent_policies = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'insurance/hub.html',
        products=products,
        partners=partners,
        patient_stats=patient_stats,
        recent_policies=recent_policies,
        selected_category=request.args.get('category', 'all')
    )

@insurance_bp.route('/patient/insurance/plans', endpoint='explore_plans')
@insurance_bp.route('/patient/insurance/plans/catalog', endpoint='plans_catalog')
def explore_plans():
    """Catalog of verified Life Insurance plans with category and insurer filters."""
    category = request.args.get('category', '').strip()
    partner_id = request.args.get('partner_id', '').strip()
    sort_by = request.args.get('sort', 'popular').strip()

    conn = get_insurance_db()
    cursor = conn.cursor()

    query = """
    SELECT p.*, ip.brand_name as partner_name, ip.legal_name as partner_legal_name,
           ip.irda_reg_no, ip.logo_url as partner_logo, ip.claim_settlement_ratio,
           ip.toll_free as partner_toll_free
    FROM insurance_products p
    JOIN insurance_partners ip ON p.partner_id = ip.id
    WHERE p.is_active = 1
    """
    params = []

    if category and category.lower() != 'all':
        query += " AND LOWER(p.category) = LOWER(?)"
        params.append(category)

    if partner_id:
        query += " AND p.partner_id = ?"
        params.append(partner_id)

    if sort_by == 'price_low':
        query += " ORDER BY p.base_annual_rate_per_lakh ASC"
    elif sort_by == 'ratio':
        query += " ORDER BY ip.claim_settlement_ratio DESC"
    else:
        query += " ORDER BY p.is_featured DESC, p.created_at ASC"

    cursor.execute(query, params)
    products = dict_list_from_rows(cursor.fetchall())
    for pr in products:
        pr['key_benefits'] = json.loads(pr.get('key_benefits') or '[]')
        pr['exclusions'] = json.loads(pr.get('exclusions') or '[]')
        pr['important_conditions'] = json.loads(pr.get('important_conditions') or '[]')

    cursor.execute("SELECT * FROM insurance_partners WHERE is_active = 1")
    partners = dict_list_from_rows(cursor.fetchall())
    conn.close()

    return render_template(
        'insurance/plans.html',
        products=products,
        partners=partners,
        selected_category=category,
        selected_partner=partner_id,
        selected_sort=sort_by
    )

@insurance_bp.route('/patient/insurance/compare', endpoint='compare')
@insurance_bp.route('/patient/insurance/compare', endpoint='compare_plans')
def compare_plans():
    """Interactive side-by-side plan comparison matrix."""
    plan_ids_param = request.args.get('plans', '').strip()
    selected_ids = [pid.strip() for pid in plan_ids_param.split(',') if pid.strip()]

    conn = get_insurance_db()
    cursor = conn.cursor()

    plans = []
    if not selected_ids:
        cursor.execute("SELECT id FROM insurance_products WHERE is_active = 1 ORDER BY is_featured DESC LIMIT 3")
        selected_ids = [r['id'] for r in cursor.fetchall()]

    if selected_ids:
        clean_ids = [str(sid).strip() for sid in selected_ids if sid and str(sid).strip().replace('-', '').replace('_', '').isalnum()]
        if clean_ids:
            placeholders = ','.join(['?'] * len(clean_ids))
            query = (
                "SELECT p.*, ip.brand_name as partner_name, ip.legal_name as partner_legal_name, "
                "ip.irda_reg_no, ip.logo_url as partner_logo, ip.claim_settlement_ratio, "
                "ip.solvency_ratio, ip.toll_free as partner_toll_free "
                "FROM insurance_products p "
                "JOIN insurance_partners ip ON p.partner_id = ip.id "
                f"WHERE p.id IN ({placeholders}) AND p.is_active = 1"
            )
            cursor.execute(query, clean_ids)
            plans = dict_list_from_rows(cursor.fetchall())

    for pl in plans:
        pl['key_benefits'] = json.loads(pl.get('key_benefits') or '[]')
        pl['exclusions'] = json.loads(pl.get('exclusions') or '[]')
        pl['important_conditions'] = json.loads(pl.get('important_conditions') or '[]')

    # All active plans for dropdown selector
    cursor.execute("SELECT id, product_name, category FROM insurance_products WHERE is_active = 1 ORDER BY product_name ASC")
    all_available_plans = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'insurance/compare.html',
        plans=plans,
        all_available_plans=all_available_plans,
        selected_ids=selected_ids
    )

# ==============================================================================
# 2. APPLICATION WORKFLOW (6 STEPS)
# ==============================================================================

@insurance_bp.route('/patient/insurance/apply', methods=['GET', 'POST'], endpoint='apply_insurance')
@insurance_bp.route('/patient/insurance/apply/wizard', methods=['GET', 'POST'], endpoint='apply_wizard')
@patient_required
def apply_insurance():
    """6-Step interactive Life Insurance proposal and application form."""
    product_id = request.args.get('product_id') or request.args.get('plan_id') or request.form.get('product_id') or 'PROD-SLIC-SHIELD'
    application_id = request.args.get('app_id') or request.form.get('application_id')

    resolved_prod_id = PRODUCT_ID_ALIASES.get(product_id, product_id)

    conn = get_insurance_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT p.*, ip.brand_name as partner_name, ip.legal_name as partner_legal_name,
           ip.irda_reg_no, ip.logo_url as partner_logo, ip.claim_settlement_ratio
    FROM insurance_products p
    JOIN insurance_partners ip ON p.partner_id = ip.id
    WHERE p.id = ?
    """, (resolved_prod_id,))
    product = dict_from_row(cursor.fetchone())
    conn.close()

    if not product:
        flash("Please select a valid insurance product.", "error")
        return redirect(url_for('insurance.explore_plans'))

    # Load existing draft if resuming
    existing_app = None
    if application_id:
        existing_app = get_insurance_application_by_id(application_id, patient_id=str(current_user.id))

    if request.method == 'POST':
        action = request.form.get('action', 'save_step')
        step = int(request.form.get('step', 1))

        # Personal Info (Step 1)
        personal_info = {
            "full_name": request.form.get('full_name') or current_user.name,
            "date_of_birth": request.form.get('date_of_birth', '1995-05-15'),
            "age": int(request.form.get('age', 30)),
            "gender": request.form.get('gender', 'Male'),
            "contact_phone": request.form.get('contact_phone') or getattr(current_user, 'phone', ''),
            "email": request.form.get('email') or getattr(current_user, 'email', ''),
            "residential_address": request.form.get('residential_address', 'Flat 402, Green Valley Apartments'),
            "city": request.form.get('city', 'New Delhi'),
            "state": request.form.get('state', 'Delhi'),
            "postal_code": request.form.get('postal_code', '110001'),
            "occupation": request.form.get('occupation', 'Salaried'),
            "annual_income": float(request.form.get('annual_income', 1000000.0)),
            "pan_number": request.form.get('pan_number', 'ABCDE1234F').upper(),
            "aadhaar_last4": request.form.get('aadhaar_last4', '8890')
        }

        # Insurance Details (Step 2)
        sum_insured = float(request.form.get('sum_insured', product['default_sum_insured']))
        term_years = int(request.form.get('term_years', 30))
        frequency = request.form.get('premium_frequency', 'ANNUAL')
        is_smoker = bool(request.form.get('is_smoker') in ['1', 'true', 'on', True])

        # Recalculate quotation
        ok_q, msg_q, quote = calculate_life_insurance_quotation(
            product_id=product['id'],
            age=personal_info['age'],
            gender=personal_info['gender'],
            is_smoker=is_smoker,
            sum_insured=sum_insured,
            term_years=term_years,
            frequency=frequency,
            annual_income=personal_info['annual_income']
        )
        if not ok_q:
            flash(msg_q, "error")
            return redirect(request.url)

        insurance_details = {
            "sum_insured": sum_insured,
            "policy_term_years": term_years,
            "premium_frequency": frequency,
            "is_smoker": 1 if is_smoker else 0,
            "base_premium": quote['base_premium'],
            "gst_amount": quote['gst_amount'],
            "total_premium": quote['total_premium']
        }

        # Nominee Information (Step 3)
        nominee_info = {
            "full_name": request.form.get('nominee_name', 'Sunita Kushwaha'),
            "relationship": request.form.get('nominee_relation', 'Spouse'),
            "date_of_birth": request.form.get('nominee_dob', '1996-08-20'),
            "contact_phone": request.form.get('nominee_phone', '+91 9811002233'),
            "contact_email": request.form.get('nominee_email', 'nominee@example.com'),
            "share_percentage": 100.0,
            "is_minor": 0
        }

        # Declarations (Step 4)
        declarations = {
            "has_critical_illness": bool(request.form.get('has_critical_illness') in ['1', 'true', 'on']),
            "has_past_surgery": bool(request.form.get('has_past_surgery') in ['1', 'true', 'on']),
            "has_pre_existing_conditions": bool(request.form.get('has_pre_existing_conditions') in ['1', 'true', 'on']),
            "tobacco_consumption": is_smoker,
            "alcohol_consumption": bool(request.form.get('alcohol_consumption') in ['1', 'true', 'on']),
            "consent_accepted": True,
            "privacy_accepted": True,
            "terms_accepted": True
        }

        # Handle Step 5 Document Uploads if provided
        uploaded_id_proof = request.files.get('id_proof')
        uploaded_addr_proof = request.files.get('address_proof')

        status = 'DRAFT'
        next_step = step + 1 if step < 6 else 6

        if action == 'submit_application' or step == 6:
            status = 'UNDER_REVIEW'

        ok_save, msg_save, saved_app = create_or_update_insurance_application(
            patient_id=str(current_user.id),
            product_id=product['id'],
            quotation_data=quote,
            personal_info=personal_info,
            insurance_details=insurance_details,
            nominee_info=nominee_info,
            declarations=declarations,
            current_step=next_step,
            status='DRAFT' if action != 'submit_application' else 'UNDER_REVIEW',
            application_id=application_id
        )

        app_id_res = saved_app['application_id']

        # Save uploaded documents if provided
        if uploaded_id_proof and uploaded_id_proof.filename:
            save_application_document(app_id_res, str(current_user.id), 'IDENTITY_PROOF', uploaded_id_proof)
        if uploaded_addr_proof and uploaded_addr_proof.filename:
            save_application_document(app_id_res, str(current_user.id), 'ADDRESS_PROOF', uploaded_addr_proof)

        if action == 'submit_application':
            # Submit to insurer adapter
            ok_sub, msg_sub, res_sub = submit_insurance_application(
                application_id=app_id_res,
                patient_id=str(current_user.id),
                ip_address=request.remote_addr or "127.0.0.1"
            )

            # Trigger automated insurer underwriting
            adapter = get_insurer_adapter(product['partner_id'])
            app_full = get_insurance_application_by_id(app_id_res, patient_id=str(current_user.id))
            adapter.submit_application(app_full)

            flash(f"Application {saved_app['application_number']} submitted successfully!", "success")
            return redirect(url_for('insurance.application_detail', app_id=app_id_res))

        flash("Application progress saved securely.", "success")
        return redirect(url_for('insurance.apply_insurance', product_id=product['id'], app_id=app_id_res, step=next_step))

    current_step = int(request.args.get('step', existing_app['current_step'] if existing_app else 1))

    return render_template(
        'insurance/apply.html',
        product=product,
        app=existing_app,
        current_step=current_step
    )

def save_application_document(application_id: str, patient_id: str, doc_type: str, file_obj) -> bool:
    """Validates and stores uploaded insurance identity and address documents."""
    try:
        filename = getattr(file_obj, 'filename', '') or 'document.pdf'
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'pdf'
        if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
            return False

        safe_name = f"INS_DOC_{doc_type}_{secrets.token_hex(4).upper()}.{ext}"
        target_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'insurance_docs')
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, safe_name)
        file_obj.save(file_path)

        conn = get_insurance_db()
        cursor = conn.cursor()
        doc_id = f"DOC-{secrets.token_hex(4).upper()}"
        cursor.execute("""
        INSERT INTO insurance_documents (
            id, application_id, patient_id, doc_type, file_name, file_path, original_name, mime_type, file_size
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id, application_id, str(patient_id), doc_type, safe_name,
            f"uploads/insurance_docs/{safe_name}", filename, f"application/{ext}",
            os.path.getsize(file_path) if os.path.exists(file_path) else 1024
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Document save error: {e}")
        return False

# ==============================================================================
# 3. PATIENT APPLICATIONS, POLICIES & STATUS
# ==============================================================================

@insurance_bp.route('/patient/insurance/applications')
@patient_required
def my_applications():
    """Lists all life insurance applications filed by the patient."""
    apps = get_patient_insurance_applications(str(current_user.id))
    return render_template('insurance/my_insurance.html', active_tab='applications', applications=apps)

@insurance_bp.route('/patient/insurance/applications/<app_id>', endpoint='application_detail')
@insurance_bp.route('/patient/insurance/applications/<app_id>/view', endpoint='view_application')
@patient_required
def application_detail(app_id):
    """View details of a specific application and underwriting status."""
    app = get_insurance_application_by_id(app_id, patient_id=str(current_user.id))
    if not app:
        flash("Unauthorized access or application not found.", "error")
        return redirect(url_for('insurance.my_applications'))

    conn = get_insurance_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM insurance_documents WHERE application_id = ?", (app_id,))
    documents = dict_list_from_rows(cursor.fetchall())
    conn.close()

    return render_template(
        'insurance/application_detail.html',
        app=app,
        documents=documents
    )

@insurance_bp.route('/patient/insurance/policies', endpoint='my_policies')
@patient_required
def my_policies():
    """Lists all active and historical life insurance policies."""
    policies = get_patient_insurance_policies(str(current_user.id))
    return render_template('insurance/my_insurance.html', active_tab='policies', policies=policies)

@insurance_bp.route('/patient/insurance/policies/<policy_id>', endpoint='policy_detail')
@insurance_bp.route('/patient/insurance/policies/<policy_id>/view', endpoint='view_policy')
@patient_required
def policy_detail(policy_id):
    """Detailed view of an issued life insurance policy with payment ledger and schedule."""
    policy = get_patient_policy_by_id(policy_id, patient_id=str(current_user.id))
    if not policy:
        flash("Unauthorized access or policy not found.", "error")
        return redirect(url_for('insurance.my_policies'))

    conn = get_insurance_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM insurance_payments WHERE policy_id = ? ORDER BY paid_at DESC", (policy['id'],))
    payments = dict_list_from_rows(cursor.fetchall())

    cursor.execute("SELECT * FROM insurance_claim_assistances WHERE policy_id = ? ORDER BY created_at DESC", (policy['id'],))
    claims = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'insurance/policy_detail.html',
        policy=policy,
        payments=payments,
        claims=claims
    )

@insurance_bp.route('/patient/insurance/policies/<policy_id>/document', endpoint='download_policy_document')
@insurance_bp.route('/patient/insurance/policies/<policy_id>/certificate', endpoint='view_policy_document')
@patient_required
def download_policy_document(policy_id):
    """Renders the official Certificate of Life Insurance Schedule with cryptographic verification."""
    policy = get_patient_policy_by_id(policy_id, patient_id=str(current_user.id))
    if not policy:
        flash("Unauthorized access or policy document not found.", "error")
        return redirect(url_for('insurance.my_policies'))

    return render_template(
        'insurance/policy_document.html',
        policy=policy,
        patient=current_user,
        now=datetime.now()
    )

# ==============================================================================
# 4. PAYMENTS & GATEWAY INTEGRATION
# ==============================================================================

@insurance_bp.route('/patient/insurance/payments')
@patient_required
def my_payments():
    """Ledger of all insurance premium payments and tax receipts."""
    payments = get_patient_insurance_payments(str(current_user.id))
    return render_template('insurance/my_insurance.html', active_tab='payments', payments=payments)

@insurance_bp.route('/patient/insurance/payments/pay/<app_id>', methods=['GET', 'POST'])
@patient_required
def pay_premium(app_id):
    """Checkout gateway interface for paying authorized insurance proposal premium."""
    app = get_insurance_application_by_id(app_id, patient_id=str(current_user.id))
    if not app:
        flash("Application not found.", "error")
        return redirect(url_for('insurance.my_applications'))

    if app['status'] not in ['APPROVED', 'PAYMENT_PENDING']:
        flash(f"Application cannot accept payment because status is '{app['status']}'. Underwriting approval required first.", "warning")
        return redirect(url_for('insurance.application_detail', app_id=app_id))

    ins_details = app.get('insurance_details', {})
    amount = float(ins_details.get('total_premium') or ins_details.get('base_premium', 9500.0))

    if request.method == 'POST':
        payment_method = request.form.get('payment_method', 'UPI')
        tx_ref = f"TXN-SPX-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

        payment_data = {
            "transaction_ref": tx_ref,
            "amount": amount,
            "total_amount": amount,
            "payment_method": payment_method
        }

        # Partner Insurer verifies and issues the policy
        adapter = get_insurer_adapter(app['partner_id'])
        ok_issue, msg_issue, pol_res = adapter.verify_payment_and_issue_policy(payment_data, app)

        if ok_issue:
            flash(f"Payment verified! Policy #{pol_res['policy_number']} has been successfully issued by {app['partner_name']}.", "success")
            return redirect(url_for('insurance.policy_detail', policy_id=pol_res['policy_id']))
        else:
            flash(f"Payment verification failed: {msg_issue}", "error")

    return render_template(
        'insurance/payment_checkout.html',
        app=app,
        amount=amount
    )

# ==============================================================================
# 5. CLAIMS ASSISTANCE, DOCUMENTS & SUPPORT
# ==============================================================================

@insurance_bp.route('/patient/insurance/claims')
@patient_required
def my_claims():
    """Claims assistance dashboard and status tracking."""
    claims = get_patient_claims(str(current_user.id))
    policies = get_patient_insurance_policies(str(current_user.id))
    return render_template('insurance/my_insurance.html', active_tab='claims', claims=claims, policies=policies)

@insurance_bp.route('/patient/insurance/claims/request', methods=['GET', 'POST'])
@patient_required
def request_claim():
    """Initiates a formal claim assistance ticket for a registered policy."""
    policies = get_patient_insurance_policies(str(current_user.id))
    if not policies:
        flash("You do not have any active policies to initiate a claim against.", "warning")
        return redirect(url_for('insurance.my_policies'))

    if request.method == 'POST':
        policy_id = request.form.get('policy_id')
        claimant_data = {
            "claimant_name": request.form.get('claimant_name', current_user.name),
            "claimant_relation": request.form.get('claimant_relation', 'Self'),
            "claimant_phone": request.form.get('claimant_phone', getattr(current_user, 'phone', '')),
            "claimant_email": request.form.get('claimant_email', getattr(current_user, 'email', '')),
            "claim_type": request.form.get('claim_type', 'CRITICAL_ILLNESS'),
            "incident_date": request.form.get('incident_date', str(date.today())),
            "hospital_name": request.form.get('hospital_name', 'Spherix Clinic & Hospital'),
            "diagnosis_summary": request.form.get('diagnosis_summary', 'Clinical claim assistance request submitted through patient portal.')
        }

        ok, msg, res = create_claim_assistance_request(policy_id, str(current_user.id), claimant_data)
        if ok:
            flash(msg, "success")
            return redirect(url_for('insurance.my_claims'))
        else:
            flash(msg, "error")

    return render_template(
        'insurance/claim_request.html',
        policies=policies,
        selected_policy_id=request.args.get('policy_id')
    )

@insurance_bp.route('/patient/insurance/documents')
@patient_required
def my_documents():
    """Documents repository for identity proof, policy schedules, and receipts."""
    conn = get_insurance_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT d.*, app.application_number
    FROM insurance_documents d
    LEFT JOIN insurance_applications app ON d.application_id = app.id
    WHERE d.patient_id = ?
    ORDER BY d.created_at DESC
    """, (str(current_user.id),))
    docs = dict_list_from_rows(cursor.fetchall())
    conn.close()

    return render_template('insurance/my_insurance.html', active_tab='documents', documents=docs)

@insurance_bp.route('/patient/insurance/support', methods=['GET', 'POST'])
def insurance_support():
    """Dedicated Insurance Grievance Redressal and IRDAI Ombudsman Support Hub."""
    conn = get_insurance_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM insurance_partners WHERE is_active = 1")
    partners = dict_list_from_rows(cursor.fetchall())

    if request.method == 'POST' and current_user and current_user.is_authenticated:
        subject = request.form.get('subject', 'Policy Enquiry')
        category = request.form.get('category', 'Policy Servicing')
        description = request.form.get('description', '')

        ticket_no = f"GRV-{datetime.now().strftime('%Y%m')}-{secrets.token_hex(3).upper()}"
        cursor.execute("""
        INSERT INTO insurance_complaints (
            id, ticket_number, patient_id, subject, category, description, status
        ) VALUES (?, ?, ?, ?, ?, ?, 'OPEN')
        """, (
            f"CMP-{secrets.token_hex(4).upper()}", ticket_no, str(current_user.id),
            subject, category, description
        ))
        conn.commit()
        flash(f"Support ticket {ticket_no} generated! Our compliance coordinator will respond within 24 hours.", "success")
        conn.close()
        return redirect(url_for('insurance.insurance_support'))

    conn.close()
    return render_template('insurance/support.html', partners=partners)

# ==============================================================================
# 6. JSON APIS FOR AJAX CALCULATIONS & UNDERWRITING SYNC
# ==============================================================================

@insurance_bp.route('/api/insurance/quote', methods=['GET', 'POST'])
def api_insurance_quote():
    """Real-time premium calculation API endpoint."""
    data = request.get_json(silent=True) or request.form or request.args or {}
    product_id = data.get('product_id', 'PROD-SLIC-SHIELD')
    age = int(data.get('age', 30))
    gender = data.get('gender', 'Male')
    is_smoker = bool(data.get('is_smoker') in [1, '1', True, 'true', 'yes'])
    sum_insured = float(data.get('sum_insured', 10000000.0))
    term_years = int(data.get('policy_term_years') or data.get('term_years', 30))
    frequency = (data.get('premium_frequency') or data.get('frequency', 'ANNUAL')).upper()

    ok, msg, quote = calculate_life_insurance_quotation(
        product_id=product_id,
        age=age,
        gender=gender,
        is_smoker=is_smoker,
        sum_insured=sum_insured,
        term_years=term_years,
        frequency=frequency
    )

    if ok:
        return jsonify({"success": True, "quote": quote})
    return jsonify({"success": False, "error": msg}), 400

@insurance_bp.route('/api/insurance/application/<app_id>/sync')
@patient_required
def api_sync_underwriting_status(app_id):
    """Syncs the underwriting decision from the partner insurer."""
    app = get_insurance_application_by_id(app_id, patient_id=str(current_user.id))
    if not app:
        return jsonify({"success": False, "error": "Application not found"}), 404

    adapter = get_insurer_adapter(app['partner_id'])
    ok, msg, res = adapter.check_underwriting_status(app_id)
    return jsonify({"success": ok, "status": res.get('status'), "remarks": res.get('remarks')})

# ==============================================================================
# 7. INSURANCE ADMIN CONSOLE
# ==============================================================================

@insurance_bp.route('/admin/insurance')
@admin_required
def admin_insurance_overview():
    """Executive Insurance Dashboard for Administrators."""
    conn = get_insurance_db()
    cursor = conn.cursor()

    # Metrics
    cursor.execute("SELECT COUNT(*) as c, COALESCE(SUM(sum_insured), 0) as s, COALESCE(SUM(premium_amount), 0) as p FROM patient_insurance_policies WHERE status = 'ACTIVE'")
    pol_kpi = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as c FROM insurance_applications WHERE status IN ('SUBMITTED', 'UNDER_REVIEW', 'ADDITIONAL_INFO_REQUIRED')")
    pending_apps = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) as c FROM insurance_claim_assistances WHERE status NOT IN ('SETTLED', 'REJECTED')")
    active_claims = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) as c FROM insurance_partners WHERE is_active = 1")
    partners_count = cursor.fetchone()['c']

    # Recent applications
    cursor.execute("""
    SELECT a.*, p.product_name, ip.brand_name as partner_name
    FROM insurance_applications a
    JOIN insurance_products p ON a.product_id = p.id
    JOIN insurance_partners ip ON a.partner_id = ip.id
    ORDER BY a.created_at DESC LIMIT 10
    """)
    recent_apps = dict_list_from_rows(cursor.fetchall())

    # Recent policies
    cursor.execute("""
    SELECT pol.*, p.product_name, ip.brand_name as partner_name
    FROM patient_insurance_policies pol
    JOIN insurance_products p ON pol.product_id = p.id
    JOIN insurance_partners ip ON pol.partner_id = ip.id
    ORDER BY pol.policy_start_date DESC LIMIT 10
    """)
    recent_pols = dict_list_from_rows(cursor.fetchall())

    # Partners
    cursor.execute("SELECT * FROM insurance_partners ORDER BY claim_settlement_ratio DESC")
    partners = dict_list_from_rows(cursor.fetchall())

    # Products
    cursor.execute("""
    SELECT p.*, ip.brand_name as partner_name
    FROM insurance_products p
    JOIN insurance_partners ip ON p.partner_id = ip.id
    ORDER BY p.is_featured DESC
    """)
    products = dict_list_from_rows(cursor.fetchall())

    # Audit Logs
    cursor.execute("SELECT * FROM insurance_audit_logs ORDER BY created_at DESC LIMIT 15")
    audit_logs = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'insurance/admin_insurance.html',
        kpi_active_policies=pol_kpi['c'],
        kpi_total_coverage=float(pol_kpi['s']),
        kpi_gross_premium=float(pol_kpi['p']),
        kpi_pending_apps=pending_apps,
        kpi_active_claims=active_claims,
        kpi_partners_count=partners_count,
        recent_apps=recent_apps,
        recent_pols=recent_pols,
        partners=partners,
        products=products,
        audit_logs=audit_logs,
        active_tab=request.args.get('tab', 'overview')
    )

# ==============================================================================
# 8. BLUEPRINT URL ALIASES (SEAMLESS ROUTING ACROSS TEMPLATES)
# ==============================================================================
insurance_bp.add_url_rule('/patient/insurance/hub', endpoint='insurance_hub', view_func=insurance_home)
insurance_bp.add_url_rule('/patient/insurance/plans/catalog', endpoint='plans_catalog', view_func=explore_plans)
insurance_bp.add_url_rule('/patient/insurance/apply/wizard', endpoint='apply_wizard', view_func=apply_insurance, methods=['GET', 'POST'])
insurance_bp.add_url_rule('/patient/insurance/applications/<app_id>/view', endpoint='view_application', view_func=application_detail)
insurance_bp.add_url_rule('/patient/insurance/policies/<policy_id>/view', endpoint='view_policy', view_func=policy_detail)
insurance_bp.add_url_rule('/patient/insurance/policies/<policy_id>/certificate', endpoint='view_policy_document', view_func=download_policy_document)
insurance_bp.add_url_rule('/patient/insurance/payments/portal', endpoint='payments_portal', view_func=my_payments)
insurance_bp.add_url_rule('/patient/insurance/payments/checkout/<app_id>', endpoint='payment_checkout', view_func=pay_premium, methods=['GET', 'POST'])
insurance_bp.add_url_rule('/patient/insurance/claims/portal', endpoint='claims_portal', view_func=my_claims)
insurance_bp.add_url_rule('/patient/insurance/documents/portal', endpoint='documents_portal', view_func=my_documents)
insurance_bp.add_url_rule('/patient/insurance/support/portal', endpoint='support_portal', view_func=insurance_support, methods=['GET', 'POST'])
insurance_bp.add_url_rule('/admin/insurance/console', endpoint='admin_portal', view_func=admin_insurance_overview)
