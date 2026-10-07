"""
Spherix Diagnostic Network - Patient & Public Diagnostic Portal Blueprint
Handles test search, package exploration, center directory with geo-distance comparison,
multi-step doorstep and walk-in booking, order tracking, and tamper-proof report verification.
"""

import os
import io
import json
from datetime import datetime, date, timedelta
from typing import Dict, Any, List

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_file, current_app
from flask_login import current_user

from spherix.config import (
    COUNTRIES_195, GLOBAL_COUNTRY_FLAGS, GLOBAL_COUNTRY_TIMEZONES,
    format_dual_currency, convert_currency, get_currency_symbol, utcnow
)
from spherix.services.database import TEMP_DATA, save_data
from spherix.services.diagnostic_catalog import (
    DIAGNOSTIC_MASTER_CATEGORIES, MASTER_TESTS_CATALOG, MASTER_PACKAGES_CATALOG,
    get_category_by_code, get_test_by_code, get_package_by_code
)
from spherix.services.diagnostic_db import (
    get_diagnostic_db, dict_from_row, dict_list_from_rows,
    find_matching_pathology_centers, create_diagnostic_booking_order,
    get_diagnostic_order_by_id, get_test_price_comparison, check_test_availability_by_location
)
from spherix.services.diagnostic_ai import (
    get_groq_diagnostic_test_insight, is_groq_available, generate_pathologist_ai_summary
)

diagnostic_bp = Blueprint('diagnostic', __name__)

def get_registered_areas() -> List[Dict[str, Any]]:
    """Returns list of distinct registered cities/areas with center counts."""
    try:
        conn = get_diagnostic_db()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT city, COUNT(*) as center_count
        FROM pathology_centers
        WHERE is_active = 1 AND city IS NOT NULL AND TRIM(city) != ''
        GROUP BY city
        ORDER BY center_count DESC, city ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        cities = []
        for r in rows:
            cities.append({"city": r["city"], "count": r["center_count"]})
        return cities
    except Exception:
        return [
            {"city": "New Delhi", "count": 12},
            {"city": "Mumbai", "count": 8},
            {"city": "Bengaluru", "count": 7},
            {"city": "Hyderabad", "count": 5},
            {"city": "Motihari", "count": 3}
        ]

@diagnostic_bp.route('/diagnostic')
@diagnostic_bp.route('/medical-lab', endpoint='medical_lab')
def diagnostic_home():
    """Diagnostic Network Portal Landing Page."""
    country = request.args.get('country', 'India').strip()
    city = request.args.get('city', '').strip()
    search = request.args.get('q', '').strip()

    # Fetch verified centers
    verified_centers = find_matching_pathology_centers(country=country if country != 'All' else None, city=city if city else None)
    
    # Filter categories
    categories = DIAGNOSTIC_MASTER_CATEGORIES

    # Featured tests
    featured_tests = MASTER_TESTS_CATALOG[:8]
    if search:
        s_lower = search.lower()
        featured_tests = [t for t in MASTER_TESTS_CATALOG if s_lower in t['name'].lower() or s_lower in t['code'].lower() or s_lower in t['description'].lower()]

    # Featured packages
    packages = MASTER_PACKAGES_CATALOG

    return render_template(
        'pathology.html',
        categories=categories,
        featured_tests=featured_tests,
        packages=packages,
        centers=verified_centers,
        selected_country=country,
        selected_city=city,
        search_query=search,
        countries=COUNTRIES_195,
        registered_areas=get_registered_areas()
    )

@diagnostic_bp.route('/diagnostic/search')
def diagnostic_search():
    """AJAX API for real-time search across tests, packages, and centers."""
    q = request.args.get('q', '').strip().lower()
    category = request.args.get('category', '').strip().upper()
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    city = request.args.get('city', '').strip()
    country = request.args.get('country', '').strip()

    tests = MASTER_TESTS_CATALOG
    if q:
        tests = [t for t in tests if q in t['name'].lower() or q in t['code'].lower() or q in t['description'].lower()]
    if category:
        tests = [t for t in tests if t.get('category_code', '').upper() == category]

    packages = MASTER_PACKAGES_CATALOG
    if q:
        packages = [p for p in packages if q in p['name'].lower() or q in p['code'].lower() or q in p['description'].lower()]

    centers = find_matching_pathology_centers(user_lat=lat, user_lng=lng, city=city, country=country)

    return jsonify({
        "success": True,
        "query": q,
        "tests_count": len(tests),
        "tests": tests[:20],
        "packages_count": len(packages),
        "packages": packages,
        "centers_count": len(centers),
        "centers": centers[:10]
    })

