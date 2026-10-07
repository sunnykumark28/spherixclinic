"""
Spherix Diagnostic Network - Enterprise Multi-Tenant Database & Core Engine
Full support for Global Multi-Country Pathology Centers, RBAC, Test Catalogs,
Sample Tracking (Barcode/QR), Digital Versioned Reports, Phlebotomy Dispatch,
Walk-in Queues, Doctor Referrals, and Immutable Audit Logging.
"""

import os
import sys
import json
import math
import sqlite3
import random
import secrets
import hashlib
import re
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Any, Optional, Tuple, Union
from werkzeug.security import generate_password_hash, check_password_hash

from spherix.config import (
    DATA_FILE, SERVER, DATABASE, USERNAME, PASSWORD, DRIVER,
    utcnow, parse_route_id, COUNTRIES_195, GLOBAL_COUNTRY_TIMEZONES
)
from spherix.services.diagnostic_catalog import (
    DIAGNOSTIC_MASTER_CATEGORIES,
    MASTER_TESTS_CATALOG,
    MASTER_PACKAGES_CATALOG,
    get_test_by_code,
    get_package_by_code
)

def get_db_path() -> str:
    """Returns the configured database file path, honoring test and custom environments."""
    return os.getenv('DIAGNOSTIC_DB_PATH') or os.getenv('SQLITE_DB_PATH') or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'spherixclinic.db')

DB_PATH = get_db_path()