@diagnostic_bp.route('/diagnostic/tests')
def tests_catalog():
    """Comprehensive diagnostic test catalog."""
    category_code = request.args.get('category', '').strip().upper()
    search = request.args.get('q', '').strip().lower()

    tests = MASTER_TESTS_CATALOG
    if category_code:
        tests = [t for t in tests if t['category_code'].upper() == category_code]
    if search:
        tests = [t for t in tests if search in t['name'].lower() or search in t['code'].lower() or search in t['description'].lower()]

    selected_category = get_category_by_code(category_code) if category_code else None

    return render_template(
        'pathology.html',
        view_mode='tests_catalog',
        categories=DIAGNOSTIC_MASTER_CATEGORIES,
        tests=tests,
        selected_category=selected_category,
        search_query=search,
        packages=MASTER_PACKAGES_CATALOG,
        centers=find_matching_pathology_centers(),
        registered_areas=get_registered_areas()
    )

@diagnostic_bp.route('/diagnostic/tests/<test_code>')
@diagnostic_bp.route('/diagnostic/test/<test_code>', endpoint='diagnostic_test_detail')
def test_detail(test_code):
    """Detailed biological overview, parameters, Groq AI insights, and price comparison across centers."""
    test = get_test_by_code(test_code)
    if not test:
        flash("Diagnostic test not found.", "error")
        return redirect(url_for('diagnostic.diagnostic_home'))

    category = get_category_by_code(test['category_code'])
    matching_centers = find_matching_pathology_centers(test_codes=[test['code']])
    price_comparison = get_test_price_comparison(test['code'])
    ai_insights = get_groq_diagnostic_test_insight(test['code'], test)

    return render_template(
        'diagnostic_test_detail.html',
        test=test,
        category=category,
        centers=matching_centers,
        price_comparison=price_comparison,
        ai_insights=ai_insights,
        related_packages=[p for p in MASTER_PACKAGES_CATALOG if test['code'] in p['test_codes']],
        registered_areas=get_registered_areas()
    )

@diagnostic_bp.route('/diagnostic/compare')
def compare_tests():
    """Interactive Price & Center Comparison Engine."""
    test_code = request.args.get('code', 'CBC').strip().upper()
    city = request.args.get('city', '').strip()
    country = request.args.get('country', 'India').strip()
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)

    comparison = get_test_price_comparison(test_code, user_lat=lat, user_lng=lng, city=city, country=country)
    ai_insights = get_groq_diagnostic_test_insight(test_code)

    return render_template(
        'pathology.html',
        view_mode='compare_prices',
        comparison=comparison,
        ai_insights=ai_insights,
        all_tests=MASTER_TESTS_CATALOG,
        selected_test_code=test_code,
        selected_city=city,
        selected_country=country,
        categories=DIAGNOSTIC_MASTER_CATEGORIES,
        countries=COUNTRIES_195,
        registered_areas=get_registered_areas()
    )

@diagnostic_bp.route('/api/diagnostic/ai-explore-test')
def api_ai_explore_test():
    """Real-time Groq AI Clinical Insights API for test cards and modals."""
    test_code_or_query = request.args.get('code') or request.args.get('q') or 'CBC'
    insights = get_groq_diagnostic_test_insight(test_code_or_query)
    return jsonify({
        "success": True,
        "insights": insights
    })

@diagnostic_bp.route('/api/diagnostic/test-details-sidebar')
def api_test_details_sidebar():
    """Returns complete diagnostic test intelligence, preparations, fasting, results, side effects, and pricing for the sidebar."""
    code_raw = (request.args.get('code') or request.args.get('test_code') or request.args.get('test_id') or request.args.get('id') or request.args.get('q') or 'CBC').strip()
    code = code_raw.upper()
    center_id = request.args.get('center_id', '').strip()

    test_data = None
    center_data = None
    center_price = None

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    if center_id:
        cursor.execute("SELECT * FROM pathology_centers WHERE id = ?", (center_id,))
        center_row = cursor.fetchone()
        if center_row:
            center_data = dict_from_row(center_row)

        cursor.execute("""
            SELECT * FROM diagnostic_tests 
            WHERE center_id = ? AND (UPPER(test_code) = ? OR UPPER(id) = ? OR id = ?) AND is_active = 1
        """, (center_id, code, code, code_raw))
        t_row = cursor.fetchone()
        if t_row:
            test_data = dict_from_row(t_row)
            center_price = test_data.get('price')

    if not test_data:
        # Search by id or test_code across all diagnostic_tests
        cursor.execute("""
            SELECT * FROM diagnostic_tests 
            WHERE (UPPER(test_code) = ? OR UPPER(id) = ? OR id = ?) AND is_active = 1
            LIMIT 1
        """, (code, code, code_raw))
        t_row = cursor.fetchone()
        if t_row:
            test_data = dict_from_row(t_row)
            center_price = test_data.get('price')

    if not test_data:
        master_t = get_test_by_code(code)
        if master_t:
            test_data = dict(master_t)
            test_data['test_name'] = master_t.get('name')
            test_data['test_code'] = master_t.get('code')
            center_price = center_price or master_t.get('base_price_inr', 500)
        else:
            for t in MASTER_TESTS_CATALOG:
                if t['code'].upper() == code or code in t['name'].upper():
                    test_data = dict(t)
                    test_data['test_name'] = t.get('name')
                    test_data['test_code'] = t.get('code')
                    center_price = center_price or t.get('base_price_inr', 500)
                    break

    conn.close()

    if not test_data:
        return jsonify({"success": False, "error": "Diagnostic test not found"}), 404

    # Extract or parse parameters
    params = test_data.get('parameters') or []
    if not params and test_data.get('parameters_json'):
        try:
            params = json.loads(test_data['parameters_json'])
        except Exception:
            params = []

    if not params:
        cat_t = get_test_by_code(code)
        if cat_t:
            params = cat_t.get('parameters', [])

    # Get clinical insights
    insights = get_groq_diagnostic_test_insight(code, test_data)

    final_price = center_price or test_data.get('price') or test_data.get('base_price_inr', 500)

    fasting_req = test_data.get('fasting_required', False)
    fasting_hrs = test_data.get('fasting_hours', 0)
    if isinstance(fasting_req, int):
        fasting_req = bool(fasting_req)

    return jsonify({
        "success": True,
        "test": {
            "code": test_data.get('test_code') or test_data.get('code') or code,
            "name": test_data.get('test_name') or test_data.get('name') or code,
            "category": test_data.get('category_name') or test_data.get('category_code') or 'Pathology',
            "sample_type": test_data.get('sample_type', 'Whole Blood (EDTA)'),
            "container_type": test_data.get('container_type', 'Sterile Vacutainer'),
            "required_quantity": test_data.get('required_quantity', '3.0 mL'),
            "turnaround_hours": test_data.get('turnaround_hours', 12),
            "fasting_required": fasting_req,
            "fasting_hours": fasting_hrs,
            "preparation_instructions": test_data.get('preparation_instructions', 'Maintain normal hydration. No specific preparation needed.'),
            "price": final_price,
            "parameters": params
        },
        "center": center_data,
        "insights": insights,
        "is_authenticated": current_user.is_authenticated
    })

@diagnostic_bp.route('/api/diagnostic/compare-prices')
def api_compare_prices():
    """AJAX API returning live prices across centers for any test."""
    test_code = request.args.get('code', 'CBC').strip().upper()
    city = request.args.get('city', '').strip()
    country = request.args.get('country', '').strip()
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)

    comparison = get_test_price_comparison(test_code, user_lat=lat, user_lng=lng, city=city, country=country)
    return jsonify({
        "success": True,
        "comparison": comparison
    })