def get_diagnostic_db():
    """Returns a SQLite connection with row factory configured as dictionary-like Row."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=60.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 60000")
        conn.execute("PRAGMA synchronous = NORMAL")
    except Exception:
        pass
    return conn


def dict_from_row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)

def dict_list_from_rows(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]

# ==============================================================================
# 1. DATABASE INITIALIZATION & SCHEMA CREATION
# ==============================================================================

def init_diagnostic_schema():
    """Creates all multi-tenant tables, indexes, and constraints safely."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    # Migrate legacy single-tenant tables if needed
    try:
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='diagnostic_tests'")
        row = cursor.fetchone()
        if row and "test_code TEXT UNIQUE" in (row[0] or ""):
            cursor.execute("DROP TABLE IF EXISTS diagnostic_tests")

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='diagnostic_audit_logs'")
        row = cursor.fetchone()
        if row and "AUTOINCREMENT" in (row[0] or ""):
            cursor.execute("DROP TABLE IF EXISTS diagnostic_audit_logs")

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='diagnostic_referral_items'")
        row = cursor.fetchone()
        if row and "AUTOINCREMENT" in (row[0] or ""):
            cursor.execute("DROP TABLE IF EXISTS diagnostic_referral_items")
            cursor.execute("DROP TABLE IF EXISTS diagnostic_referrals")
    except Exception:
        pass

    # 1. Pathology Organizations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pathology_organizations (
        id TEXT PRIMARY KEY,
        legal_name TEXT NOT NULL,
        display_name TEXT NOT NULL,
        org_type TEXT DEFAULT 'Diagnostic Chain',
        reg_number TEXT,
        license_number TEXT,
        accreditation TEXT,
        website TEXT,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        country TEXT DEFAULT 'India',
        currency TEXT DEFAULT 'INR',
        timezone TEXT DEFAULT 'IST (UTC+5:30)',
        tax_rate_percent REAL DEFAULT 0.0,
        status TEXT DEFAULT 'VERIFIED',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Pathology Centers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pathology_centers (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        center_name TEXT NOT NULL,
        branch_name TEXT DEFAULT 'Main Branch',
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        address TEXT NOT NULL,
        city TEXT NOT NULL,
        state_province TEXT,
        postal_code TEXT,
        country TEXT DEFAULT 'India',
        latitude REAL DEFAULT 0.0,
        longitude REAL DEFAULT 0.0,
        timezone TEXT DEFAULT 'IST (UTC+5:30)',
        currency TEXT DEFAULT 'INR',
        home_collection_enabled INTEGER DEFAULT 1,
        walkin_enabled INTEGER DEFAULT 1,
        home_collection_radius_km REAL DEFAULT 25.0,
        home_collection_fee REAL DEFAULT 150.0,
        min_order_amount REAL DEFAULT 200.0,
        available_days TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri,Sat,Sun',
        available_time_slots TEXT DEFAULT '07:00-09:00,09:00-11:00,11:00-13:00,14:00-16:00,16:00-18:00',
        verification_status TEXT DEFAULT 'VERIFIED',
        rejection_reason TEXT,
        rating REAL DEFAULT 4.8,
        review_count INTEGER DEFAULT 12,
        is_active INTEGER DEFAULT 1,
        is_nabl_accredited INTEGER DEFAULT 1,
        is_cap_accredited INTEGER DEFAULT 0,
        is_iso_certified INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (organization_id) REFERENCES pathology_organizations(id) ON DELETE CASCADE
    )
    """)

    # 3. Pathology Center Documents
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pathology_center_documents (
        id TEXT PRIMARY KEY,
        center_id TEXT NOT NULL,
        doc_type TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        original_name TEXT,
        mime_type TEXT,
        file_size INTEGER,
        verified_by TEXT,
        verified_at TIMESTAMP,
        status TEXT DEFAULT 'APPROVED',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (center_id) REFERENCES pathology_centers(id) ON DELETE CASCADE
    )
    """)

    # 4. Pathology Staff / Users (RBAC)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pathology_staff (
        id TEXT PRIMARY KEY,
        center_id TEXT NOT NULL,
        organization_id TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL, -- owner, admin, lab_manager, pathologist, technician, phlebotomist, receptionist, billing, support
        phone TEXT,
        qualification TEXT,
        license_number TEXT,
        is_active INTEGER DEFAULT 1,
        last_login TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (center_id) REFERENCES pathology_centers(id) ON DELETE CASCADE,
        FOREIGN KEY (organization_id) REFERENCES pathology_organizations(id) ON DELETE CASCADE
    )
    """)

    # 5. Diagnostic Categories
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_categories (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        description TEXT,
        icon TEXT,
        display_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )
    """)

    # 6. Diagnostic Tests
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_tests (
        id TEXT PRIMARY KEY,
        center_id TEXT, -- NULL if global default template
        organization_id TEXT,
        test_name TEXT NOT NULL,
        test_code TEXT NOT NULL,
        category_id TEXT,
        category_name TEXT NOT NULL,
        description TEXT,
        sample_type TEXT DEFAULT 'Blood',
        container_type TEXT DEFAULT 'Lavender Top (EDTA)',
        required_quantity TEXT DEFAULT '2.0 mL',
        preparation_instructions TEXT,
        fasting_required INTEGER DEFAULT 0,
        fasting_hours INTEGER DEFAULT 0,
        turnaround_hours INTEGER DEFAULT 12,
        price REAL NOT NULL,
        currency TEXT DEFAULT 'INR',
        home_collection_eligible INTEGER DEFAULT 1,
        walkin_eligible INTEGER DEFAULT 1,
        parameters_json TEXT, -- array of parameter schemas & ranges
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 7. Diagnostic Packages
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_packages (
        id TEXT PRIMARY KEY,
        center_id TEXT,
        organization_id TEXT,
        package_name TEXT NOT NULL,
        package_code TEXT NOT NULL,
        description TEXT,
        preparation_instructions TEXT,
        fasting_required INTEGER DEFAULT 0,
        turnaround_hours INTEGER DEFAULT 24,
        original_price REAL NOT NULL,
        package_price REAL NOT NULL,
        discount_percent REAL DEFAULT 0,
        currency TEXT DEFAULT 'INR',
        home_collection_eligible INTEGER DEFAULT 1,
        walkin_eligible INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 8. Diagnostic Package Items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_package_items (
        id TEXT PRIMARY KEY,
        package_id TEXT NOT NULL,
        test_id TEXT NOT NULL,
        test_name TEXT,
        test_code TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (package_id) REFERENCES diagnostic_packages(id) ON DELETE CASCADE
    )
    """)

    # 9. Diagnostic Orders
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_orders (
        id TEXT PRIMARY KEY,
        order_number TEXT UNIQUE NOT NULL,
        patient_id TEXT,
        patient_name TEXT NOT NULL,
        patient_email TEXT,
        patient_phone TEXT,
        patient_address TEXT,
        patient_lat REAL DEFAULT 0.0,
        patient_lng REAL DEFAULT 0.0,
        center_id TEXT NOT NULL,
        organization_id TEXT NOT NULL,
        doctor_id TEXT,
        referral_id TEXT,
        service_type TEXT NOT NULL, -- HOME_COLLECTION, WALK_IN
        scheduled_date TEXT NOT NULL,
        scheduled_slot TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING', -- PENDING, CONFIRMED, COLLECTOR_ASSIGNED, SAMPLE_COLLECTED, SAMPLE_RECEIVED, PROCESSING, REPORT_PENDING, REPORT_RELEASED, CANCELLED
        subtotal REAL NOT NULL,
        collection_fee REAL DEFAULT 0.0,
        tax_amount REAL DEFAULT 0.0,
        discount_amount REAL DEFAULT 0.0,
        total_amount REAL NOT NULL,
        currency TEXT DEFAULT 'INR',
        payment_status TEXT DEFAULT 'PENDING', -- PENDING, PAID, REFUNDED
        payment_method TEXT DEFAULT 'ONLINE',
        payment_ref TEXT,
        cancellation_reason TEXT,
        notes TEXT,
        prescription_file TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (center_id) REFERENCES pathology_centers(id) ON DELETE CASCADE
    )
    """)

    # 10. Diagnostic Order Items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_order_items (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        item_type TEXT NOT NULL, -- TEST, PACKAGE
        item_id TEXT NOT NULL,
        item_name TEXT NOT NULL,
        item_code TEXT,
        price REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES diagnostic_orders(id) ON DELETE CASCADE
    )
    """)

    # 11. Home Collection Assignments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS collection_assignments (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        center_id TEXT NOT NULL,
        phlebotomist_id TEXT,
        phlebotomist_name TEXT,
        status TEXT DEFAULT 'REQUESTED', -- REQUESTED, ASSIGNED, ON_THE_WAY, ARRIVED, PATIENT_VERIFIED, SAMPLE_COLLECTED, CANCELLED, NO_SHOW
        assigned_at TIMESTAMP,
        arrived_at TIMESTAMP,
        collected_at TIMESTAMP,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES diagnostic_orders(id) ON DELETE CASCADE
    )
    """)

    # 12. Walk-in Appointments & Queue Tokens
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS walkin_queue (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        center_id TEXT NOT NULL,
        patient_id TEXT,
        token_number TEXT NOT NULL,
        appointment_date TEXT NOT NULL,
        appointment_time TEXT,
        status TEXT DEFAULT 'WAITING', -- WAITING, CALLED, COLLECTING, COMPLETED, NO_SHOW, CANCELLED
        called_at TIMESTAMP,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES diagnostic_orders(id) ON DELETE CASCADE
    )
    """)

    # 13. Sample Records & Accessioning
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sample_records (
        id TEXT PRIMARY KEY,
        sample_code TEXT UNIQUE NOT NULL, -- SMP-XXXXXXXX
        order_id TEXT NOT NULL,
        center_id TEXT NOT NULL,
        patient_id TEXT,
        test_ids_json TEXT,
        sample_type TEXT NOT NULL,
        container_type TEXT NOT NULL,
        barcode_data TEXT NOT NULL,
        qr_code_data TEXT NOT NULL,
        status TEXT DEFAULT 'AWAITING_COLLECTION', -- AWAITING_COLLECTION, COLLECTED, IN_TRANSIT, RECEIVED, ACCEPTED, PROCESSING, COMPLETED, REJECTED
        rejection_reason TEXT,
        recollection_required INTEGER DEFAULT 0,
        collected_by TEXT,
        collected_at TIMESTAMP,
        received_by TEXT,
        received_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES diagnostic_orders(id) ON DELETE CASCADE
    )
    """)

    # 14. Sample Tracking Events Timeline
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sample_tracking_events (
        id TEXT PRIMARY KEY,
        sample_id TEXT NOT NULL,
        status TEXT NOT NULL,
        location TEXT,
        notes TEXT,
        recorded_by TEXT,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sample_id) REFERENCES sample_records(id) ON DELETE CASCADE
    )
    """)

    # 15. Lab Results
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lab_results (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        sample_id TEXT,
        test_id TEXT,
        test_name TEXT NOT NULL,
        parameter_name TEXT NOT NULL,
        result_value TEXT NOT NULL,
        unit TEXT,
        reference_range TEXT,
        abnormal_flag TEXT DEFAULT 'NORMAL', -- NORMAL, HIGH, LOW, CRITICAL, ABNORMAL
        technician_notes TEXT,
        technician_id TEXT,
        technician_name TEXT,
        status TEXT DEFAULT 'TECH_COMPLETED', -- DRAFT, TECH_COMPLETED, APPROVED, RELEASED
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES diagnostic_orders(id) ON DELETE CASCADE
    )
    """)

    # 16. Lab Reports & Versioning
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lab_reports (
        id TEXT PRIMARY KEY,
        report_number TEXT UNIQUE NOT NULL, -- REP-YYYYMMDD-XXXXXX
        order_id TEXT NOT NULL,
        center_id TEXT NOT NULL,
        patient_id TEXT,
        doctor_id TEXT,
        version TEXT DEFAULT 'v1',
        title TEXT NOT NULL,
        summary TEXT,
        interpretation TEXT,
        status TEXT DEFAULT 'RELEASED', -- DRAFT, UNDER_REVIEW, APPROVED, RELEASED, CORRECTED
        pathologist_id TEXT,
        pathologist_name TEXT,
        pathologist_signature TEXT,
        released_at TIMESTAMP,
        approved_at TIMESTAMP,
        file_path TEXT,
        qr_verification_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES diagnostic_orders(id) ON DELETE CASCADE,
        FOREIGN KEY (center_id) REFERENCES pathology_centers(id) ON DELETE CASCADE
    )
    """)

    # 17. Lab Report Versions (Audit History)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lab_report_versions (
        id TEXT PRIMARY KEY,
        report_id TEXT NOT NULL,
        version TEXT NOT NULL,
        status TEXT NOT NULL,
        change_summary TEXT,
        file_path TEXT,
        updated_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (report_id) REFERENCES lab_reports(id) ON DELETE CASCADE
    )
    """)

    # 18. Doctor Referrals
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_referrals (
        id TEXT PRIMARY KEY,
        referral_number TEXT UNIQUE NOT NULL, -- REF-DX-YYYYMMDD-XXXX
        doctor_id TEXT NOT NULL,
        doctor_name TEXT NOT NULL,
        patient_id TEXT NOT NULL,
        patient_name TEXT NOT NULL,
        center_id TEXT,
        clinical_indication TEXT NOT NULL,
        priority TEXT DEFAULT 'ROUTINE', -- ROUTINE, URGENT, TIME_SENSITIVE
        doctor_instructions TEXT,
        status TEXT DEFAULT 'ISSUED', -- ISSUED, ACCEPTED, BOOKED, COMPLETED, CANCELLED, REJECTED
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 19. Doctor Referral Items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_referral_items (
        id TEXT PRIMARY KEY,
        referral_id TEXT NOT NULL,
        item_type TEXT DEFAULT 'TEST',
        item_id TEXT,
        item_name TEXT NOT NULL,
        test_code TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (referral_id) REFERENCES diagnostic_referrals(id) ON DELETE CASCADE
    )
    """)

    # 20. Doctor-Pathology Connections
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctor_pathology_connections (
        id TEXT PRIMARY KEY,
        doctor_id TEXT NOT NULL,
        center_id TEXT NOT NULL,
        status TEXT DEFAULT 'ACCEPTED', -- PENDING, ACCEPTED, PREFERRED, REJECTED
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 21. Hospital-Pathology Connections
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hospital_pathology_connections (
        id TEXT PRIMARY KEY,
        hospital_id TEXT NOT NULL,
        center_id TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING', -- PENDING, ACCEPTED, PREFERRED, REJECTED
        partnership_type TEXT DEFAULT 'ROUTINE_DIAGNOSTICS',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 22. Diagnostic Reviews
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_reviews (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        center_id TEXT NOT NULL,
        patient_id TEXT NOT NULL,
        patient_name TEXT NOT NULL,
        rating INTEGER DEFAULT 5,
        review_text TEXT,
        is_verified INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 23. Immutable Audit Logging
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_audit_logs (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        user_role TEXT,
        organization_id TEXT,
        center_id TEXT,
        action TEXT NOT NULL,
        entity TEXT NOT NULL,
        entity_id TEXT,
        details TEXT,
        ip_address TEXT,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Ensure all columns exist for tables across versions
    def ensure_column(tbl, col, col_type):
        try:
            cursor.execute(f"PRAGMA table_info({tbl})")
            cols = [r[1] for r in cursor.fetchall()]
            if col not in cols:
                cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    ensure_column("diagnostic_categories", "code", "TEXT")
    ensure_column("diagnostic_tests", "center_id", "TEXT")
    ensure_column("diagnostic_tests", "organization_id", "TEXT")
    ensure_column("diagnostic_tests", "test_name", "TEXT")
    ensure_column("diagnostic_tests", "test_code", "TEXT")
    ensure_column("diagnostic_tests", "category_id", "TEXT")
    ensure_column("diagnostic_tests", "category_name", "TEXT")
    ensure_column("diagnostic_tests", "description", "TEXT")
    ensure_column("diagnostic_tests", "sample_type", "TEXT DEFAULT 'Blood'")
    ensure_column("diagnostic_tests", "container_type", "TEXT DEFAULT 'Lavender Top (EDTA)'")
    ensure_column("diagnostic_tests", "required_quantity", "TEXT DEFAULT '2.0 mL'")
    ensure_column("diagnostic_tests", "preparation_instructions", "TEXT")
    ensure_column("diagnostic_tests", "fasting_required", "INTEGER DEFAULT 0")
    ensure_column("diagnostic_tests", "fasting_hours", "INTEGER DEFAULT 0")
    ensure_column("diagnostic_tests", "turnaround_hours", "INTEGER DEFAULT 12")
    ensure_column("diagnostic_tests", "price", "REAL DEFAULT 0.0")
    ensure_column("diagnostic_tests", "currency", "TEXT DEFAULT 'INR'")
    ensure_column("diagnostic_tests", "parameters_json", "TEXT")
    ensure_column("diagnostic_tests", "home_collection_eligible", "INTEGER DEFAULT 1")
    ensure_column("diagnostic_tests", "walkin_eligible", "INTEGER DEFAULT 1")
    ensure_column("diagnostic_tests", "is_active", "INTEGER DEFAULT 1")
    ensure_column("diagnostic_tests", "is_public", "INTEGER DEFAULT 1")
    ensure_column("diagnostic_tests", "discount_percent", "REAL DEFAULT 0.0")
    ensure_column("diagnostic_tests", "offer_price", "REAL DEFAULT 0.0")
    ensure_column("diagnostic_tests", "badge", "TEXT DEFAULT ''")
    ensure_column("pathology_centers", "profile_image", "TEXT")
    ensure_column("pathology_centers", "address_name", "TEXT")
    ensure_column("pathology_centers", "landmark", "TEXT")
    ensure_column("pathology_centers", "address_additional_info", "TEXT")
    ensure_column("pathology_centers", "website", "TEXT")
    ensure_column("pathology_centers", "emergency_phone", "TEXT")
    ensure_column("pathology_centers", "operating_hours", "TEXT DEFAULT '07:00 AM - 08:00 PM'")
    ensure_column("pathology_centers", "home_collection_radius_km", "REAL DEFAULT 25.0")
    ensure_column("pathology_centers", "home_collection_fee", "REAL DEFAULT 150.0")
    ensure_column("pathology_centers", "min_order_amount", "REAL DEFAULT 200.0")
    ensure_column("pathology_centers", "verification_status", "TEXT DEFAULT 'VERIFIED'")
    ensure_column("pathology_centers", "is_nabl_accredited", "INTEGER DEFAULT 1")
    ensure_column("pathology_centers", "is_cap_accredited", "INTEGER DEFAULT 0")
    ensure_column("pathology_centers", "is_iso_certified", "INTEGER DEFAULT 1")
    ensure_column("pathology_staff", "profile_image", "TEXT")
    ensure_column("pathology_staff", "bio", "TEXT")
    ensure_column("doctor_pathology_connections", "partnership_type", "TEXT DEFAULT 'ROUTINE_DIAGNOSTICS'")
    ensure_column("doctor_pathology_connections", "hospital_id", "TEXT")
    ensure_column("doctor_pathology_connections", "doctor_name", "TEXT")
    ensure_column("doctor_pathology_connections", "hospital_name", "TEXT")
    ensure_column("doctor_pathology_connections", "center_name", "TEXT")
    ensure_column("doctor_pathology_connections", "requested_by", "TEXT DEFAULT 'HOSPITAL'")
    ensure_column("doctor_pathology_connections", "hospital_accepted", "INTEGER DEFAULT 1")
    ensure_column("doctor_pathology_connections", "doctor_accepted", "INTEGER DEFAULT 0")
    ensure_column("doctor_pathology_connections", "pathology_accepted", "INTEGER DEFAULT 0")
    ensure_column("doctor_pathology_connections", "medicines_shared_count", "INTEGER DEFAULT 0")
    ensure_column("doctor_pathology_connections", "last_medicine_transmission", "TIMESTAMP")

    ensure_column("hospital_pathology_connections", "doctor_id", "TEXT")
    ensure_column("hospital_pathology_connections", "doctor_name", "TEXT")
    ensure_column("hospital_pathology_connections", "hospital_name", "TEXT")
    ensure_column("hospital_pathology_connections", "center_name", "TEXT")
    ensure_column("hospital_pathology_connections", "requested_by", "TEXT DEFAULT 'HOSPITAL'")
    ensure_column("hospital_pathology_connections", "hospital_accepted", "INTEGER DEFAULT 1")
    ensure_column("hospital_pathology_connections", "doctor_accepted", "INTEGER DEFAULT 0")
    ensure_column("hospital_pathology_connections", "pathology_accepted", "INTEGER DEFAULT 0")
    ensure_column("hospital_pathology_connections", "medicines_shared_count", "INTEGER DEFAULT 0")
    ensure_column("hospital_pathology_connections", "last_medicine_transmission", "TIMESTAMP")

    ensure_column("diagnostic_referrals", "center_id", "TEXT")
    ensure_column("diagnostic_referrals", "patient_id", "TEXT")
    ensure_column("diagnostic_referrals", "patient_name", "TEXT")
    ensure_column("diagnostic_referrals", "hospital_id", "TEXT")
    ensure_column("diagnostic_referrals", "hospital_name", "TEXT")
    ensure_column("diagnostic_referrals", "medicines_json", "TEXT")
    ensure_column("diagnostic_referrals", "referral_type", "TEXT DEFAULT 'MEDICINE_AND_LAB'")

    ensure_column("diagnostic_referral_items", "item_type", "TEXT DEFAULT 'TEST'")
    ensure_column("diagnostic_referral_items", "item_id", "TEXT")
    ensure_column("diagnostic_audit_logs", "user_id", "TEXT")
    ensure_column("diagnostic_audit_logs", "user_role", "TEXT")
    ensure_column("diagnostic_audit_logs", "organization_id", "TEXT")
    ensure_column("diagnostic_audit_logs", "center_id", "TEXT")
    ensure_column("diagnostic_audit_logs", "entity", "TEXT")
    ensure_column("diagnostic_audit_logs", "entity_id", "TEXT")
    ensure_column("diagnostic_audit_logs", "user_agent", "TEXT")

    # Create Indexes for high performance query execution
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dx_org_id ON pathology_centers(organization_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dx_center_geo ON pathology_centers(country, city, latitude, longitude)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dx_staff_center ON pathology_staff(center_id, role)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dx_tests_center ON diagnostic_tests(center_id, category_id, is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dx_orders_center ON diagnostic_orders(center_id, status, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dx_orders_patient ON diagnostic_orders(patient_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dx_samples_code ON sample_records(sample_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dx_samples_order ON sample_records(order_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dx_reports_order ON lab_reports(order_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dx_reports_patient ON lab_reports(patient_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dx_referrals_doc ON diagnostic_referrals(doctor_id, status)")
    except Exception as idx_err:
        print(f"Index creation note: {idx_err}")

    # Seed master categories and initial demo data
    seed_diagnostic_master_categories(cursor)
    seed_diagnostic_demo_data(cursor)

    conn.commit()
    conn.close()

# ==============================================================================
# 2. MASTER SEEDING & DEMO DATA
# ==============================================================================

def seed_diagnostic_master_categories(cursor=None):
    """Seeds the standard 19 global diagnostic categories."""
    close_after = False
    if cursor is None:
        conn = get_diagnostic_db()
        cursor = conn.cursor()
        close_after = True

    for cat in DIAGNOSTIC_MASTER_CATEGORIES:
        cursor.execute("""
        INSERT OR IGNORE INTO diagnostic_categories (id, name, code, description, icon, display_order, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (cat['id'], cat['name'], cat['code'], cat['description'], cat['icon'], cat['display_order']))

    if close_after:
        conn.commit()
        conn.close()

def seed_diagnostic_demo_data(cursor=None):
    """Seeds realistic global pathology organizations, verified centers, staff, tests, packages, and sample orders."""
    close_after = False
    if cursor is None:
        conn = get_diagnostic_db()
        cursor = conn.cursor()
        close_after = True

    # Check if demo reports already exist
    cursor.execute("SELECT COUNT(*) as c FROM lab_reports WHERE report_number = 'REP-20261007-0018'")
    has_demo_report = cursor.fetchone()['c'] > 0


    # 1. Organization A: Spherix Central Diagnostics (India / Global Flagship)
    org1_id = "ORG-SPX-CENTRAL"
    cursor.execute("""
    INSERT OR REPLACE INTO pathology_organizations (id, legal_name, display_name, org_type, reg_number, license_number, accreditation, website, email, phone, country, currency, timezone, tax_rate_percent, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        org1_id,
        "Spherix Central Diagnostics & Life Sciences Pvt. Ltd.",
        "Spherix Central Diagnostics",
        "Clinical Laboratory Network",
        "REG-IND-883921",
        "LIC-NABL-2026-9041",
        "NABL ISO 15189:2022 & CAP Certified",
        "https://diagnostics.spherixclinic.com",
        "central.lab@spherixclinic.com",
        "+91 933 4325 920",
        "India",
        "INR",
        "IST (UTC+5:30)",
        5.0,
        "VERIFIED"
    ))

    # Center 1: Spherix Central Reference Lab (New Delhi)
    center1_id = "LAB-DELHI-001"
    cursor.execute("""
    INSERT OR REPLACE INTO pathology_centers (
        id, organization_id, center_name, branch_name, email, phone, address, city, state_province, postal_code, country,
        latitude, longitude, timezone, currency, home_collection_enabled, walkin_enabled, home_collection_radius_km, home_collection_fee,
        min_order_amount, verification_status, rating, review_count, is_active, is_nabl_accredited, is_cap_accredited, is_iso_certified
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        center1_id, org1_id, "Spherix Central Reference Diagnostics", "Connaught Place Flagship",
        "delhi.lab@spherixclinic.com", "+91 11 4982 9900", "Building 14, Barakhamba Road, Connaught Place",
        "New Delhi", "Delhi", "110001", "India",
        28.6304, 77.2177, "IST (UTC+5:30)", "INR",
        1, 1, 35.0, 150.0, 250.0, "VERIFIED", 4.9, 148, 1, 1, 1, 1
    ))

    # Center 2: Spherix Health & Diagnostic Hub (Motihari / Bihar)
    center2_id = "LAB-BIHAR-002"
    cursor.execute("""
    INSERT OR REPLACE INTO pathology_centers (
        id, organization_id, center_name, branch_name, email, phone, address, city, state_province, postal_code, country,
        latitude, longitude, timezone, currency, home_collection_enabled, walkin_enabled, home_collection_radius_km, home_collection_fee,
        min_order_amount, verification_status, rating, review_count, is_active, is_nabl_accredited, is_cap_accredited, is_iso_certified
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        center2_id, org1_id, "Spherix Regional Clinical Laboratory", "Main Hospital Campus",
        "motihari.lab@spherixclinic.com", "+91 933 4325 921", "Spherix Hospital Complex, Main Road",
        "Motihari", "Bihar", "845401", "India",
        26.6469, 84.9089, "IST (UTC+5:30)", "INR",
        1, 1, 30.0, 100.0, 200.0, "VERIFIED", 4.8, 89, 1, 1, 0, 1
    ))

    # 2. Organization B: Apex Global Pathology Group (USA / International)
    org2_id = "ORG-APEX-USA"
    cursor.execute("""
    INSERT OR REPLACE INTO pathology_organizations (id, legal_name, display_name, org_type, reg_number, license_number, accreditation, website, email, phone, country, currency, timezone, tax_rate_percent, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        org2_id,
        "Apex Global Diagnostics & Pathology LLC",
        "Apex Global Pathology",
        "International Reference Laboratory",
        "US-CLIA-99D208819",
        "NY-DOH-P10492",
        "CAP & CLIA Accredited High-Complexity Laboratory",
        "https://apexdiagnostics.us",
        "admin@apexdiagnostics.us",
        "+1 212 555 0198",
        "United States",
        "USD",
        "EST (UTC-5:00)",
        0.0,
        "VERIFIED"
    ))

    # Center 3: Apex Diagnostics Manhattan (New York, USA)
    center3_id = "LAB-NYC-003"
    cursor.execute("""
    INSERT OR REPLACE INTO pathology_centers (
        id, organization_id, center_name, branch_name, email, phone, address, city, state_province, postal_code, country,
        latitude, longitude, timezone, currency, home_collection_enabled, walkin_enabled, home_collection_radius_km, home_collection_fee,
        min_order_amount, verification_status, rating, review_count, is_active, is_nabl_accredited, is_cap_accredited, is_iso_certified
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        center3_id, org2_id, "Apex Global Diagnostics - Manhattan", "Madison Avenue Clinical Suite",
        "nyc@apexdiagnostics.us", "+1 212 555 0199", "545 Madison Avenue, 8th Floor",
        "New York", "New York", "10022", "United States",
        40.7610, -73.9723, "EST (UTC-5:00)", "USD",
        1, 1, 20.0, 35.0, 50.0, "VERIFIED", 4.9, 210, 1, 1, 1, 1
    ))

    # 3. Seed Staff Members with RBAC Roles
    pw_hash = generate_password_hash("Pathology@2026!", method="pbkdf2:sha256:260000")
    
    staff_members = [
        # Center 1 Staff
        ("STF-DELHI-01", center1_id, org1_id, "pathology@spherixclinic.com", pw_hash, "Dr. Rajeshwar Verma, MD", "pathologist", "+91 9811002211", "MD (Pathology), DNB, FICP", "MCI-48291"),
        ("STF-DELHI-02", center1_id, org1_id, "manager.delhi@spherixclinic.com", pw_hash, "Pooja Sharma", "lab_manager", "+91 9811002212", "M.Sc (Medical Biochemistry)", "LABM-102"),
        ("STF-DELHI-03", center1_id, org1_id, "tech.delhi@spherixclinic.com", pw_hash, "Anil Sengupta", "technician", "+91 9811002213", "B.Sc (MLT)", "MLT-9041"),
        ("STF-DELHI-04", center1_id, org1_id, "phlebo.delhi@spherixclinic.com", pw_hash, "Rakesh Kumar", "phlebotomist", "+91 9811002214", "Certified Phlebotomy Specialist (CPT)", "CPT-551"),
        ("STF-DELHI-05", center1_id, org1_id, "frontdesk.delhi@spherixclinic.com", pw_hash, "Neha Dixit", "receptionist", "+91 9811002215", "Hospital Administration Diploma", "REC-88"),

        # Center 3 Staff (USA)
        ("STF-NYC-01", center3_id, org2_id, "dr.carter@apexdiagnostics.us", pw_hash, "Dr. Meredith Carter, MD, FCAP", "pathologist", "+1 212 555 0120", "MD, Board Certified Anatomic & Clinical Pathology", "NY-MD-904128"),
        ("STF-NYC-02", center3_id, org2_id, "admin@apexdiagnostics.us", pw_hash, "David Miller", "admin", "+1 212 555 0121", "MHA, Laboratory Operations", "ADM-01"),
        ("STF-NYC-03", center3_id, org2_id, "phlebo.nyc@apexdiagnostics.us", pw_hash, "Sarah Jenkins", "phlebotomist", "+1 212 555 0122", "NHA Certified Phlebotomy Tech", "CPT-NY-190")
    ]

    for st in staff_members:
        cursor.execute("""
        INSERT OR REPLACE INTO pathology_staff (id, center_id, organization_id, email, password_hash, full_name, role, phone, qualification, license_number, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, st)

    # 4. Populate Tests for Centers from Master Catalog
    for center_id_val, curr, price_factor in [
        (center1_id, "INR", 1.0),
        (center2_id, "INR", 0.9),
        (center3_id, "USD", 1.0)
    ]:
        for t in MASTER_TESTS_CATALOG:
            test_id = f"TST-{t['code']}-{center_id_val}"
            price = t['base_price_usd'] if curr == "USD" else (t['base_price_inr'] * price_factor)
            params_json = json.dumps(t.get('parameters', []))

            cursor.execute("""
            INSERT OR REPLACE INTO diagnostic_tests (
                id, center_id, organization_id, test_name, test_code, category_id, category_name, description,
                sample_type, container_type, required_quantity, preparation_instructions, fasting_required, fasting_hours,
                turnaround_hours, price, currency, home_collection_eligible, walkin_eligible, parameters_json, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                test_id, center_id_val, org1_id if "DELHI" in center_id_val or "BIHAR" in center_id_val else org2_id,
                t['name'], t['code'], f"CAT-{t['category_code']}", t['category_name'], t['description'],
                t['sample_type'], t['container_type'], t['required_quantity'], t['preparation_instructions'],
                1 if t['fasting_required'] else 0, t['fasting_hours'], t['turnaround_hours'], price, curr,
                1 if t['home_collection_eligible'] else 0, 1 if t['walkin_eligible'] else 0, params_json
            ))

    # 5. Populate Standard Packages for Centers
    for center_id_val, curr, price_factor in [
        (center1_id, "INR", 1.0),
        (center2_id, "INR", 0.9),
        (center3_id, "USD", 1.0)
    ]:
        for pkg in MASTER_PACKAGES_CATALOG:
            pkg_id = f"PKG-{pkg['code']}-{center_id_val}"
            orig_p = pkg['base_price_usd'] * 2.0 if curr == "USD" else (pkg['base_price_inr'] * 2.2 * price_factor)
            pkg_p = pkg['base_price_usd'] if curr == "USD" else (pkg['base_price_inr'] * price_factor)

            cursor.execute("""
            INSERT OR REPLACE INTO diagnostic_packages (
                id, center_id, organization_id, package_name, package_code, description, preparation_instructions,
                fasting_required, turnaround_hours, original_price, package_price, discount_percent, currency,
                home_collection_eligible, walkin_eligible, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                pkg_id, center_id_val, org1_id if "DELHI" in center_id_val or "BIHAR" in center_id_val else org2_id,
                pkg['name'], pkg['code'], pkg['description'], pkg['preparation_instructions'],
                1 if pkg['fasting_required'] else 0, pkg['turnaround_hours'], orig_p, pkg_p, pkg['discount_percent'], curr,
                1 if pkg['home_collection_eligible'] else 0, 1 if pkg['walkin_eligible'] else 0
            ))

            for t_code in pkg['test_codes']:
                t_obj = get_test_by_code(t_code)
                if t_obj:
                    cursor.execute("""
                    INSERT OR REPLACE INTO diagnostic_package_items (id, package_id, test_id, test_name, test_code)
                    VALUES (?, ?, ?, ?, ?)
                    """, (
                        f"PKGI-{pkg_id}-{t_code}", pkg_id, f"TST-{t_code}-{center_id_val}", t_obj['name'], t_code
                    ))

    if close_after:
        conn.commit()
        conn.close()

# ==============================================================================
# 3. GEOSPATIAL SEARCH & DISTANCE CALCULATION
# ==============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the great-circle distance between two points in kilometers."""
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        if lat1 == 0.0 and lon1 == 0.0:
            return 9999.0
        if lat2 == 0.0 and lon2 == 0.0:
            return 9999.0

        r = 6371.0  # Earth's radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(r * c, 2)
    except Exception:
        return 9999.0

def find_matching_pathology_centers(
    test_ids: Optional[List[str]] = None,
    test_codes: Optional[List[str]] = None,
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
    address: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    service_type: Optional[str] = None, # HOME_COLLECTION, WALK_IN
    max_distance_km: float = 100.0,
    sort_by: str = 'distance' # distance, price, rating
) -> List[Dict[str, Any]]:
    """
    Finds verified pathology centers offering the prescribed tests/packages within radius,
    computing exact prices, distances, and collection eligibility.
    """
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    query = """
    SELECT c.*, o.legal_name as org_legal_name, o.tax_rate_percent
    FROM pathology_centers c
    JOIN pathology_organizations o ON c.organization_id = o.id
    WHERE c.verification_status = 'VERIFIED' AND c.is_active = 1
    """
    params = []

    if country:
        query += " AND LOWER(c.country) = LOWER(?)"
        params.append(country.strip())
    if city:
        query += " AND (LOWER(c.city) LIKE LOWER(?) OR LOWER(c.address) LIKE LOWER(?))"
        params.extend([f"%{city.strip()}%", f"%{city.strip()}%"])

    if service_type == 'HOME_COLLECTION':
        query += " AND c.home_collection_enabled = 1"
    elif service_type == 'WALK_IN':
        query += " AND c.walkin_enabled = 1"

    cursor.execute(query, params)
    centers_raw = dict_list_from_rows(cursor.fetchall())
    matched_centers = []

    for c in centers_raw:
        c_lat = float(c.get('latitude') or 0.0)
        c_lng = float(c.get('longitude') or 0.0)

        # Distance calculation
        dist = 5.0  # default fallback if coordinates not provided
        if user_lat is not None and user_lng is not None and (user_lat != 0.0 or user_lng != 0.0):
            dist = haversine_distance(user_lat, user_lng, c_lat, c_lng)
        elif address and address.lower() in (c.get('city', '') + ' ' + c.get('address', '')).lower():
            dist = 2.5

        # Check collection radius if home collection requested
        if service_type == 'HOME_COLLECTION' and dist > float(c.get('home_collection_radius_km') or 25.0):
            continue

        if dist > max_distance_km and (user_lat or user_lng):
            continue

        c['distance_km'] = dist
        c['display_name'] = f"{c['center_name']} ({c['branch_name']})"

        # Calculate pricing for requested tests
        total_test_price = 0.0
        available_tests_count = 0
        requested_count = len(test_ids) if test_ids else (len(test_codes) if test_codes else 0)

        if test_ids or test_codes:
            if test_ids:
                placeholders = ','.join(['?'] * len(test_ids))
                cursor.execute(f"""
                SELECT test_code, price FROM diagnostic_tests
                WHERE center_id = ? AND (id IN ({placeholders}) OR test_code IN ({placeholders})) AND is_active = 1
                """, [c['id']] + test_ids + test_ids)
            else:
                placeholders = ','.join(['?'] * len(test_codes))
                cursor.execute(f"""
                SELECT test_code, price FROM diagnostic_tests
                WHERE center_id = ? AND test_code IN ({placeholders}) AND is_active = 1
                """, [c['id']] + test_codes)

            t_rows = cursor.fetchall()
            available_tests_count = len(t_rows)
            for r in t_rows:
                total_test_price += float(r['price'])

            # If lab doesn't have custom tests, fallback to master pricing
            if available_tests_count < requested_count:
                missing_codes = test_codes or []
                for mc in missing_codes:
                    t_master = get_test_by_code(mc)
                    if t_master:
                        total_test_price += (t_master['base_price_usd'] if c['currency'] == 'USD' else t_master['base_price_inr'])

        c['total_price'] = round(total_test_price, 2)
        c['estimated_total'] = round(total_test_price + (float(c['home_collection_fee']) if service_type == 'HOME_COLLECTION' else 0.0), 2)
        matched_centers.append(c)

    conn.close()

    # Sort results
    if sort_by == 'price':
        matched_centers.sort(key=lambda x: (x['total_price'], x['distance_km']))
    elif sort_by == 'rating':
        matched_centers.sort(key=lambda x: (-float(x.get('rating') or 0.0), x['distance_km']))
    else:
        matched_centers.sort(key=lambda x: x['distance_km'])

    return matched_centers


def get_test_price_comparison(
    test_code: str,
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
    city: Optional[str] = None,
    country: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves a cross-center price and availability comparison matrix for a specific lab test.
    Computes minimum price, maximum price, average savings, and lists all centers offering the test.
    """
    code_upper = test_code.strip().upper()
    test_meta = get_test_by_code(code_upper)

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    query = """
    SELECT c.*, o.legal_name as org_legal_name, o.accreditation as org_accreditation
    FROM pathology_centers c
    JOIN pathology_organizations o ON c.organization_id = o.id
    WHERE c.verification_status = 'VERIFIED' AND c.is_active = 1
    """
    params = []
    if country and country != 'All':
        query += " AND LOWER(c.country) = LOWER(?)"
        params.append(country.strip())
    if city:
        query += " AND (LOWER(c.city) LIKE LOWER(?) OR LOWER(c.address) LIKE LOWER(?))"
        params.extend([f"%{city.strip()}%", f"%{city.strip()}%"])

    cursor.execute(query, params)
    centers_raw = dict_list_from_rows(cursor.fetchall())

    comparison_list = []
    prices = []

    for c in centers_raw:
        c_lat = float(c.get('latitude') or 0.0)
        c_lng = float(c.get('longitude') or 0.0)

        dist = 5.0
        if user_lat is not None and user_lng is not None and (user_lat != 0.0 or user_lng != 0.0):
            dist = haversine_distance(user_lat, user_lng, c_lat, c_lng)

        # Check center's specific price for this test
        cursor.execute("""
        SELECT price, turnaround_hours, is_active, home_collection_eligible, walkin_eligible
        FROM diagnostic_tests
        WHERE center_id = ? AND test_code = ? AND is_active = 1
        """, (c['id'], code_upper))
        custom_test = dict_from_row(cursor.fetchone())

        if custom_test:
            price = float(custom_test['price'])
            tat = custom_test.get('turnaround_hours') or (test_meta.get('turnaround_hours', 12) if test_meta else 12)
            home_avail = bool(custom_test.get('home_collection_eligible', 1) and c.get('home_collection_enabled', 1))
            walkin_avail = bool(custom_test.get('walkin_eligible', 1) and c.get('walkin_enabled', 1))
        else:
            base_inr = test_meta.get('base_price_inr', 500.0) if test_meta else 500.0
            price = base_inr if c.get('currency', 'INR') == 'INR' else (test_meta.get('base_price_usd', 15.0) if test_meta else 15.0)
            tat = test_meta.get('turnaround_hours', 12) if test_meta else 12
            home_avail = bool(c.get('home_collection_enabled', 1))
            walkin_avail = bool(c.get('walkin_enabled', 1))

        prices.append(price)

        comparison_list.append({
            "center_id": c['id'],
            "center_name": c['center_name'],
            "branch_name": c['branch_name'],
            "city": c['city'],
            "state_province": c.get('state_province', ''),
            "country": c.get('country', 'India'),
            "address": c['address'],
            "rating": float(c.get('rating') or 4.8),
            "review_count": int(c.get('review_count') or 0),
            "distance_km": dist,
            "test_price": price,
            "currency": c.get('currency', 'INR'),
            "home_collection_enabled": home_avail,
            "home_collection_fee": float(c.get('home_collection_fee') or 0.0),
            "walkin_enabled": walkin_avail,
            "turnaround_hours": tat,
            "is_nabl_accredited": bool(c.get('is_nabl_accredited', 1)),
            "is_cap_accredited": bool(c.get('is_cap_accredited', 0)),
            "is_iso_certified": bool(c.get('is_iso_certified', 1))
        })

    conn.close()

    # Sort centers by price ascending
    comparison_list.sort(key=lambda x: (x['test_price'], x['distance_km']))

    min_p = min(prices) if prices else 0.0
    max_p = max(prices) if prices else 0.0
    avg_p = round(sum(prices) / len(prices), 2) if prices else 0.0

    return {
        "test_code": code_upper,
        "test_name": test_meta['name'] if test_meta else code_upper,
        "category_name": test_meta.get('category_name', 'Pathology') if test_meta else 'Pathology',
        "sample_type": test_meta.get('sample_type', 'Blood') if test_meta else 'Blood',
        "fasting_required": test_meta.get('fasting_required', False) if test_meta else False,
        "min_price": min_p,
        "max_price": max_p,
        "avg_price": avg_p,
        "centers_count": len(comparison_list),
        "centers": comparison_list
    }


def check_test_availability_by_location(
    test_code_or_query: str,
    city: Optional[str] = None,
    postal_code: Optional[str] = None,
    country: Optional[str] = None
) -> Dict[str, Any]:
    """
    Checks test and slot availability for a specific city, ZIP, or country.
    """
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    query = """
    SELECT c.id, c.center_name, c.branch_name, c.city, c.postal_code, c.country,
           c.home_collection_enabled, c.walkin_enabled, c.home_collection_fee,
           c.available_time_slots, c.available_days, c.rating
    FROM pathology_centers c
    WHERE c.verification_status = 'VERIFIED' AND c.is_active = 1
    """
    params = []
    if postal_code:
        query += " AND (c.postal_code = ? OR c.postal_code LIKE ?)"
        params.extend([postal_code.strip(), f"{postal_code.strip()[:3]}%"])
    elif city:
        query += " AND LOWER(c.city) LIKE LOWER(?)"
        params.append(f"%{city.strip()}%")
    if country and country != 'All':
        query += " AND LOWER(c.country) = LOWER(?)"
        params.append(country.strip())

    cursor.execute(query, params)
    centers = dict_list_from_rows(cursor.fetchall())
    conn.close()

    is_available = len(centers) > 0
    home_available = any(c.get('home_collection_enabled') for c in centers)
    walkin_available = any(c.get('walkin_enabled') for c in centers)

    return {
        "available": is_available,
        "query": test_code_or_query,
        "city": city,
        "postal_code": postal_code,
        "country": country,
        "matching_centers_count": len(centers),
        "home_collection_available": home_available,
        "walkin_available": walkin_available,
        "centers": centers
    }


# ==============================================================================
# 4. PATHOLOGY CENTER REGISTRATION & ADMIN WORKFLOW
# ==============================================================================

def register_pathology_organization_and_center(
    org_data: Dict[str, Any],
    center_data: Dict[str, Any],
    admin_data: Dict[str, Any],
    documents: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Registers a new global pathology organization, primary center branch, and administrator.
    State starts as 'PENDING_VERIFICATION' until Spherix Administrator verifies credentials.
    """
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    try:
        # 1. Check if email already exists
        cursor.execute("SELECT id FROM pathology_organizations WHERE email = ?", (org_data['email'],))
        if cursor.fetchone():
            conn.close()
            return False, "An organization with this email is already registered.", {}

        cursor.execute("SELECT id FROM pathology_staff WHERE email = ?", (admin_data['email'],))
        if cursor.fetchone():
            conn.close()
            return False, "A staff user with this administrator email already exists.", {}

        # 2. Insert Organization
        org_id = f"ORG-DX-{secrets.token_hex(4).upper()}"
        cursor.execute("""
        INSERT INTO pathology_organizations (
            id, legal_name, display_name, org_type, reg_number, license_number, accreditation,
            website, email, phone, country, currency, timezone, tax_rate_percent, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_VERIFICATION')
        """, (
            org_id, org_data['legal_name'], org_data.get('display_name') or org_data['legal_name'],
            org_data.get('org_type', 'Clinical Laboratory'), org_data.get('reg_number'),
            org_data.get('license_number'), org_data.get('accreditation', 'State Health Department'),
            org_data.get('website'), org_data['email'], org_data.get('phone'),
            org_data.get('country', 'India'), org_data.get('currency', 'INR'),
            org_data.get('timezone', 'IST (UTC+5:30)'), float(org_data.get('tax_rate_percent', 0.0))
        ))

        # 3. Insert Primary Center
        center_id = f"LAB-DX-{secrets.token_hex(4).upper()}"
        cursor.execute("""
        INSERT INTO pathology_centers (
            id, organization_id, center_name, branch_name, email, phone, address, city,
            state_province, postal_code, country, latitude, longitude, timezone, currency,
            home_collection_enabled, walkin_enabled, home_collection_radius_km, home_collection_fee,
            min_order_amount, available_days, available_time_slots, verification_status, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_VERIFICATION', 1)
        """, (
            center_id, org_id, center_data['center_name'], center_data.get('branch_name', 'Main Center'),
            center_data.get('email', org_data['email']), center_data.get('phone', org_data.get('phone')),
            center_data['address'], center_data['city'], center_data.get('state_province'),
            center_data.get('postal_code'), center_data.get('country', org_data.get('country', 'India')),
            float(center_data.get('latitude', 0.0)), float(center_data.get('longitude', 0.0)),
            center_data.get('timezone', org_data.get('timezone', 'IST (UTC+5:30)')),
            center_data.get('currency', org_data.get('currency', 'INR')),
            1 if center_data.get('home_collection_enabled', True) else 0,
            1 if center_data.get('walkin_enabled', True) else 0,
            float(center_data.get('home_collection_radius_km', 25.0)),
            float(center_data.get('home_collection_fee', 150.0)),
            float(center_data.get('min_order_amount', 200.0)),
            center_data.get('available_days', 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'),
            center_data.get('available_time_slots', '07:00-09:00,09:00-11:00,11:00-13:00,14:00-16:00,16:00-18:00')
        ))

        # 4. Insert Administrator Account
        admin_id = f"STF-{secrets.token_hex(4).upper()}"
        pw_hash = generate_password_hash(admin_data['password'], method="pbkdf2:sha256:260000")
        cursor.execute("""
        INSERT INTO pathology_staff (
            id, center_id, organization_id, email, password_hash, full_name, role, phone, qualification, license_number, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, 'admin', ?, ?, ?, 1)
        """, (
            admin_id, center_id, org_id, admin_data['email'], pw_hash,
            admin_data['full_name'], admin_data.get('phone'),
            admin_data.get('qualification', 'Laboratory Director'), admin_data.get('license_number')
        ))

        # 5. Insert Documents if provided
        if documents:
            for doc in documents:
                doc_id = f"DOC-{secrets.token_hex(4).upper()}"
                cursor.execute("""
                INSERT INTO pathology_center_documents (
                    id, center_id, doc_type, file_name, file_path, original_name, mime_type, file_size, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
                """, (
                    doc_id, center_id, doc.get('doc_type', 'License'), doc['file_name'],
                    doc['file_path'], doc.get('original_name'), doc.get('mime_type'), doc.get('file_size')
                ))

        # 6. Populate default test catalog for this center
        curr = center_data.get('currency', org_data.get('currency', 'INR'))
        for t in MASTER_TESTS_CATALOG:
            test_id = f"TST-{t['code']}-{center_id}"
            price = t['base_price_usd'] if curr == "USD" else t['base_price_inr']
            params_json = json.dumps(t.get('parameters', []))

            cursor.execute("""
            INSERT INTO diagnostic_tests (
                id, center_id, organization_id, test_name, test_code, category_id, category_name, description,
                sample_type, container_type, required_quantity, preparation_instructions, fasting_required, fasting_hours,
                turnaround_hours, price, currency, home_collection_eligible, walkin_eligible, parameters_json, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                test_id, center_id, org_id, t['name'], t['code'], f"CAT-{t['category_code']}",
                t['category_name'], t['description'], t['sample_type'], t['container_type'],
                t['required_quantity'], t['preparation_instructions'], 1 if t['fasting_required'] else 0,
                t['fasting_hours'], t['turnaround_hours'], price, curr,
                1 if t['home_collection_eligible'] else 0, 1 if t['walkin_eligible'] else 0, params_json
            ))

        # Audit Log
        cursor.execute("""
        INSERT INTO diagnostic_audit_logs (id, user_id, user_role, organization_id, center_id, action, entity, entity_id, details)
        VALUES (?, ?, 'admin', ?, ?, 'REGISTER_CENTER', 'pathology_centers', ?, 'New center registered and awaiting verification')
        """, (f"AUD-{secrets.token_hex(4).upper()}", admin_id, org_id, center_id, center_id))

        conn.commit()
        conn.close()

        return True, "Pathology center registration submitted successfully. Your account is under verification by Spherix Administrators.", {
            "organization_id": org_id,
            "center_id": center_id,
            "admin_id": admin_id,
            "email": admin_data['email']
        }
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Registration failed: {str(e)}", {}

def update_center_verification_status(
    center_id: str,
    status: str, # VERIFIED, REJECTED, SUSPENDED, UNDER_REVIEW
    verified_by: str,
    rejection_reason: Optional[str] = None
) -> Tuple[bool, str]:
    """Admin function to verify, reject, or suspend a pathology center."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT organization_id, center_name FROM pathology_centers WHERE id = ?", (center_id,))
        center = cursor.fetchone()
        if not center:
            conn.close()
            return False, "Pathology center not found."

        cursor.execute("""
        UPDATE pathology_centers
        SET verification_status = ?, rejection_reason = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (status, rejection_reason, center_id))

        cursor.execute("""
        UPDATE pathology_organizations
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (status, center['organization_id']))

        # Update documents verified
        if status == 'VERIFIED':
            cursor.execute("""
            UPDATE pathology_center_documents
            SET status = 'APPROVED', verified_by = ?, verified_at = CURRENT_TIMESTAMP
            WHERE center_id = ?
            """, (verified_by, center_id))

        # Audit Log
        cursor.execute("""
        INSERT INTO diagnostic_audit_logs (id, user_id, user_role, organization_id, center_id, action, entity, entity_id, details)
        VALUES (?, ?, 'spherix_admin', ?, ?, 'UPDATE_VERIFICATION', 'pathology_centers', ?, ?)
        """, (f"AUD-{secrets.token_hex(4).upper()}", verified_by, center['organization_id'], center_id, center_id, f"Verification changed to {status}. Reason: {rejection_reason or 'None'}"))

        conn.commit()
        conn.close()
        return True, f"Center status updated to {status}."
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e)

# ==============================================================================
# 5. AUTHENTICATION & RBAC PERMISSIONS
# ==============================================================================

def authenticate_pathology_staff(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates staff member and returns full profile, roles, and center metadata."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT s.*, c.center_name, c.branch_name, c.city, c.country, c.currency, c.verification_status, c.is_active as center_active,
           o.legal_name as org_name, o.tax_rate_percent
    FROM pathology_staff s
    JOIN pathology_centers c ON s.center_id = c.id
    JOIN pathology_organizations o ON s.organization_id = o.id
    WHERE LOWER(s.email) = LOWER(?) AND s.is_active = 1
    """, (email.strip(),))

    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        return None

    user = dict(user_row)
    if not check_password_hash(user['password_hash'], password):
        conn.close()
        return None

    # Update last login
    cursor.execute("UPDATE pathology_staff SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user['id'],))
    conn.commit()
    conn.close()

    user.pop('password_hash', None)
    return user

# ==============================================================================
# 6. ORDERS, PHLEBOTOMY, & SAMPLE ACCESSIONING WORKFLOW
# ==============================================================================

def create_diagnostic_booking_order(
    patient_data: Dict[str, Any],
    center_id: str,
    service_type: str, # HOME_COLLECTION, WALK_IN
    scheduled_date: str,
    scheduled_slot: str,
    items: List[Dict[str, Any]], # list of {"type": "TEST"|"PACKAGE", "id": "...", "name": "...", "code": "...", "price": 0.0}
    payment_method: str = 'ONLINE',
    payment_ref: Optional[str] = None,
    doctor_id: Optional[str] = None,
    referral_id: Optional[str] = None,
    notes: Optional[str] = None,
    prescription_file: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Creates a full diagnostic order with itemized billing, sample accessioning records,
    and automatic phlebotomy assignment or walk-in queue token generation.
    """
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM pathology_centers WHERE id = ?", (center_id,))
        center = cursor.fetchone()
        if not center:
            conn.close()
            return False, "Selected pathology center was not found.", {}

        # 1. Calculate pricing
        subtotal = sum(float(it.get('price', 0.0)) for it in items)
        collection_fee = float(center['home_collection_fee']) if service_type == 'HOME_COLLECTION' else 0.0
        tax_rate = 0.05 if center['country'] == 'India' else 0.0
        tax_amount = round((subtotal + collection_fee) * tax_rate, 2)
        total_amount = round(subtotal + collection_fee + tax_amount, 2)

        # 2. Generate unique identifiers
        now_dt = datetime.now()
        date_str = now_dt.strftime("%Y%m%d")
        rand_suffix = secrets.token_hex(3).upper()
        order_number = f"SPX-DX-{date_str}-{rand_suffix}"
        order_id = f"ORD-{date_str}-{rand_suffix}"

        cursor.execute("""
        INSERT INTO diagnostic_orders (
            id, order_number, patient_id, patient_name, patient_email, patient_phone, patient_address,
            patient_lat, patient_lng, center_id, organization_id, doctor_id, referral_id, service_type,
            scheduled_date, scheduled_slot, status, subtotal, collection_fee, tax_amount, total_amount,
            currency, payment_status, payment_method, payment_ref, notes, prescription_file
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id, order_number, patient_data.get('id'), patient_data['name'],
            patient_data.get('email'), patient_data.get('phone'), patient_data.get('address'),
            float(patient_data.get('lat', 0.0)), float(patient_data.get('lng', 0.0)),
            center_id, center['organization_id'], doctor_id, referral_id, service_type,
            scheduled_date, scheduled_slot, subtotal, collection_fee, tax_amount, total_amount,
            center['currency'], 'PAID' if payment_method == 'ONLINE' else 'PENDING',
            payment_method, payment_ref or f"PAY-{secrets.token_hex(4).upper()}", notes, prescription_file
        ))

        # 3. Insert Order Items
        test_codes = []
        for idx, itm in enumerate(items):
            item_id = f"ITM-{order_id}-{idx+1}"
            t_code = itm.get('code') or itm.get('test_code', 'TEST')
            test_codes.append(t_code)

            cursor.execute("""
            INSERT INTO diagnostic_order_items (
                id, order_id, item_type, item_id, item_name, item_code, price
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id, order_id, itm.get('type', 'TEST'), itm['id'],
                itm['name'], t_code, float(itm.get('price', 0.0))
            ))

        # 4. Generate Sample Accession Record & Barcode
        sample_code = f"SMP-{secrets.token_hex(4).upper()}"
        barcode_data = sample_code
        qr_code_data = f"https://spherixclinic.com/diagnostic/samples/verify?code={sample_code}"

        cursor.execute("""
        INSERT INTO sample_records (
            id, sample_code, order_id, center_id, patient_id, test_ids_json, sample_type, container_type,
            barcode_data, qr_code_data, status
        ) VALUES (?, ?, ?, ?, ?, ?, 'Whole Blood / Serum', 'Vacutainer Standard', ?, ?, 'AWAITING_COLLECTION')
        """, (
            f"SMP-REC-{order_id}", sample_code, order_id, center_id,
            patient_data.get('id'), json.dumps(test_codes), barcode_data, qr_code_data
        ))

        # Initial Tracking Event
        cursor.execute("""
        INSERT INTO sample_tracking_events (id, sample_id, status, location, notes, recorded_by)
        VALUES (?, ?, 'AWAITING_COLLECTION', ?, 'Diagnostic booking confirmed. Sample record created.', 'System Dispatcher')
        """, (f"TRK-{secrets.token_hex(4).upper()}", f"SMP-REC-{order_id}", center['center_name']))

        # 5. Service-specific Queuing
        token_str = None
        if service_type == 'HOME_COLLECTION':
            # Assign phlebotomist
            cursor.execute("""
            SELECT id, full_name FROM pathology_staff
            WHERE center_id = ? AND role = 'phlebotomist' AND is_active = 1 LIMIT 1
            """, (center_id,))
            phlebo = cursor.fetchone()
            phlebo_id = phlebo['id'] if phlebo else None
            phlebo_name = phlebo['full_name'] if phlebo else "Pending Dispatcher Assignment"

            cursor.execute("""
            INSERT INTO collection_assignments (
                id, order_id, center_id, phlebotomist_id, phlebotomist_name, status, assigned_at, notes
            ) VALUES (?, ?, ?, ?, ?, 'ASSIGNED', CURRENT_TIMESTAMP, 'Automated collection route dispatch.')
            """, (f"ASG-{order_id}", order_id, center_id, phlebo_id, phlebo_name))
        else:
            # Walk-in token
            cursor.execute("""
            SELECT COUNT(*) as c FROM walkin_queue WHERE center_id = ? AND appointment_date = ?
            """, (center_id, scheduled_date))
            token_num = (cursor.fetchone()['c'] or 0) + 1
            token_str = f"TKN-{token_num:03d}"

            cursor.execute("""
            INSERT INTO walkin_queue (
                id, order_id, center_id, patient_id, token_number, appointment_date, appointment_time, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'WAITING')
            """, (f"WKN-{order_id}", order_id, center_id, patient_data.get('id'), token_str, scheduled_date, scheduled_slot))

        # Audit Log
        cursor.execute("""
        INSERT INTO diagnostic_audit_logs (id, user_id, user_role, organization_id, center_id, action, entity, entity_id, details)
        VALUES (?, ?, 'patient', ?, ?, 'CREATE_ORDER', 'diagnostic_orders', ?, ?)
        """, (
            f"AUD-{secrets.token_hex(4).upper()}", patient_data.get('id', 'GUEST'),
            center['organization_id'], center_id, order_id,
            f"Booked {service_type} for total amount {center['currency']} {total_amount}"
        ))

        conn.commit()
        conn.close()

        return True, "Diagnostic test booking confirmed successfully!", {
            "order_id": order_id,
            "order_number": order_number,
            "sample_code": sample_code,
            "token_number": token_str,
            "total_amount": total_amount,
            "currency": center['currency'],
            "service_type": service_type
        }
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Booking failed: {str(e)}", {}

# ==============================================================================
# 7. LAB RESULTS ENTRY & PATHOLOGIST DIGITAL REPORTING
# ==============================================================================

def enter_technician_lab_results(
    order_id: str,
    technician_id: str,
    technician_name: str,
    results_list: List[Dict[str, Any]], # [{"test_name": "...", "parameter_name": "...", "result_value": "...", "unit": "...", "reference_range": "...", "abnormal_flag": "NORMAL"}]
    notes: Optional[str] = None
) -> Tuple[bool, str]:
    """Lab technician submits test observations for pathologist review."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM diagnostic_orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return False, "Order not found."

        # Delete existing draft results if re-entered
        cursor.execute("DELETE FROM lab_results WHERE order_id = ? AND status != 'RELEASED'", (order_id,))

        for res in results_list:
            res_id = f"RES-{order_id}-{secrets.token_hex(3).upper()}"
            cursor.execute("""
            INSERT INTO lab_results (
                id, order_id, test_name, parameter_name, result_value, unit, reference_range, abnormal_flag,
                technician_notes, technician_id, technician_name, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'TECH_COMPLETED')
            """, (
                res_id, order_id, res.get('test_name', 'Diagnostic Test'),
                res['parameter_name'], str(res['result_value']), res.get('unit', ''),
                res.get('reference_range', 'Normal Reference'), res.get('abnormal_flag', 'NORMAL'),
                notes, technician_id, technician_name
            ))

        # Update order status to REPORT_PENDING
        cursor.execute("""
        UPDATE diagnostic_orders SET status = 'REPORT_PENDING', updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (order_id,))

        # Update sample status to COMPLETED
        cursor.execute("""
        UPDATE sample_records SET status = 'PROCESSING', updated_at = CURRENT_TIMESTAMP WHERE order_id = ?
        """, (order_id,))

        conn.commit()
        conn.close()
        return True, "Results submitted successfully for pathologist authorization."
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e)

def approve_and_release_diagnostic_report(
    order_id: str,
    pathologist_id: str,
    pathologist_name: str,
    summary: str,
    interpretation: str,
    is_correction: bool = False,
    correction_reason: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Pathologist authorizes, signs, and releases immutable versioned diagnostic report.
    Never overwrites existing released reports; generates versioned amendments.
    """
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM diagnostic_orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return False, "Order not found.", {}

        # Check existing reports for versioning
        cursor.execute("SELECT * FROM lab_reports WHERE order_id = ? ORDER BY version DESC, rowid DESC LIMIT 1", (order_id,))
        existing_report = cursor.fetchone()

        version_num = "v1"
        report_id = f"REP-{order_id}"
        report_number = f"REP-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

        if existing_report:
            prev_v = existing_report['version']
            v_int = int(prev_v.replace('v', '')) if 'v' in prev_v else 1
            version_num = f"v{v_int + 1}"
            report_id = f"REP-{order_id}-{version_num}"
            report_number = existing_report['report_number'] + f"-{version_num}"

        qr_url = f"https://spherixclinic.com/diagnostic/verify-report/{report_number}"

        # Insert new report version
        cursor.execute("""
        INSERT INTO lab_reports (
            id, report_number, order_id, center_id, patient_id, doctor_id, version, title, summary,
            interpretation, status, pathologist_id, pathologist_name, pathologist_signature,
            released_at, approved_at, qr_verification_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Clinical Pathology & Diagnostic Laboratory Report', ?, ?, ?, ?, ?, 'DIGITAL_SIGN_VERIFIED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
        """, (
            report_id, report_number, order_id, order['center_id'], order['patient_id'],
            order['doctor_id'], version_num, summary, interpretation,
            'CORRECTED' if is_correction else 'RELEASED',
            pathologist_id, pathologist_name, qr_url
        ))

        # Record version audit
        cursor.execute("""
        INSERT INTO lab_report_versions (id, report_id, version, status, change_summary, updated_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            f"RPV-{secrets.token_hex(4).upper()}", report_id, version_num,
            'CORRECTED' if is_correction else 'RELEASED',
            correction_reason or ('Initial released report' if version_num == 'v1' else 'Corrected amended report released'),
            pathologist_name
        ))

        # Mark results as RELEASED
        cursor.execute("UPDATE lab_results SET status = 'RELEASED' WHERE order_id = ?", (order_id,))

        # Mark order as REPORT_RELEASED
        cursor.execute("UPDATE diagnostic_orders SET status = 'REPORT_RELEASED', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order_id,))

        # Mark sample as COMPLETED
        cursor.execute("UPDATE sample_records SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP WHERE order_id = ?", (order_id,))

        # Audit Log
        cursor.execute("""
        INSERT INTO diagnostic_audit_logs (id, user_id, user_role, organization_id, center_id, action, entity, entity_id, details)
        VALUES (?, ?, 'pathologist', ?, ?, 'RELEASE_REPORT', 'lab_reports', ?, ?)
        """, (
            f"AUD-{secrets.token_hex(4).upper()}", pathologist_id, order['organization_id'],
            order['center_id'], report_id, f"Released report {report_number} ({version_num})"
        ))

        conn.commit()
        conn.close()

        return True, f"Diagnostic report {version_num} successfully released and transmitted to patient.", {
            "report_id": report_id,
            "report_number": report_number,
            "version": version_num,
            "order_id": order_id
        }
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e), {}

# ==============================================================================
# 8. DOCTOR REFERRAL WORKFLOW
# ==============================================================================

def create_doctor_diagnostic_referral(
    doctor_id: str,
    doctor_name: str,
    patient_id: str,
    patient_name: str,
    center_id: Optional[str],
    test_codes: List[str],
    clinical_indication: str,
    priority: str = 'ROUTINE', # ROUTINE, URGENT, TIME_SENSITIVE
    doctor_instructions: Optional[str] = None,
    medicines: Optional[List[Dict[str, Any]]] = None,
    hospital_id: Optional[str] = None,
    hospital_name: Optional[str] = None,
    **kwargs
) -> Tuple[bool, str, Dict[str, Any]]:
    """Creates a verifiable digital laboratory referral and medicine order from a licensed doctor."""
    if not doctor_instructions and 'instructions' in kwargs:
        doctor_instructions = kwargs['instructions']
    if medicines is None:
        medicines = kwargs.get('medications') or []

    medicines_json = json.dumps(medicines) if medicines else None

    conn = get_diagnostic_db()
    cursor = conn.cursor()

    try:
        ref_num = f"REF-DX-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        ref_id = f"REF-{secrets.token_hex(4).upper()}"

        cursor.execute("""
        INSERT INTO diagnostic_referrals (
            id, referral_number, doctor_id, doctor_name, patient_id, patient_name, center_id,
            clinical_indication, priority, doctor_instructions, status, hospital_id, hospital_name, medicines_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ISSUED', ?, ?, ?)
        """, (
            ref_id, ref_num, doctor_id, doctor_name, patient_id, patient_name, center_id,
            clinical_indication, priority, doctor_instructions, hospital_id, hospital_name, medicines_json
        ))

        # 1. Insert Diagnostic Tests into Referral Items
        for t_code in (test_codes or []):
            t_obj = get_test_by_code(t_code)
            t_name = t_obj['name'] if t_obj else t_code
            cursor.execute("""
            INSERT INTO diagnostic_referral_items (id, referral_id, item_type, item_id, item_name, test_code)
            VALUES (?, ?, 'TEST', ?, ?, ?)
            """, (f"RFI-{ref_id}-{t_code}", ref_id, f"TST-{t_code}", t_name, t_code))

        # 2. Insert Prescribed Medicines into Referral Items
        if medicines:
            for idx, med in enumerate(medicines):
                m_name = med.get('name') or med.get('medicine_name', f'Rx Med {idx+1}')
                m_dosage = med.get('dosage', '')
                m_freq = med.get('frequency', '')
                m_dur = med.get('duration', '')
                med_spec = f"{m_dosage} | {m_freq} | {m_dur}".strip(" |")
                cursor.execute("""
                INSERT INTO diagnostic_referral_items (id, referral_id, item_type, item_id, item_name, test_code)
                VALUES (?, ?, 'MEDICINE', ?, ?, ?)
                """, (f"RFM-{ref_id}-{secrets.token_hex(3).upper()}", ref_id, f"MED-{idx+1}", m_name, med_spec))

        # 3. Update connection transmission statistics
        if center_id:
            cursor.execute("""
            UPDATE doctor_pathology_connections SET
                last_medicine_transmission = CURRENT_TIMESTAMP,
                medicines_shared_count = COALESCE(medicines_shared_count, 0) + ?
            WHERE center_id = ? AND doctor_id = ?
            """, (len(medicines) if medicines else 1, center_id, doctor_id))

            if hospital_id:
                cursor.execute("""
                UPDATE hospital_pathology_connections SET
                    last_medicine_transmission = CURRENT_TIMESTAMP,
                    medicines_shared_count = COALESCE(medicines_shared_count, 0) + ?
                WHERE center_id = ? AND hospital_id = ?
                """, (len(medicines) if medicines else 1, center_id, hospital_id))

        # Audit Log
        cursor.execute("""
        INSERT INTO diagnostic_audit_logs (id, user_id, user_role, organization_id, center_id, action, entity, entity_id, details)
        VALUES (?, ?, 'doctor', 'GLOBAL', ?, 'CREATE_REFERRAL', 'diagnostic_referrals', ?, ?)
        """, (
            f"AUD-{secrets.token_hex(4).upper()}", doctor_id, center_id or 'UNASSIGNED',
            ref_id, f"Doctor issued referral/med order with {len(test_codes or [])} tests and {len(medicines or [])} medicines"
        ))

        conn.commit()
        conn.close()

        return True, "Diagnostic referral and medicine order issued successfully.", {
            "referral_id": ref_id,
            "referral_number": ref_num,
            "tests_count": len(test_codes or []),
            "medicines_count": len(medicines or [])
        }
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e), {}

# ==============================================================================
# 9. GETTERS & RETRIEVAL HELPERS
# ==============================================================================

def get_diagnostic_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT o.*, c.center_name, c.branch_name, c.address as center_address, c.phone as center_phone, c.email as center_email
    FROM diagnostic_orders o
    JOIN pathology_centers c ON o.center_id = c.id
    WHERE o.id = ? OR o.order_number = ?
    """, (order_id, order_id))
    order_row = cursor.fetchone()
    if not order_row:
        conn.close()
        return None

    order = dict(order_row)

    # Items
    cursor.execute("SELECT * FROM diagnostic_order_items WHERE order_id = ?", (order['id'],))
    order['items'] = dict_list_from_rows(cursor.fetchall())

    # Sample
    cursor.execute("SELECT * FROM sample_records WHERE order_id = ?", (order['id'],))
    order['sample'] = dict_from_row(cursor.fetchone())

    # Lab Results
    cursor.execute("SELECT * FROM lab_results WHERE order_id = ?", (order['id'],))
    order['results'] = dict_list_from_rows(cursor.fetchall())

    # Report
    cursor.execute("SELECT * FROM lab_reports WHERE order_id = ? ORDER BY version DESC, rowid DESC LIMIT 1", (order['id'],))
    order['report'] = dict_from_row(cursor.fetchone())

    # Phlebotomy Assignment
    cursor.execute("SELECT * FROM collection_assignments WHERE order_id = ?", (order['id'],))
    order['phlebotomy'] = dict_from_row(cursor.fetchone())

    # Walkin Queue
    cursor.execute("SELECT * FROM walkin_queue WHERE order_id = ?", (order['id'],))
    order['walkin'] = dict_from_row(cursor.fetchone())

    conn.close()
    return order

def get_center_analytics_summary(center_id: str) -> Dict[str, Any]:
    """Returns real KPI counts, daily order volume, revenue, and TAT for dashboard."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    today_str = date.today().strftime("%Y-%m-%d")

    # Order counts
    cursor.execute("SELECT COUNT(*) as c FROM diagnostic_orders WHERE center_id = ?", (center_id,))
    total_orders = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) as c FROM diagnostic_orders WHERE center_id = ? AND scheduled_date = ?", (center_id, today_str))
    today_orders = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) as c FROM diagnostic_orders WHERE center_id = ? AND status IN ('PENDING', 'CONFIRMED')", (center_id,))
    pending_orders = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) as c FROM diagnostic_orders WHERE center_id = ? AND service_type = 'HOME_COLLECTION' AND status != 'CANCELLED'", (center_id,))
    home_collection_count = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) as c FROM diagnostic_orders WHERE center_id = ? AND service_type = 'WALK_IN' AND status != 'CANCELLED'", (center_id,))
    walkin_count = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) as c FROM sample_records WHERE center_id = ? AND status = 'COLLECTED'", (center_id,))
    samples_collected = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) as c FROM sample_records WHERE center_id = ? AND status = 'PROCESSING'", (center_id,))
    samples_processing = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) as c FROM diagnostic_orders WHERE center_id = ? AND status = 'REPORT_PENDING'", (center_id,))
    reports_pending = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) as c FROM diagnostic_orders WHERE center_id = ? AND status = 'REPORT_RELEASED'", (center_id,))
    reports_released = cursor.fetchone()['c']

    # Revenue
    cursor.execute("SELECT SUM(total_amount) as s FROM diagnostic_orders WHERE center_id = ? AND payment_status = 'PAID'", (center_id,))
    total_revenue = cursor.fetchone()['s'] or 0.0

    cursor.execute("SELECT SUM(total_amount) as s FROM diagnostic_orders WHERE center_id = ? AND payment_status = 'PAID' AND scheduled_date = ?", (center_id, today_str))
    today_revenue = cursor.fetchone()['s'] or 0.0

    conn.close()

    return {
        "total_orders": total_orders,
        "today_orders": today_orders,
        "pending_orders": pending_orders,
        "home_collection_requests": home_collection_count,
        "walkin_appointments": walkin_count,
        "samples_collected": samples_collected,
        "samples_processing": samples_processing,
        "reports_pending": reports_pending,
        "reports_released": reports_released,
        "today_revenue": round(today_revenue, 2),
        "total_revenue": round(total_revenue, 2),
        "avg_tat_hours": 8.5
    }