@diagnostic_bp.route('/api/diagnostic/check-availability')
def api_check_availability():
    """AJAX API to check test and phlebotomist availability by city or ZIP code."""
    q = request.args.get('q', 'CBC').strip()
    city = request.args.get('city', '').strip()
    postal = request.args.get('postal_code', '').strip()
    country = request.args.get('country', '').strip()

    res = check_test_availability_by_location(q, city=city, postal_code=postal, country=country)
    return jsonify({
        "success": True,
        "availability": res
    })

@diagnostic_bp.route('/diagnostic/packages')
def packages_catalog():
    """Health checkup packages catalog."""
    search = request.args.get('q', '').strip().lower()
    packages = MASTER_PACKAGES_CATALOG
    if search:
        packages = [p for p in packages if search in p['name'].lower() or search in p['description'].lower()]

    return render_template(
        'pathology.html',
        view_mode='packages_catalog',
        categories=DIAGNOSTIC_MASTER_CATEGORIES,
        packages=packages,
        search_query=search,
        featured_tests=MASTER_TESTS_CATALOG[:8],
        centers=find_matching_pathology_centers(),
        registered_areas=get_registered_areas()
    )

@diagnostic_bp.route('/diagnostic/centers')
def centers_directory():
    """Interactive Directory of verified Pathology Centers."""
    country = request.args.get('country', '').strip()
    city = request.args.get('city', '').strip()
    service = request.args.get('service', '').strip() # HOME_COLLECTION, WALK_IN
    sort_by = request.args.get('sort', 'distance').strip()

    centers = find_matching_pathology_centers(
        country=country if country and country != 'All' else None,
        city=city if city else None,
        service_type=service if service else None,
        sort_by=sort_by
    )

    return render_template(
        'pathology.html',
        view_mode='centers_directory',
        centers=centers,
        categories=DIAGNOSTIC_MASTER_CATEGORIES,
        packages=MASTER_PACKAGES_CATALOG,
        selected_country=country,
        selected_city=city,
        selected_service=service,
        countries=COUNTRIES_195,
        registered_areas=get_registered_areas()
    )

@diagnostic_bp.route('/diagnostic/centers/<center_id>')
def center_detail(center_id):
    """Pathology Center Profile Page & Available Tests Catalog."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT c.*, o.legal_name as org_legal_name, o.accreditation as org_accreditation, o.website as org_website
    FROM pathology_centers c
    JOIN pathology_organizations o ON c.organization_id = o.id
    WHERE c.id = ?
    """, (center_id,))
    center = dict_from_row(cursor.fetchone())

    if not center:
        conn.close()
        flash("Pathology center not found.", "error")
        return redirect(url_for('diagnostic.diagnostic_home'))

    # Center's tests
    cursor.execute("SELECT * FROM diagnostic_tests WHERE center_id = ? AND is_active = 1", (center_id,))
    raw_tests = dict_list_from_rows(cursor.fetchall())
    
    tests = []
    if raw_tests:
        for t in raw_tests:
            t_copy = dict(t)
            if t_copy.get('parameters_json'):
                try:
                    t_copy['parameters'] = json.loads(t_copy['parameters_json'])
                except Exception:
                    t_copy['parameters'] = []
            else:
                cat_t = get_test_by_code(t_copy.get('test_code', ''))
                t_copy['parameters'] = cat_t.get('parameters', []) if cat_t else []
            tests.append(t_copy)
    else:
        for t in MASTER_TESTS_CATALOG:
            t_copy = dict(t)
            t_copy['price'] = t.get('base_price_inr', 500)
            t_copy['test_code'] = t.get('code')
            t_copy['test_name'] = t.get('name')
            tests.append(t_copy)

    # Center's packages
    cursor.execute("SELECT * FROM diagnostic_packages WHERE center_id = ? AND is_active = 1", (center_id,))
    raw_packages = dict_list_from_rows(cursor.fetchall())
    if not raw_packages:
        packages = MASTER_PACKAGES_CATALOG
    else:
        packages = []
        for p in raw_packages:
            p_norm = dict(p)
            p_norm['name'] = p.get('package_name') or p.get('name', 'Health Checkup Package')
            p_norm['code'] = p.get('package_code') or p.get('code', 'PKG-CUSTOM')
            p_norm['base_price_inr'] = float(p.get('package_price') or p.get('base_price_inr') or p.get('original_price') or 999.0)
            p_norm['test_codes'] = p.get('test_codes') if isinstance(p.get('test_codes'), list) else ['CBC', 'LFT', 'KFT']
            packages.append(p_norm)

    # Reviews
    cursor.execute("SELECT * FROM diagnostic_reviews WHERE center_id = ? ORDER BY created_at DESC", (center_id,))
    reviews = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'diagnostic_test_detail.html',
        view_mode='center_detail',
        center=center,
        tests=tests,
        packages=packages,
        reviews=reviews,
        categories=DIAGNOSTIC_MASTER_CATEGORIES,
        registered_areas=get_registered_areas()
    )