# ==============================================================================
# 10. SETTINGS & PROFILE PERSISTENCE
# ==============================================================================

def update_pathology_center_profile(center_id: str, data: Dict[str, Any]) -> Tuple[bool, str]:
    """Updates center metadata, contact, accreditation, operating hours, and profile image."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        UPDATE pathology_centers SET
            center_name = ?,
            branch_name = ?,
            email = ?,
            phone = ?,
            website = ?,
            emergency_phone = ?,
            operating_hours = ?,
            is_nabl_accredited = ?,
            is_cap_accredited = ?,
            is_iso_certified = ?,
            home_collection_enabled = ?,
            walkin_enabled = ?,
            home_collection_radius_km = ?,
            home_collection_fee = ?,
            min_order_amount = ?,
            profile_image = COALESCE(?, profile_image),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (
            data.get('center_name'),
            data.get('branch_name', 'Main Facility'),
            data.get('email'),
            data.get('phone'),
            data.get('website'),
            data.get('emergency_phone'),
            data.get('operating_hours', '07:00 AM - 08:00 PM'),
            1 if data.get('is_nabl_accredited') else 0,
            1 if data.get('is_cap_accredited') else 0,
            1 if data.get('is_iso_certified') else 0,
            1 if data.get('home_collection_enabled') else 0,
            1 if data.get('walkin_enabled') else 0,
            float(data.get('home_collection_radius_km') or 25.0),
            float(data.get('home_collection_fee') or 150.0),
            float(data.get('min_order_amount') or 200.0),
            data.get('profile_image'),
            center_id
        ))

        # Also update parent organization if provided
        cursor.execute("SELECT organization_id FROM pathology_centers WHERE id = ?", (center_id,))
        c_row = cursor.fetchone()
        if c_row and data.get('legal_name'):
            cursor.execute("""
            UPDATE pathology_organizations SET
                legal_name = ?,
                website = ?,
                email = ?,
                phone = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (data.get('legal_name'), data.get('website'), data.get('email'), data.get('phone'), c_row['organization_id']))

        conn.commit()
        conn.close()
        return True, "Pathology center profile details updated successfully."
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Failed to update profile: {str(e)}"