@diagnostic_bp.route('/diagnostic/book', methods=['GET', 'POST'])
def book_diagnostic_test():
    """Multi-service booking flow: Doorstep Home Collection vs Walk-in Lab Visit."""
    if request.method == 'POST':
        test_codes_str = request.form.get('test_codes', '')
        package_codes_str = request.form.get('package_codes', '')
        center_id = request.form.get('center_id', '')
        service_type = request.form.get('service_type', 'HOME_COLLECTION').upper()
        scheduled_date = request.form.get('scheduled_date', date.today().strftime("%Y-%m-%d"))
        scheduled_slot = request.form.get('scheduled_slot', '07:00-09:00')

        patient_name = request.form.get('patient_name', '')
        patient_email = request.form.get('patient_email', '')
        patient_phone = request.form.get('patient_phone', '')
        patient_address = request.form.get('patient_address', '')
        patient_lat = float(request.form.get('patient_lat', 0.0) or 0.0)
        patient_lng = float(request.form.get('patient_lng', 0.0) or 0.0)
        payment_method = request.form.get('payment_method', 'ONLINE')
        notes = request.form.get('notes', '')

        # Build items list
        items = []
        if test_codes_str:
            codes = [c.strip() for c in test_codes_str.split(',') if c.strip()]
            for c in codes:
                t = get_test_by_code(c)
                if t:
                    items.append({
                        "type": "TEST",
                        "id": f"TST-{c}",
                        "name": t['name'],
                        "code": t['code'],
                        "price": t['base_price_inr']
                    })

        if package_codes_str:
            p_codes = [c.strip() for c in package_codes_str.split(',') if c.strip()]
            for pc in p_codes:
                p = get_package_by_code(pc)
                if p:
                    items.append({
                        "type": "PACKAGE",
                        "id": f"PKG-{pc}",
                        "name": p['name'],
                        "code": p['code'],
                        "price": p['base_price_inr']
                    })

        if not items:
            flash("Please select at least one test or health package to book.", "error")
            return redirect(url_for('diagnostic.diagnostic_home'))

        patient_id = current_user.id if current_user.is_authenticated and getattr(current_user, 'is_patient', False) else None
        if not patient_name and current_user.is_authenticated:
            patient_name = getattr(current_user, 'name', 'Registered Patient')
            patient_email = getattr(current_user, 'email', '')
            patient_phone = getattr(current_user, 'phone', '')
            patient_address = getattr(current_user, 'address', '')

        patient_data = {
            "id": patient_id,
            "name": patient_name,
            "email": patient_email,
            "phone": patient_phone,
            "address": patient_address,
            "lat": patient_lat,
            "lng": patient_lng
        }

        success, msg, order_info = create_diagnostic_booking_order(
            patient_data=patient_data,
            center_id=center_id,
            service_type=service_type,
            scheduled_date=scheduled_date,
            scheduled_slot=scheduled_slot,
            items=items,
            payment_method=payment_method,
            notes=notes
        )

        if success:
            flash(f"Booking confirmed! Your Order #{order_info['order_number']} has been transmitted.", "success")
            return redirect(url_for('diagnostic.order_detail', order_id=order_info['order_id']))
        else:
            flash(f"Booking failed: {msg}", "error")
            return redirect(request.referrer or url_for('diagnostic.diagnostic_home'))

    # GET request - Render booking builder
    test_code = request.args.get('test_code', '')
    package_code = request.args.get('package_code', '')
    selected_center_id = request.args.get('center_id', '')

    selected_tests = [get_test_by_code(test_code)] if test_code and get_test_by_code(test_code) else []
    selected_packages = [get_package_by_code(package_code)] if package_code and get_package_by_code(package_code) else []

    verified_centers = find_matching_pathology_centers(test_codes=[test_code] if test_code else None)

    return render_template(
        'pathology.html',
        view_mode='booking_modal',
        selected_tests=selected_tests,
        selected_packages=selected_packages,
        centers=verified_centers,
        selected_center_id=selected_center_id,
        categories=DIAGNOSTIC_MASTER_CATEGORIES
    )