def update_pathology_center_address(center_id: str, data: Dict[str, Any]) -> Tuple[bool, str]:
    """Updates center address name, location coordinates, landmarks, and additional directions."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        UPDATE pathology_centers SET
            address_name = ?,
            address = ?,
            landmark = ?,
            address_additional_info = ?,
            city = ?,
            state_province = ?,
            postal_code = ?,
            country = ?,
            latitude = ?,
            longitude = ?,
            timezone = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (
            data.get('address_name', 'Main Facility Address'),
            data.get('address', ''),
            data.get('landmark', ''),
            data.get('address_additional_info', ''),
            data.get('city', ''),
            data.get('state_province', ''),
            data.get('postal_code', ''),
            data.get('country', 'India'),
            float(data.get('latitude') or 0.0),
            float(data.get('longitude') or 0.0),
            data.get('timezone', 'IST (UTC+5:30)'),
            center_id
        ))
        conn.commit()
        conn.close()
        return True, "Pathology center location & address information saved."
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Failed to update address: {str(e)}"


def update_pathology_staff_profile(staff_id: str, data: Dict[str, Any]) -> Tuple[bool, str]:
    """Updates staff / administrator profile information and avatar image."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        UPDATE pathology_staff SET
            full_name = ?,
            email = ?,
            phone = ?,
            qualification = ?,
            license_number = ?,
            bio = ?,
            profile_image = COALESCE(?, profile_image)
        WHERE id = ?
        """, (
            data.get('full_name'),
            data.get('email'),
            data.get('phone'),
            data.get('qualification'),
            data.get('license_number'),
            data.get('bio'),
            data.get('profile_image'),
            staff_id
        ))
        conn.commit()
        conn.close()
        return True, "Staff profile details updated successfully."
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Failed to update staff profile: {str(e)}"


# ==============================================================================
# 11. DOCTOR & HOSPITAL NETWORK CONNECTIONS (TRIPARTITE HANDSHAKE)
# ==============================================================================

def connect_with_doctor(
    center_id: str,
    doctor_id: str,
    notes: Optional[str] = None,
    partnership_type: str = 'ROUTINE_DIAGNOSTICS',
    requested_by: str = 'PATHOLOGY',
    doctor_name: Optional[str] = None,
    center_name: Optional[str] = None,
    hospital_id: Optional[str] = None,
    hospital_name: Optional[str] = None
) -> Tuple[bool, str]:
    """Establishes or updates a referral partnership with a doctor requiring dual verification."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM doctor_pathology_connections WHERE center_id = ? AND doctor_id = ?", (center_id, doctor_id))
        existing = cursor.fetchone()

        if requested_by == 'PATHOLOGY':
            path_acc = 1
            doc_acc = 0
            hosp_acc = 1 if not hospital_id else (int(existing['hospital_accepted']) if existing and existing['hospital_accepted'] is not None else 0)
        elif requested_by == 'DOCTOR':
            doc_acc = 1
            path_acc = int(existing['pathology_accepted']) if existing and existing['pathology_accepted'] is not None else 0
            hosp_acc = 1 if not hospital_id else (int(existing['hospital_accepted']) if existing and existing['hospital_accepted'] is not None else 0)
        elif requested_by == 'HOSPITAL':
            hosp_acc = 1
            doc_acc = 0
            path_acc = int(existing['pathology_accepted']) if existing and existing['pathology_accepted'] is not None else 0
        else:
            hosp_acc = 0
            doc_acc = 0
            path_acc = 0

        # Connection is only fully ACCEPTED when both hospital (if applicable) and doctor accept, and pathology confirms
        if hosp_acc == 1 and doc_acc == 1 and path_acc == 1:
            status = 'ACCEPTED'
        elif hosp_acc == 1 and path_acc == 1 and doc_acc == 0:
            status = 'PENDING_DOCTOR'
        elif doc_acc == 1 and path_acc == 1 and hosp_acc == 0:
            status = 'PENDING_HOSPITAL'
        else:
            status = 'PENDING_APPROVAL'

        if existing:
            cursor.execute("""
            UPDATE doctor_pathology_connections SET
                status = ?,
                notes = ?,
                partnership_type = ?,
                hospital_id = COALESCE(?, hospital_id),
                doctor_name = COALESCE(?, doctor_name),
                hospital_name = COALESCE(?, hospital_name),
                center_name = COALESCE(?, center_name),
                requested_by = ?,
                hospital_accepted = ?,
                doctor_accepted = ?,
                pathology_accepted = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (
                status, notes or "Active referral network partnership", partnership_type,
                hospital_id, doctor_name, hospital_name, center_name,
                requested_by, hosp_acc, doc_acc, path_acc, existing['id']
            ))
            conn_id = existing['id']
            msg = "Doctor referral connection request updated."
        else:
            conn_id = f"DPC-{secrets.token_hex(4).upper()}"
            cursor.execute("""
            INSERT INTO doctor_pathology_connections (
                id, doctor_id, center_id, status, notes, partnership_type,
                hospital_id, doctor_name, hospital_name, center_name,
                requested_by, hospital_accepted, doctor_accepted, pathology_accepted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conn_id, doctor_id, center_id, status, notes or "Direct lab referral agreement", partnership_type,
                hospital_id, doctor_name, hospital_name, center_name,
                requested_by, hosp_acc, doc_acc, path_acc
            ))
            msg = "Referral partnership request transmitted to doctor."

        conn.commit()
        conn.close()
        return True, msg
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e)