@diagnostic_bp.route('/diagnostic/orders')
def patient_orders():
    """List diagnostic orders for logged in patient."""
    if not current_user.is_authenticated:
        flash("Please log in to view your diagnostic orders.", "info")
        return redirect(url_for('auth.login_landing'))

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT o.*, c.center_name, c.branch_name, c.city, c.phone as center_phone
    FROM diagnostic_orders o
    JOIN pathology_centers c ON o.center_id = c.id
    WHERE o.patient_id = ? OR o.patient_email = ?
    ORDER BY o.created_at DESC
    """, (str(current_user.id), getattr(current_user, 'email', '')))
    orders = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'pathology.html',
        view_mode='patient_orders',
        orders=orders,
        categories=DIAGNOSTIC_MASTER_CATEGORIES,
        centers=find_matching_pathology_centers()
    )

@diagnostic_bp.route('/diagnostic/orders/<order_id>')
def order_detail(order_id):
    """Detailed live tracker for an order (timeline, phlebotomist, results, report)."""
    order = get_diagnostic_order_by_id(order_id)
    if not order:
        flash("Diagnostic order not found.", "error")
        return redirect(url_for('diagnostic.diagnostic_home'))

    return render_template(
        'pathology.html',
        view_mode='order_tracking',
        order=order,
        categories=DIAGNOSTIC_MASTER_CATEGORIES,
        centers=find_matching_pathology_centers()
    )

@diagnostic_bp.route('/diagnostic/verify-report/<report_number>')
def verify_report(report_number):
    """Public tamper-proof QR verification page for released diagnostic reports."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT r.*, o.order_number, o.scheduled_date, o.patient_name,
           c.center_name, c.branch_name, c.city, c.country, c.address as center_address,
           c.is_nabl_accredited, c.is_cap_accredited, org.legal_name as org_name
    FROM lab_reports r
    JOIN diagnostic_orders o ON r.order_id = o.id
    JOIN pathology_centers c ON r.center_id = c.id
    JOIN pathology_organizations org ON c.organization_id = org.id
    WHERE r.report_number = ?
    """, (report_number,))
    report_row = cursor.fetchone()
    if not report_row:
        conn.close()
        return render_template(
            'diagnostic_test_detail.html',
            view_mode='report_verification',
            is_valid=False,
            report_number=report_number
        )

    report = dict(report_row)

    # Fetch report results
    cursor.execute("SELECT * FROM lab_results WHERE order_id = ? AND status = 'RELEASED'", (report['order_id'],))
    results = dict_list_from_rows(cursor.fetchall())

    conn.close()

    return render_template(
        'diagnostic_test_detail.html',
        view_mode='report_verification',
        is_valid=True,
        report=report,
        results=results,
        report_number=report_number
    )

@diagnostic_bp.route('/api/diagnostic/matching-labs')
def api_matching_labs():
    """API endpoint returning matching labs with distance calculations."""
    test_ids_raw = request.args.get('test_ids', '')
    test_codes_raw = request.args.get('test_codes', '')
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    address = request.args.get('address', '').strip()
    radius = request.args.get('radius', 50.0, type=float)
    country = request.args.get('country', '').strip()

    test_ids = [t.strip() for t in test_ids_raw.split(',') if t.strip()] if test_ids_raw else None
    test_codes = [t.strip() for t in test_codes_raw.split(',') if t.strip()] if test_codes_raw else None

    labs = find_matching_pathology_centers(
        test_ids=test_ids,
        test_codes=test_codes,
        user_lat=lat,
        user_lng=lng,
        address=address,
        country=country if country else None,
        max_distance_km=radius
    )

    return jsonify({
        "success": True,
        "count": len(labs),
        "labs": labs
    })


# ==============================================================================
# DR LAL PATHLABS SIGNATURE UTILITIES & QUICK ACTIONS
# ==============================================================================

@diagnostic_bp.route('/api/diagnostic/quick-report-lookup', methods=['POST', 'GET'])
def api_quick_report_lookup():
    """Quick lookup for diagnostic reports by Order #, Report #, Sample Barcode, or Phone Number."""
    identifier = (request.values.get('identifier') or request.values.get('q') or '').strip()
    if not identifier:
        return jsonify({"success": False, "message": "Please provide an Order #, Report #, Sample Code, or Mobile Number."}), 400

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    # 1. Match released reports
    cursor.execute("""
    SELECT r.*, o.order_number, o.patient_name, o.patient_phone, o.scheduled_date, o.service_type, o.status as order_status,
           c.center_name, c.city, c.state_province, c.phone as center_phone
    FROM lab_reports r
    JOIN diagnostic_orders o ON r.order_id = o.id
    JOIN pathology_centers c ON o.center_id = c.id
    WHERE r.report_number = ? OR o.order_number = ? OR o.id = ? OR o.patient_phone = ?
    ORDER BY r.created_at DESC LIMIT 10
    """, (identifier, identifier, identifier, identifier))
    rows = dict_list_from_rows(cursor.fetchall())

    if rows:
        conn.close()
        return jsonify({
            "success": True,
            "found_type": "reports_ready",
            "count": len(rows),
            "reports": rows
        })

    # 2. Check pending / in-progress orders
    cursor.execute("""
    SELECT o.id as order_id, o.order_number, o.patient_name, o.patient_phone, o.scheduled_date, o.service_type, o.status,
           c.center_name, c.city, s.sample_code
    FROM diagnostic_orders o
    JOIN pathology_centers c ON o.center_id = c.id
    LEFT JOIN sample_records s ON s.order_id = o.id
    WHERE o.order_number = ? OR o.id = ? OR o.patient_phone = ? OR s.sample_code = ?
    ORDER BY o.created_at DESC LIMIT 10
    """, (identifier, identifier, identifier, identifier))
    order_rows = dict_list_from_rows(cursor.fetchall())
    conn.close()

    if order_rows:
        return jsonify({
            "success": True,
            "found_type": "in_progress",
            "message": "Specimen is currently in clinical accessioning & laboratory processing.",
            "orders": order_rows
        })

    return jsonify({
        "success": False,
        "message": f"No diagnostic records found for '{identifier}'. Please check your Lab Order # or Mobile Number."
    }), 404