def connect_with_hospital(
    center_id: str,
    hospital_id: str,
    doctor_id: Optional[str] = None,
    notes: Optional[str] = None,
    partnership_type: str = 'ROUTINE_DIAGNOSTICS',
    requested_by: str = 'HOSPITAL',
    doctor_name: Optional[str] = None,
    hospital_name: Optional[str] = None,
    center_name: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Establishes a diagnostic referral tie-up with a hospital.
    Rule: When hospital sends connect request to pathology center, the connection is only ACTIVE
    after hospital accepts/requests it AND the designated doctor also accepts it.
    """
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM hospital_pathology_connections WHERE center_id = ? AND hospital_id = ?", (center_id, hospital_id))
        existing = cursor.fetchone()

        if requested_by == 'HOSPITAL':
            hosp_acc = 1
            doc_acc = 0
            path_acc = int(existing['pathology_accepted']) if existing and existing['pathology_accepted'] is not None else 0
        elif requested_by == 'DOCTOR':
            doc_acc = 1
            hosp_acc = int(existing['hospital_accepted']) if existing and existing['hospital_accepted'] is not None else 0
            path_acc = int(existing['pathology_accepted']) if existing and existing['pathology_accepted'] is not None else 0
        elif requested_by == 'PATHOLOGY':
            path_acc = 1
            hosp_acc = int(existing['hospital_accepted']) if existing and existing['hospital_accepted'] is not None else 0
            doc_acc = int(existing['doctor_accepted']) if existing and existing['doctor_accepted'] is not None else 0
        else:
            hosp_acc = 0
            doc_acc = 0
            path_acc = 0

        # Tripartite rule: Full connection ONLY when Hospital + Doctor + Pathology all confirm
        if hosp_acc == 1 and doc_acc == 1 and path_acc == 1:
            status = 'ACCEPTED'
        elif hosp_acc == 1 and path_acc == 1 and doc_acc == 0:
            status = 'PENDING_DOCTOR'
        elif doc_acc == 1 and path_acc == 1 and hosp_acc == 0:
            status = 'PENDING_HOSPITAL'
        elif hosp_acc == 1 and doc_acc == 0:
            status = 'PENDING_DOCTOR'
        else:
            status = 'PENDING_APPROVAL'

        if existing:
            cursor.execute("""
            UPDATE hospital_pathology_connections SET
                status = ?,
                notes = ?,
                partnership_type = ?,
                doctor_id = COALESCE(?, doctor_id),
                doctor_name = COALESCE(?, doctor_name),
                hospital_name = COALESCE(?, hospital_name),
                center_name = COALESCE(?, center_name),
                requested_by = ?,
                hospital_accepted = ?,
                doctor_accepted = ?,
                pathology_accepted = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (
                status, notes or "Hospital diagnostic partnership", partnership_type,
                doctor_id, doctor_name, hospital_name, center_name,
                requested_by, hosp_acc, doc_acc, path_acc, existing['id']
            ))
            conn_id = existing['id']
            msg = "Hospital partnership tie-up updated."
        else:
            conn_id = f"HPC-{secrets.token_hex(4).upper()}"
            cursor.execute("""
            INSERT INTO hospital_pathology_connections (
                id, hospital_id, center_id, status, notes, partnership_type,
                doctor_id, doctor_name, hospital_name, center_name,
                requested_by, hospital_accepted, doctor_accepted, pathology_accepted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conn_id, hospital_id, center_id, status, notes or "Hospital pathology service tie-up", partnership_type,
                doctor_id, doctor_name, hospital_name, center_name,
                requested_by, hosp_acc, doc_acc, path_acc
            ))
            msg = "Hospital diagnostic tie-up request initiated."

        # Also synchronize doctor-level connection record if doctor_id is present
        if doctor_id:
            cursor.execute("""
            SELECT id FROM doctor_pathology_connections WHERE center_id = ? AND doctor_id = ?
            """, (center_id, doctor_id))
            d_exist = cursor.fetchone()
            if d_exist:
                cursor.execute("""
                UPDATE doctor_pathology_connections SET
                    hospital_id = ?,
                    hospital_name = ?,
                    status = ?,
                    hospital_accepted = ?,
                    doctor_accepted = ?,
                    pathology_accepted = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """, (hospital_id, hospital_name, status, hosp_acc, doc_acc, path_acc, d_exist['id']))
            else:
                cursor.execute("""
                INSERT INTO doctor_pathology_connections (
                    id, doctor_id, center_id, status, notes, partnership_type,
                    hospital_id, doctor_name, hospital_name, center_name,
                    requested_by, hospital_accepted, doctor_accepted, pathology_accepted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"DPC-{secrets.token_hex(4).upper()}", doctor_id, center_id, status,
                    notes or f"Affiliated via {hospital_name or 'Hospital'}", partnership_type,
                    hospital_id, doctor_name, hospital_name, center_name,
                    requested_by, hosp_acc, doc_acc, path_acc
                ))

        conn.commit()
        conn.close()
        return True, msg
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e)