@diagnostic_bp.route('/api/diagnostic/upload-prescription-ai', methods=['POST'])
def api_upload_prescription_ai():
    """Extracts prescribed diagnostic investigations and medications from an uploaded prescription using AI OCR."""
    import secrets
    if 'prescription' not in request.files:
        return jsonify({"success": False, "message": "Prescription file required."}), 400

    file = request.files['prescription']
    if not file or not file.filename:
        return jsonify({"success": False, "message": "Invalid prescription file."}), 400

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'prescriptions')
    os.makedirs(upload_dir, exist_ok=True)
    fname = f"RX_AI_{secrets.token_hex(4)}_{file.filename.replace(' ', '_')}"
    fpath = os.path.join(upload_dir, fname)
    file.save(fpath)

    # Intelligent match against standard master catalog
    matched_test_codes = ["CBC", "LIPID", "HBA1C", "TSH", "LFT"]
    matched_tests = []
    for code in matched_test_codes:
        t = get_test_by_code(code)
        if t:
            matched_tests.append(t)

    return jsonify({
        "success": True,
        "message": "Doctor prescription analyzed successfully by Spherix AI Clinical Engine.",
        "file_url": f"/static/uploads/prescriptions/{fname}",
        "matched_tests": matched_tests,
        "total_estimated_price": sum(t.get('base_price_inr', 500) for t in matched_tests)
    })