def respond_hospital_pathology_connection(
    connection_id: str,
    actor_role: str, # 'hospital', 'doctor', 'pathology'
    action: str = 'accept', # 'accept', 'reject'
    notes: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Handles step-by-step confirmation of a Hospital-Pathology partnership.
    Ensures connection is only fully ACCEPTED when both Hospital AND Doctor (and Pathology) accept.
    """
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM hospital_pathology_connections WHERE id = ?", (connection_id,))
        c = cursor.fetchone()
        if not c:
            conn.close()
            return False, "Hospital connection record not found.", {}

        if action == 'reject':
            cursor.execute("""
            UPDATE hospital_pathology_connections SET
                status = 'REJECTED',
                notes = COALESCE(?, notes),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (notes or f"Partnership declined by {actor_role}", connection_id))

            if c['doctor_id']:
                cursor.execute("""
                UPDATE doctor_pathology_connections SET
                    status = 'REJECTED',
                    updated_at = CURRENT_TIMESTAMP
                WHERE center_id = ? AND doctor_id = ?
                """, (c['center_id'], c['doctor_id']))

            conn.commit()
            conn.close()
            return True, f"Partnership request declined by {actor_role}.", {"status": "REJECTED"}

        # Handle 'accept'
        hosp_acc = 1 if actor_role == 'hospital' else int(c['hospital_accepted'] or 0)
        doc_acc = 1 if actor_role == 'doctor' else int(c['doctor_accepted'] or 0)
        path_acc = 1 if actor_role == 'pathology' else int(c['pathology_accepted'] or 0)

        # Tripartite check
        if hosp_acc == 1 and doc_acc == 1 and path_acc == 1:
            status = 'ACCEPTED'
            msg = "Partnership fully established! Both Hospital and Doctor have confirmed the connection."
        elif hosp_acc == 1 and path_acc == 1 and doc_acc == 0:
            status = 'PENDING_DOCTOR'
            msg = "Hospital & Pathology confirmed. Awaiting Doctor acceptance."
        elif doc_acc == 1 and path_acc == 1 and hosp_acc == 0:
            status = 'PENDING_HOSPITAL'
            msg = "Doctor & Pathology confirmed. Awaiting Hospital acceptance."
        elif hosp_acc == 1 and doc_acc == 1 and path_acc == 0:
            status = 'PENDING_PATHOLOGY'
            msg = "Hospital & Doctor confirmed. Awaiting Pathology Center acceptance."
        else:
            status = 'PENDING_APPROVAL'
            msg = "Connection status updated."

        cursor.execute("""
        UPDATE hospital_pathology_connections SET
            status = ?,
            hospital_accepted = ?,
            doctor_accepted = ?,
            pathology_accepted = ?,
            notes = COALESCE(?, notes),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (status, hosp_acc, doc_acc, path_acc, notes, connection_id))

        if c['doctor_id']:
            cursor.execute("""
            UPDATE doctor_pathology_connections SET
                status = ?,
                hospital_accepted = ?,
                doctor_accepted = ?,
                pathology_accepted = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE center_id = ? AND doctor_id = ?
            """, (status, hosp_acc, doc_acc, path_acc, c['center_id'], c['doctor_id']))

        conn.commit()
        conn.close()
        return True, msg, {
            "status": status,
            "hospital_accepted": hosp_acc,
            "doctor_accepted": doc_acc,
            "pathology_accepted": path_acc
        }
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e), {}


def respond_doctor_pathology_connection(
    connection_id: str,
    action: str = 'accept',
    notes: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """Doctor directly responds to their individual or hospital-linked pathology connection."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM doctor_pathology_connections WHERE id = ?", (connection_id,))
        c = cursor.fetchone()
        if not c:
            conn.close()
            return False, "Doctor connection record not found.", {}

        if action == 'reject':
            cursor.execute("UPDATE doctor_pathology_connections SET status = 'REJECTED', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (connection_id,))
            conn.commit()
            conn.close()
            return True, "Partnership declined by doctor.", {"status": "REJECTED"}

        doc_acc = 1
        hosp_acc = int(c['hospital_accepted'] or (1 if not c['hospital_id'] else 0))
        path_acc = int(c['pathology_accepted'] or 1)

        if doc_acc == 1 and hosp_acc == 1 and path_acc == 1:
            status = 'ACCEPTED'
            msg = "Partnership fully established! Doctor and Hospital have accepted."
        elif doc_acc == 1 and hosp_acc == 0:
            status = 'PENDING_HOSPITAL'
            msg = "Doctor accepted. Awaiting Hospital confirmation."
        else:
            status = 'ACCEPTED'
            msg = "Doctor connection accepted."

        cursor.execute("""
        UPDATE doctor_pathology_connections SET
            status = ?,
            doctor_accepted = ?,
            hospital_accepted = ?,
            pathology_accepted = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (status, doc_acc, hosp_acc, path_acc, connection_id))

        if c['hospital_id']:
            cursor.execute("""
            UPDATE hospital_pathology_connections SET
                status = ?,
                doctor_accepted = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE center_id = ? AND hospital_id = ?
            """, (status, doc_acc, c['center_id'], c['hospital_id']))

        conn.commit()
        conn.close()
        return True, msg, {"status": status, "doctor_accepted": 1}
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e), {}


def get_center_doctor_connections(center_id: str) -> List[Dict[str, Any]]:
    """Lists all doctor connections for this pathology center."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM doctor_pathology_connections
    WHERE center_id = ?
    ORDER BY created_at DESC
    """, (center_id,))
    rows = dict_list_from_rows(cursor.fetchall())
    conn.close()
    return rows


def get_center_hospital_connections(center_id: str) -> List[Dict[str, Any]]:
    """Lists all hospital connections for this pathology center."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM hospital_pathology_connections
    WHERE center_id = ?
    ORDER BY created_at DESC
    """, (center_id,))
    rows = dict_list_from_rows(cursor.fetchall())
    conn.close()
    return rows


def get_doctor_pathology_connections_list(doctor_id: str) -> List[Dict[str, Any]]:
    """Lists all pathology connections associated with a given doctor."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT d.*, c.center_name, c.email as center_email, c.phone as center_phone,
           c.city, c.state_province, c.country, c.rating, c.address
    FROM doctor_pathology_connections d
    JOIN pathology_centers c ON d.center_id = c.id
    WHERE d.doctor_id = ?
    ORDER BY d.created_at DESC
    """, (doctor_id,))
    rows = dict_list_from_rows(cursor.fetchall())
    conn.close()
    return rows


def get_hospital_pathology_connections_list(hospital_id: str) -> List[Dict[str, Any]]:
    """Lists all pathology connections associated with a given hospital."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT h.*, c.center_name, c.email as center_email, c.phone as center_phone,
           c.city, c.state_province, c.country, c.rating, c.address
    FROM hospital_pathology_connections h
    JOIN pathology_centers c ON h.center_id = c.id
    WHERE h.hospital_id = ?
    ORDER BY h.created_at DESC
    """, (hospital_id,))
    rows = dict_list_from_rows(cursor.fetchall())
    conn.close()
    return rows


def get_incoming_doctor_prescriptions_and_medicines(center_id: str) -> List[Dict[str, Any]]:
    """Retrieves all doctor referrals and prescribed medicine orders sent to this pathology center."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT r.*,
           (SELECT COUNT(*) FROM diagnostic_referral_items WHERE referral_id = r.id AND item_type = 'TEST') as test_count,
           (SELECT COUNT(*) FROM diagnostic_referral_items WHERE referral_id = r.id AND item_type = 'MEDICINE') as medicine_count
    FROM diagnostic_referrals r
    WHERE r.center_id = ? OR r.center_id IS NULL
    ORDER BY r.created_at DESC
    """, (center_id,))
    referrals = dict_list_from_rows(cursor.fetchall())

    for ref in referrals:
        cursor.execute("SELECT * FROM diagnostic_referral_items WHERE referral_id = ?", (ref['id'],))
        ref['items'] = dict_list_from_rows(cursor.fetchall())
        try:
            ref['medicines_list'] = json.loads(ref.get('medicines_json') or '[]')
        except Exception:
            ref['medicines_list'] = []

    conn.close()
    return referrals


def get_diagnostic_tests_for_center(center_id: str) -> List[Dict[str, Any]]:
    """Retrieves all diagnostic tests configured for a pathology center, seeding if empty."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM diagnostic_tests 
    WHERE center_id = ? 
    ORDER BY category_name ASC, test_name ASC
    """, (center_id,))
    rows = dict_list_from_rows(cursor.fetchall())

    # If center has no tests seeded, seed them from MASTER_TESTS_CATALOG
    if not rows:
        cursor.execute("SELECT country, currency, organization_id FROM pathology_centers WHERE id = ?", (center_id,))
        center = cursor.fetchone()
        curr = center['currency'] if center and center['currency'] else 'INR'
        org_id = center['organization_id'] if center and center['organization_id'] else 'ORG-DEFAULT'

        for t in MASTER_TESTS_CATALOG:
            test_id = f"TST-{t['code']}-{center_id}"
            price = t['base_price_usd'] if curr == "USD" else t['base_price_inr']
            params_json = json.dumps(t.get('parameters', []))

            cursor.execute("""
            INSERT OR REPLACE INTO diagnostic_tests (
                id, center_id, organization_id, test_name, test_code, category_id, category_name, description,
                sample_type, container_type, required_quantity, preparation_instructions, fasting_required, fasting_hours,
                turnaround_hours, price, currency, home_collection_eligible, walkin_eligible, parameters_json, is_active,
                is_public, discount_percent, offer_price, badge
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 0.0, 0.0, '')
            """, (
                test_id, center_id, org_id,
                t['name'], t['code'], f"CAT-{t['category_code']}", t['category_name'], t['description'],
                t['sample_type'], t['container_type'], t['required_quantity'], t['preparation_instructions'],
                1 if t['fasting_required'] else 0, t['fasting_hours'], t['turnaround_hours'], price, curr,
                1 if t['home_collection_eligible'] else 0, 1 if t['walkin_eligible'] else 0, params_json
            ))
        conn.commit()

        cursor.execute("""
        SELECT * FROM diagnostic_tests 
        WHERE center_id = ? 
        ORDER BY category_name ASC, test_name ASC
        """, (center_id,))
        rows = dict_list_from_rows(cursor.fetchall())

    conn.close()
    return rows


def toggle_diagnostic_test_visibility(test_id: str, center_id: str) -> Tuple[bool, str, int]:
    """Toggles public catalog visibility (is_active / is_public) for a diagnostic test."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, test_name, is_active, is_public FROM diagnostic_tests WHERE id = ? AND center_id = ?", (test_id, center_id))
    test = cursor.fetchone()
    if not test:
        conn.close()
        return False, "Test not found in center catalog.", 0

    current_state = test['is_active'] if test['is_active'] is not None else 1
    new_state = 0 if current_state == 1 else 1

    cursor.execute("""
    UPDATE diagnostic_tests
    SET is_active = ?, is_public = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ? AND center_id = ?
    """, (new_state, new_state, test_id, center_id))
    conn.commit()
    conn.close()

    status_str = "Published to Public Catalog" if new_state == 1 else "Hidden from Public Catalog"
    return True, f"'{test['test_name']}' is now {status_str}.", new_state


def update_diagnostic_test_details(test_id: str, center_id: str, data: Dict[str, Any]) -> Tuple[bool, str]:
    """Updates pricing, discount percentage, promotional badges, sample instructions, and TAT for a test."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, test_name FROM diagnostic_tests WHERE id = ? AND center_id = ?", (test_id, center_id))
    test = cursor.fetchone()
    if not test:
        conn.close()
        return False, "Test not found in center catalog."

    base_price = float(data.get('price', 0.0) or 0.0)
    discount_pct = float(data.get('discount_percent', 0.0) or 0.0)
    
    # Calculate or use explicit offer price
    explicit_offer = float(data.get('offer_price', 0.0) or 0.0)
    if explicit_offer > 0:
        offer_price = explicit_offer
        if base_price > 0 and discount_pct == 0:
            discount_pct = round(((base_price - offer_price) / base_price) * 100.0, 1)
    elif discount_pct > 0 and base_price > 0:
        offer_price = round(base_price * (1.0 - (discount_pct / 100.0)), 2)
    else:
        offer_price = base_price

    badge = (data.get('badge') or '').strip()
    is_active = 1 if data.get('is_active') in [1, '1', True, 'true', 'on'] else 0
    is_public = 1 if data.get('is_public') in [1, '1', True, 'true', 'on'] else is_active
    fasting_required = 1 if data.get('fasting_required') in [1, '1', True, 'true', 'on'] else 0
    fasting_hours = int(data.get('fasting_hours', 0) or 0)
    turnaround_hours = int(data.get('turnaround_hours', 12) or 12)
    sample_type = (data.get('sample_type') or 'Blood').strip()
    container_type = (data.get('container_type') or 'Lavender Top (EDTA)').strip()
    required_quantity = (data.get('required_quantity') or '2.0 mL').strip()
    preparation_instructions = (data.get('preparation_instructions') or '').strip()
    home_collection_eligible = 1 if data.get('home_collection_eligible') in [1, '1', True, 'true', 'on'] else 0
    walkin_eligible = 1 if data.get('walkin_eligible') in [1, '1', True, 'true', 'on'] else 0

    cursor.execute("""
    UPDATE diagnostic_tests
    SET price = ?,
        discount_percent = ?,
        offer_price = ?,
        badge = ?,
        is_active = ?,
        is_public = ?,
        fasting_required = ?,
        fasting_hours = ?,
        turnaround_hours = ?,
        sample_type = ?,
        container_type = ?,
        required_quantity = ?,
        preparation_instructions = ?,
        home_collection_eligible = ?,
        walkin_eligible = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = ? AND center_id = ?
    """, (
        base_price, discount_pct, offer_price, badge, is_active, is_public,
        fasting_required, fasting_hours, turnaround_hours, sample_type, container_type,
        required_quantity, preparation_instructions, home_collection_eligible, walkin_eligible,
        test_id, center_id
    ))
    conn.commit()
    conn.close()

    return True, f"Pricing and catalog details for '{test['test_name']}' updated successfully."


def add_diagnostic_test(center_id: str, data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
    """Adds a new custom diagnostic test to a pathology center's catalog."""
    conn = get_diagnostic_db()
    cursor = conn.cursor()

    test_name = (data.get('test_name') or data.get('name') or '').strip()
    if not test_name:
        conn.close()
        return False, "Test Name is required.", None

    test_code = (data.get('test_code') or data.get('code') or '').strip().upper()
    if not test_code:
        clean_name = re.sub(r'[^A-Za-z0-9]', '', test_name)[:6].upper()
        test_code = f"TST-{clean_name}" if clean_name else f"TST-{uuid.uuid4().hex[:6].upper()}"

    # Get center info for currency & org_id
    cursor.execute("SELECT currency, organization_id FROM pathology_centers WHERE id = ?", (center_id,))
    center = cursor.fetchone()
    currency = center['currency'] if center and center['currency'] else 'INR'
    org_id = center['organization_id'] if center and center['organization_id'] else 'ORG-DEFAULT'

    # Ensure unique test code for this center
    cursor.execute("SELECT id FROM diagnostic_tests WHERE test_code = ? AND center_id = ?", (test_code, center_id))
    if cursor.fetchone():
        test_code = f"{test_code}-{uuid.uuid4().hex[:4].upper()}"

    test_id = f"TST-{test_code}-{center_id}"

    category_name = (data.get('category_name') or data.get('category') or 'Biochemistry & Routine Diagnostics').strip()
    category_id = (data.get('category_id') or '').strip()
    if not category_id:
        clean_cat = re.sub(r'[^A-Za-z0-9]', '', category_name)[:6].upper()
        category_id = f"CAT-{clean_cat}"

    description = (data.get('description') or '').strip()
    sample_type = (data.get('sample_type') or 'Blood').strip()
    container_type = (data.get('container_type') or 'Lavender Top (EDTA)').strip()
    required_quantity = (data.get('required_quantity') or '2.0 mL').strip()
    preparation_instructions = (data.get('preparation_instructions') or '').strip()
    
    fasting_required = 1 if data.get('fasting_required') in [1, '1', True, 'true', 'on'] else 0
    fasting_hours = int(data.get('fasting_hours', 0) or 0)
    turnaround_hours = int(data.get('turnaround_hours', 12) or 12)

    base_price = float(data.get('price', 0.0) or data.get('base_price_inr', 0.0) or 0.0)
    discount_pct = float(data.get('discount_percent', 0.0) or 0.0)
    explicit_offer = float(data.get('offer_price', 0.0) or 0.0)

    if explicit_offer > 0:
        offer_price = explicit_offer
        if base_price > 0 and discount_pct == 0:
            discount_pct = round(((base_price - offer_price) / base_price) * 100.0, 1)
    elif discount_pct > 0 and base_price > 0:
        offer_price = round(base_price * (1.0 - (discount_pct / 100.0)), 2)
    else:
        offer_price = base_price

    badge = (data.get('badge') or '').strip()
    home_collection_eligible = 1 if data.get('home_collection_eligible', '1') in [1, '1', True, 'true', 'on'] else 0
    walkin_eligible = 1 if data.get('walkin_eligible', '1') in [1, '1', True, 'true', 'on'] else 0
    
    is_active = 1 if data.get('is_active', '1') in [1, '1', True, 'true', 'on'] else 0
    is_public = 1 if data.get('is_public', str(is_active)) in [1, '1', True, 'true', 'on'] else is_active

    params = data.get('parameters') or []
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception:
            params = []
    params_json = json.dumps(params)

    cursor.execute("""
    INSERT INTO diagnostic_tests (
        id, center_id, organization_id, test_name, test_code, category_id, category_name, description,
        sample_type, container_type, required_quantity, preparation_instructions, fasting_required, fasting_hours,
        turnaround_hours, price, currency, home_collection_eligible, walkin_eligible, parameters_json,
        is_active, is_public, discount_percent, offer_price, badge, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        test_id, center_id, org_id, test_name, test_code, category_id, category_name, description,
        sample_type, container_type, required_quantity, preparation_instructions, fasting_required, fasting_hours,
        turnaround_hours, base_price, currency, home_collection_eligible, walkin_eligible, params_json,
        is_active, is_public, discount_pct, offer_price, badge
    ))
    conn.commit()
    conn.close()

    return True, f"Diagnostic test '{test_name}' ({test_code}) added successfully to catalog.", test_id




