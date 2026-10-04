"""
spherix/services/diagnostic_db.py
Unified Diagnostic & Pathology Laboratory Database Management Engine
Supports Microsoft SQL Server (via pyodbc) with automatic SQLite fallback.
Provides schema definitions, migrations, catalog seeding, matching engine,
state transitions, sample tracking, report management, and audit logging.
"""

import os
import sys
import json
import math
import uuid
from datetime import datetime, date, timezone
from werkzeug.security import generate_password_hash, check_password_hash

# ─── Database Connection Helper ───────────────────────────────────────────────
def get_db():
    from spherix.services.database import get_db_connection
    return get_db_connection()

def is_sqlite_conn(conn):
    return conn and getattr(conn, '__module__', '').startswith('sqlite3')

# ─── State Machine Constants ──────────────────────────────────────────────────
BOOKING_STATES = [
    'DRAFT',
    'REQUESTED',
    'AWAITING_LAB_ACCEPTANCE',
    'ACCEPTED',
    'DECLINED',
    'AWAITING_PATIENT_CONFIRMATION',
    'PAYMENT_PENDING',
    'CONFIRMED',
    'COLLECTION_SCHEDULED',
    'COLLECTOR_ASSIGNED',
    'SAMPLE_COLLECTED',
    'SAMPLE_RECEIVED',
    'PROCESSING',
    'REPORT_PENDING_VERIFICATION',
    'REPORT_PUBLISHED',
    'COMPLETED',
    'CANCELLATION_REQUESTED',
    'CANCELLED',
    'REFUND_PENDING',
    'REFUNDED',
    'EXPIRED'
]

VALID_TRANSITIONS = {
    'DRAFT': ['REQUESTED', 'CANCELLED'],
    'REQUESTED': ['AWAITING_LAB_ACCEPTANCE', 'DECLINED', 'CANCELLED'],
    'AWAITING_LAB_ACCEPTANCE': ['ACCEPTED', 'DECLINED', 'CANCELLED'],
    'ACCEPTED': ['AWAITING_PATIENT_CONFIRMATION', 'PAYMENT_PENDING', 'CONFIRMED', 'CANCELLED'],
    'DECLINED': ['REQUESTED', 'CANCELLED'],
    'AWAITING_PATIENT_CONFIRMATION': ['PAYMENT_PENDING', 'CONFIRMED', 'DECLINED', 'CANCELLED'],
    'PAYMENT_PENDING': ['CONFIRMED', 'CANCELLED', 'EXPIRED'],
    'CONFIRMED': ['COLLECTION_SCHEDULED', 'CANCELLATION_REQUESTED', 'CANCELLED'],
    'COLLECTION_SCHEDULED': ['COLLECTOR_ASSIGNED', 'SAMPLE_COLLECTED', 'CANCELLATION_REQUESTED', 'CANCELLED'],
    'COLLECTOR_ASSIGNED': ['SAMPLE_COLLECTED', 'COLLECTION_SCHEDULED', 'CANCELLATION_REQUESTED', 'CANCELLED'],
    'SAMPLE_COLLECTED': ['SAMPLE_RECEIVED', 'CANCELLATION_REQUESTED'],
    'SAMPLE_RECEIVED': ['PROCESSING'],
    'PROCESSING': ['REPORT_PENDING_VERIFICATION', 'REPORT_PUBLISHED'],
    'REPORT_PENDING_VERIFICATION': ['REPORT_PUBLISHED', 'PROCESSING'],
    'REPORT_PUBLISHED': ['COMPLETED', 'REPORT_PUBLISHED'], # Amendment returns to PUBLISHED
    'COMPLETED': ['REPORT_PUBLISHED'], # In case of post-completion amendment
    'CANCELLATION_REQUESTED': ['CANCELLED', 'CONFIRMED'],
    'CANCELLED': ['REFUND_PENDING', 'REFUNDED'],
    'REFUND_PENDING': ['REFUNDED'],
    'REFUNDED': [],
    'EXPIRED': []
}

LAB_STATUSES = ['PENDING_VERIFICATION', 'APPROVED', 'REJECTED', 'SUSPENDED', 'INACTIVE']
REFERRAL_PRIORITIES = ['ROUTINE', 'URGENT', 'TIME_SENSITIVE']
REPORT_STATUSES = ['DRAFT', 'UNDER_REVIEW', 'VERIFIED', 'PUBLISHED', 'AMENDED', 'WITHDRAWN']

# ─── 1. Schema Initialization ─────────────────────────────────────────────────
def init_diagnostic_schema():
    """Initializes all diagnostic tables in SQL Server or SQLite fallback."""
    conn = get_db()
    if not conn:
        print("⚠️ Diagnostic DB: Connection unavailable.")
        return False

    cursor = conn.cursor()
    is_sqlite = is_sqlite_conn(conn)

    # 1. DiagnosticCategories
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT DEFAULT 'fas fa-vial',
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_categories' AND xtype='U')
            CREATE TABLE diagnostic_categories (
                id VARCHAR(50) PRIMARY KEY,
                name NVARCHAR(100) NOT NULL,
                description NVARCHAR(MAX),
                icon NVARCHAR(100) DEFAULT 'fas fa-vial',
                display_order INT DEFAULT 0,
                is_active BIT DEFAULT 1,
                created_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 2. DiagnosticTests (Master Catalog)
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_tests (
                id TEXT PRIMARY KEY,
                test_code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category_id TEXT NOT NULL,
                category_name TEXT,
                description TEXT,
                specimen_type TEXT NOT NULL,
                preparation_instructions TEXT,
                fasting_required INTEGER DEFAULT 0,
                fasting_hours INTEGER DEFAULT 0,
                expected_tat_hours INTEGER DEFAULT 12,
                prescription_required INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                clinical_notes TEXT,
                base_price REAL DEFAULT 500.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_tests' AND xtype='U')
            CREATE TABLE diagnostic_tests (
                id VARCHAR(50) PRIMARY KEY,
                test_code NVARCHAR(50) UNIQUE NOT NULL,
                name NVARCHAR(255) NOT NULL,
                category_id VARCHAR(50) NOT NULL,
                category_name NVARCHAR(100),
                description NVARCHAR(MAX),
                specimen_type NVARCHAR(100) NOT NULL,
                preparation_instructions NVARCHAR(MAX),
                fasting_required BIT DEFAULT 0,
                fasting_hours INT DEFAULT 0,
                expected_tat_hours INT DEFAULT 12,
                prescription_required BIT DEFAULT 0,
                is_active BIT DEFAULT 1,
                clinical_notes NVARCHAR(MAX),
                base_price DECIMAL(10,2) DEFAULT 500.0,
                created_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 3. DiagnosticLabs
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_labs (
                id TEXT PRIMARY KEY,
                legal_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                registration_number TEXT UNIQUE NOT NULL,
                lab_type TEXT DEFAULT 'Independent Pathology Lab',
                owner_name TEXT,
                phone TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                address TEXT NOT NULL,
                city TEXT NOT NULL,
                state TEXT NOT NULL,
                pincode TEXT NOT NULL,
                latitude REAL DEFAULT 0.0,
                longitude REAL DEFAULT 0.0,
                service_radius_km REAL DEFAULT 15.0,
                license_number TEXT,
                nabl_accreditation_number TEXT,
                nabl_scope TEXT,
                is_nabl_accredited INTEGER DEFAULT 0,
                home_collection_available INTEGER DEFAULT 1,
                walkin_available INTEGER DEFAULT 1,
                operating_hours TEXT DEFAULT '07:00 AM - 09:00 PM',
                bank_name TEXT,
                account_number TEXT,
                account_holder TEXT,
                ifsc_code TEXT,
                status TEXT DEFAULT 'PENDING_VERIFICATION',
                rejection_reason TEXT,
                correction_request TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_labs' AND xtype='U')
            CREATE TABLE diagnostic_labs (
                id VARCHAR(50) PRIMARY KEY,
                legal_name NVARCHAR(255) NOT NULL,
                display_name NVARCHAR(255) NOT NULL,
                registration_number NVARCHAR(100) UNIQUE NOT NULL,
                lab_type NVARCHAR(100) DEFAULT 'Independent Pathology Lab',
                owner_name NVARCHAR(255),
                phone NVARCHAR(50) NOT NULL,
                email NVARCHAR(255) UNIQUE NOT NULL,
                password NVARCHAR(255) NOT NULL,
                address NVARCHAR(MAX) NOT NULL,
                city NVARCHAR(100) NOT NULL,
                state NVARCHAR(100) NOT NULL,
                pincode NVARCHAR(20) NOT NULL,
                latitude FLOAT DEFAULT 0.0,
                longitude FLOAT DEFAULT 0.0,
                service_radius_km FLOAT DEFAULT 15.0,
                license_number NVARCHAR(100),
                nabl_accreditation_number NVARCHAR(100),
                nabl_scope NVARCHAR(MAX),
                is_nabl_accredited BIT DEFAULT 0,
                home_collection_available BIT DEFAULT 1,
                walkin_available BIT DEFAULT 1,
                operating_hours NVARCHAR(MAX) DEFAULT '07:00 AM - 09:00 PM',
                bank_name NVARCHAR(255),
                account_number NVARCHAR(100),
                account_holder NVARCHAR(255),
                ifsc_code NVARCHAR(50),
                status NVARCHAR(50) DEFAULT 'PENDING_VERIFICATION',
                rejection_reason NVARCHAR(MAX),
                correction_request NVARCHAR(MAX),
                is_active BIT DEFAULT 1,
                created_at DATETIME DEFAULT GETDATE(),
                updated_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 4. DiagnosticLabDocuments
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_lab_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lab_id TEXT NOT NULL,
                document_type TEXT NOT NULL,
                document_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_lab_documents' AND xtype='U')
            CREATE TABLE diagnostic_lab_documents (
                id INT IDENTITY(1,1) PRIMARY KEY,
                lab_id VARCHAR(50) NOT NULL,
                document_type NVARCHAR(100) NOT NULL,
                document_name NVARCHAR(255) NOT NULL,
                file_path NVARCHAR(500) NOT NULL,
                uploaded_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 5. DiagnosticLabServices (Test Pricing and Availability per Lab)
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_lab_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lab_id TEXT NOT NULL,
                test_id TEXT NOT NULL,
                price REAL NOT NULL,
                mrp REAL NOT NULL,
                home_collection_fee REAL DEFAULT 0.0,
                home_collection_available INTEGER DEFAULT 1,
                processing_available INTEGER DEFAULT 1,
                custom_tat_hours INTEGER,
                is_available INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(lab_id, test_id)
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_lab_services' AND xtype='U')
            CREATE TABLE diagnostic_lab_services (
                id INT IDENTITY(1,1) PRIMARY KEY,
                lab_id VARCHAR(50) NOT NULL,
                test_id VARCHAR(50) NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                mrp DECIMAL(10,2) NOT NULL,
                home_collection_fee DECIMAL(10,2) DEFAULT 0.0,
                home_collection_available BIT DEFAULT 1,
                processing_available BIT DEFAULT 1,
                custom_tat_hours INT,
                is_available BIT DEFAULT 1,
                created_at DATETIME DEFAULT GETDATE(),
                updated_at DATETIME DEFAULT GETDATE(),
                CONSTRAINT UQ_lab_test UNIQUE(lab_id, test_id)
            )
        """)

    # 6. DiagnosticLabSlots (Time Slot Capacity)
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_lab_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lab_id TEXT NOT NULL,
                slot_date DATE NOT NULL,
                slot_time TEXT NOT NULL,
                collection_type TEXT DEFAULT 'HOME_COLLECTION',
                max_capacity INTEGER DEFAULT 10,
                booked_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                UNIQUE(lab_id, slot_date, slot_time, collection_type)
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_lab_slots' AND xtype='U')
            CREATE TABLE diagnostic_lab_slots (
                id INT IDENTITY(1,1) PRIMARY KEY,
                lab_id VARCHAR(50) NOT NULL,
                slot_date DATE NOT NULL,
                slot_time NVARCHAR(100) NOT NULL,
                collection_type NVARCHAR(50) DEFAULT 'HOME_COLLECTION',
                max_capacity INT DEFAULT 10,
                booked_count INT DEFAULT 0,
                is_active BIT DEFAULT 1,
                CONSTRAINT UQ_lab_slot UNIQUE(lab_id, slot_date, slot_time, collection_type)
            )
        """)

    # 7. DiagnosticBookings
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_bookings (
                id TEXT PRIMARY KEY,
                booking_source TEXT DEFAULT 'PATIENT_DIRECT',
                referral_id TEXT,
                patient_id TEXT NOT NULL,
                patient_name TEXT NOT NULL,
                patient_phone TEXT,
                patient_email TEXT,
                doctor_id TEXT,
                lab_id TEXT NOT NULL,
                collection_type TEXT DEFAULT 'HOME_COLLECTION',
                collection_address TEXT,
                collection_city TEXT,
                collection_pincode TEXT,
                collection_latitude REAL,
                collection_longitude REAL,
                scheduled_date DATE NOT NULL,
                scheduled_slot TEXT NOT NULL,
                subtotal REAL NOT NULL,
                collection_fee REAL DEFAULT 0.0,
                platform_fee REAL DEFAULT 0.0,
                total_amount REAL NOT NULL,
                lab_commission_rate REAL DEFAULT 10.0,
                lab_payout_amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'REQUESTED',
                decline_reason TEXT,
                cancellation_reason TEXT,
                patient_notes TEXT,
                prescription_file TEXT,
                idempotency_key TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_bookings' AND xtype='U')
            CREATE TABLE diagnostic_bookings (
                id VARCHAR(50) PRIMARY KEY,
                booking_source NVARCHAR(50) DEFAULT 'PATIENT_DIRECT',
                referral_id VARCHAR(50) NULL,
                patient_id VARCHAR(50) NOT NULL,
                patient_name NVARCHAR(255) NOT NULL,
                patient_phone NVARCHAR(50) NULL,
                patient_email NVARCHAR(255) NULL,
                doctor_id VARCHAR(50) NULL,
                lab_id VARCHAR(50) NOT NULL,
                collection_type NVARCHAR(50) DEFAULT 'HOME_COLLECTION',
                collection_address NVARCHAR(MAX),
                collection_city NVARCHAR(100),
                collection_pincode NVARCHAR(20),
                collection_latitude FLOAT NULL,
                collection_longitude FLOAT NULL,
                scheduled_date DATE NOT NULL,
                scheduled_slot NVARCHAR(100) NOT NULL,
                subtotal DECIMAL(10,2) NOT NULL,
                collection_fee DECIMAL(10,2) DEFAULT 0.0,
                platform_fee DECIMAL(10,2) DEFAULT 0.0,
                total_amount DECIMAL(10,2) NOT NULL,
                lab_commission_rate DECIMAL(5,2) DEFAULT 10.0,
                lab_payout_amount DECIMAL(10,2) NOT NULL,
                status NVARCHAR(50) NOT NULL DEFAULT 'REQUESTED',
                decline_reason NVARCHAR(MAX) NULL,
                cancellation_reason NVARCHAR(MAX) NULL,
                patient_notes NVARCHAR(MAX) NULL,
                prescription_file NVARCHAR(500) NULL,
                idempotency_key NVARCHAR(100) UNIQUE NULL,
                created_at DATETIME DEFAULT GETDATE(),
                updated_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 8. DiagnosticBookingItems
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_booking_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id TEXT NOT NULL,
                test_id TEXT NOT NULL,
                test_name TEXT NOT NULL,
                test_code TEXT,
                price REAL NOT NULL,
                specimen_type TEXT,
                fasting_required INTEGER DEFAULT 0
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_booking_items' AND xtype='U')
            CREATE TABLE diagnostic_booking_items (
                id INT IDENTITY(1,1) PRIMARY KEY,
                booking_id VARCHAR(50) NOT NULL,
                test_id VARCHAR(50) NOT NULL,
                test_name NVARCHAR(255) NOT NULL,
                test_code NVARCHAR(50),
                price DECIMAL(10,2) NOT NULL,
                specimen_type NVARCHAR(100),
                fasting_required BIT DEFAULT 0
            )
        """)

    # 9. DiagnosticReferrals
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_referrals (
                id TEXT PRIMARY KEY,
                referral_number TEXT UNIQUE NOT NULL,
                doctor_id TEXT NOT NULL,
                doctor_name TEXT,
                patient_id TEXT NOT NULL,
                patient_name TEXT,
                selected_lab_id TEXT,
                priority TEXT DEFAULT 'ROUTINE',
                clinical_indication TEXT NOT NULL,
                doctor_instructions TEXT,
                patient_location TEXT,
                status TEXT DEFAULT 'ISSUED',
                booking_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_referrals' AND xtype='U')
            CREATE TABLE diagnostic_referrals (
                id VARCHAR(50) PRIMARY KEY,
                referral_number NVARCHAR(100) UNIQUE NOT NULL,
                doctor_id VARCHAR(50) NOT NULL,
                doctor_name NVARCHAR(255) NULL,
                patient_id VARCHAR(50) NOT NULL,
                patient_name NVARCHAR(255) NULL,
                selected_lab_id VARCHAR(50) NULL,
                priority NVARCHAR(50) DEFAULT 'ROUTINE',
                clinical_indication NVARCHAR(MAX) NOT NULL,
                doctor_instructions NVARCHAR(MAX) NULL,
                patient_location NVARCHAR(MAX) NULL,
                status NVARCHAR(50) DEFAULT 'ISSUED',
                booking_id VARCHAR(50) NULL,
                created_at DATETIME DEFAULT GETDATE(),
                updated_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 10. DiagnosticReferralItems
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_referral_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referral_id TEXT NOT NULL,
                test_id TEXT NOT NULL,
                test_name TEXT NOT NULL,
                test_code TEXT
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_referral_items' AND xtype='U')
            CREATE TABLE diagnostic_referral_items (
                id INT IDENTITY(1,1) PRIMARY KEY,
                referral_id VARCHAR(50) NOT NULL,
                test_id VARCHAR(50) NOT NULL,
                test_name NVARCHAR(255) NOT NULL,
                test_code NVARCHAR(50)
            )
        """)

    # 11. DiagnosticSampleCollections
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_sample_collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id TEXT NOT NULL,
                collection_type TEXT NOT NULL,
                collector_name TEXT,
                collector_phone TEXT,
                collection_address TEXT,
                scheduled_date DATE NOT NULL,
                scheduled_slot TEXT NOT NULL,
                collection_status TEXT DEFAULT 'SCHEDULED',
                collection_notes TEXT,
                collected_at TIMESTAMP,
                received_at_lab_at TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_sample_collections' AND xtype='U')
            CREATE TABLE diagnostic_sample_collections (
                id INT IDENTITY(1,1) PRIMARY KEY,
                booking_id VARCHAR(50) NOT NULL,
                collection_type NVARCHAR(50) NOT NULL,
                collector_name NVARCHAR(255) NULL,
                collector_phone NVARCHAR(50) NULL,
                collection_address NVARCHAR(MAX) NULL,
                scheduled_date DATE NOT NULL,
                scheduled_slot NVARCHAR(100) NOT NULL,
                collection_status NVARCHAR(50) DEFAULT 'SCHEDULED',
                collection_notes NVARCHAR(MAX) NULL,
                collected_at DATETIME NULL,
                received_at_lab_at DATETIME NULL
            )
        """)

    # 12. DiagnosticSamples
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_samples (
                id TEXT PRIMARY KEY,
                booking_id TEXT NOT NULL,
                test_id TEXT NOT NULL,
                test_name TEXT,
                sample_identifier TEXT UNIQUE NOT NULL,
                specimen_type TEXT NOT NULL,
                collected_at TIMESTAMP,
                status TEXT DEFAULT 'COLLECTED',
                rejection_reason TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_samples' AND xtype='U')
            CREATE TABLE diagnostic_samples (
                id VARCHAR(50) PRIMARY KEY,
                booking_id VARCHAR(50) NOT NULL,
                test_id VARCHAR(50) NOT NULL,
                test_name NVARCHAR(255) NULL,
                sample_identifier NVARCHAR(100) UNIQUE NOT NULL,
                specimen_type NVARCHAR(100) NOT NULL,
                collected_at DATETIME NULL,
                status NVARCHAR(50) DEFAULT 'COLLECTED',
                rejection_reason NVARCHAR(MAX) NULL,
                notes NVARCHAR(MAX) NULL,
                created_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 13. DiagnosticReports
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_reports (
                id TEXT PRIMARY KEY,
                booking_id TEXT NOT NULL,
                patient_id TEXT NOT NULL,
                doctor_id TEXT,
                lab_id TEXT NOT NULL,
                test_id TEXT NOT NULL,
                test_name TEXT,
                report_number TEXT UNIQUE NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                mime_type TEXT DEFAULT 'application/pdf',
                status TEXT DEFAULT 'DRAFT',
                verified_by TEXT,
                verified_at TIMESTAMP,
                published_at TIMESTAMP,
                version INTEGER DEFAULT 1,
                amendment_reason TEXT,
                clinical_summary TEXT,
                parameters_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_reports' AND xtype='U')
            CREATE TABLE diagnostic_reports (
                id VARCHAR(50) PRIMARY KEY,
                booking_id VARCHAR(50) NOT NULL,
                patient_id VARCHAR(50) NOT NULL,
                doctor_id VARCHAR(50) NULL,
                lab_id VARCHAR(50) NOT NULL,
                test_id VARCHAR(50) NOT NULL,
                test_name NVARCHAR(255) NULL,
                report_number NVARCHAR(100) UNIQUE NOT NULL,
                file_path NVARCHAR(500) NOT NULL,
                file_name NVARCHAR(255) NOT NULL,
                file_size INT DEFAULT 0,
                mime_type NVARCHAR(100) DEFAULT 'application/pdf',
                status NVARCHAR(50) DEFAULT 'DRAFT',
                verified_by NVARCHAR(255) NULL,
                verified_at DATETIME NULL,
                published_at DATETIME NULL,
                version INT DEFAULT 1,
                amendment_reason NVARCHAR(MAX) NULL,
                clinical_summary NVARCHAR(MAX) NULL,
                parameters_json NVARCHAR(MAX) NULL,
                created_at DATETIME DEFAULT GETDATE(),
                updated_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 14. DiagnosticReportVersions
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_report_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                amended_by TEXT NOT NULL,
                amendment_reason TEXT NOT NULL,
                amended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_report_versions' AND xtype='U')
            CREATE TABLE diagnostic_report_versions (
                id INT IDENTITY(1,1) PRIMARY KEY,
                report_id VARCHAR(50) NOT NULL,
                version INT NOT NULL,
                file_path NVARCHAR(500) NOT NULL,
                amended_by NVARCHAR(255) NOT NULL,
                amendment_reason NVARCHAR(MAX) NOT NULL,
                amended_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 15. DiagnosticPayments
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_payments (
                id TEXT PRIMARY KEY,
                booking_id TEXT NOT NULL,
                patient_id TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'INR',
                payment_method TEXT DEFAULT 'RAZORPAY',
                payment_gateway_order_id TEXT,
                payment_gateway_payment_id TEXT,
                payment_gateway_signature TEXT,
                status TEXT DEFAULT 'PENDING',
                idempotency_key TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_payments' AND xtype='U')
            CREATE TABLE diagnostic_payments (
                id VARCHAR(50) PRIMARY KEY,
                booking_id VARCHAR(50) NOT NULL,
                patient_id VARCHAR(50) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                currency NVARCHAR(10) DEFAULT 'INR',
                payment_method NVARCHAR(50) DEFAULT 'RAZORPAY',
                payment_gateway_order_id NVARCHAR(255) NULL,
                payment_gateway_payment_id NVARCHAR(255) NULL,
                payment_gateway_signature NVARCHAR(255) NULL,
                status NVARCHAR(50) DEFAULT 'PENDING',
                idempotency_key NVARCHAR(100) UNIQUE NULL,
                created_at DATETIME DEFAULT GETDATE(),
                updated_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 16. DiagnosticRefunds
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_refunds (
                id TEXT PRIMARY KEY,
                booking_id TEXT NOT NULL,
                payment_id TEXT,
                patient_id TEXT NOT NULL,
                refund_amount REAL NOT NULL,
                reason TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                gateway_refund_id TEXT,
                processed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_refunds' AND xtype='U')
            CREATE TABLE diagnostic_refunds (
                id VARCHAR(50) PRIMARY KEY,
                booking_id VARCHAR(50) NOT NULL,
                payment_id VARCHAR(50) NULL,
                patient_id VARCHAR(50) NOT NULL,
                refund_amount DECIMAL(10,2) NOT NULL,
                reason NVARCHAR(MAX) NOT NULL,
                status NVARCHAR(50) DEFAULT 'PENDING',
                gateway_refund_id NVARCHAR(255) NULL,
                processed_at DATETIME NULL,
                created_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 17. DiagnosticSettlements
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_settlements (
                id TEXT PRIMARY KEY,
                lab_id TEXT NOT NULL,
                period_start DATE NOT NULL,
                period_end DATE NOT NULL,
                gross_amount REAL NOT NULL,
                commission_amount REAL NOT NULL,
                net_payout_amount REAL NOT NULL,
                status TEXT DEFAULT 'PENDING',
                utr_number TEXT,
                settled_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_settlements' AND xtype='U')
            CREATE TABLE diagnostic_settlements (
                id VARCHAR(50) PRIMARY KEY,
                lab_id VARCHAR(50) NOT NULL,
                period_start DATE NOT NULL,
                period_end DATE NOT NULL,
                gross_amount DECIMAL(10,2) NOT NULL,
                commission_amount DECIMAL(10,2) NOT NULL,
                net_payout_amount DECIMAL(10,2) NOT NULL,
                status NVARCHAR(50) DEFAULT 'PENDING',
                utr_number NVARCHAR(100) NULL,
                settled_at DATETIME NULL,
                created_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 18. DiagnosticNotifications
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_type TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                booking_id TEXT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                link TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_notifications' AND xtype='U')
            CREATE TABLE diagnostic_notifications (
                id INT IDENTITY(1,1) PRIMARY KEY,
                recipient_type NVARCHAR(50) NOT NULL,
                recipient_id VARCHAR(50) NOT NULL,
                booking_id VARCHAR(50) NULL,
                title NVARCHAR(255) NOT NULL,
                message NVARCHAR(MAX) NOT NULL,
                link NVARCHAR(500) NULL,
                is_read BIT DEFAULT 0,
                created_at DATETIME DEFAULT GETDATE()
            )
        """)

    # 19. DiagnosticAuditLogs
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_audit_logs' AND xtype='U')
            CREATE TABLE diagnostic_audit_logs (
                id INT IDENTITY(1,1) PRIMARY KEY,
                actor_type NVARCHAR(50) NOT NULL,
                actor_id VARCHAR(50) NOT NULL,
                action NVARCHAR(100) NOT NULL,
                resource_type NVARCHAR(100) NOT NULL,
                resource_id VARCHAR(50) NOT NULL,
                details NVARCHAR(MAX) NULL,
                ip_address NVARCHAR(50) NULL,
                timestamp DATETIME DEFAULT GETDATE()
            )
        """)

    # 20. DiagnosticLabStaff
    if is_sqlite:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostic_lab_staff (
                id TEXT PRIMARY KEY,
                lab_id TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT NOT NULL,
                role TEXT DEFAULT 'Phlebotomist',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_lab_staff' AND xtype='U')
            CREATE TABLE diagnostic_lab_staff (
                id VARCHAR(50) PRIMARY KEY,
                lab_id VARCHAR(50) NOT NULL,
                name NVARCHAR(255) NOT NULL,
                email NVARCHAR(255) NULL,
                phone NVARCHAR(50) NOT NULL,
                role NVARCHAR(100) DEFAULT 'Phlebotomist',
                is_active BIT DEFAULT 1,
                created_at DATETIME DEFAULT GETDATE()
            )
        """)

    # Commit table creation
    try:
        conn.commit()
    except Exception:
        pass
    conn.close()
    print("✅ Diagnostic & Pathology Database Schema initialized successfully.")
    seed_master_catalog()
    return True

# ─── 2. Master Catalog Seeding ────────────────────────────────────────────────
def seed_master_catalog():
    """Seeds standardized diagnostic categories and clinical tests."""
    conn = get_db()
    if not conn:
        return
    cursor = conn.cursor()

    categories = [
        ('CAT-BLOOD-SUGAR', 'Blood Sugar', 'Glycemic control and diabetes monitoring tests', 'fas fa-tint', 1),
        ('CAT-CBC', 'Complete Blood Count', 'Hemoglobin, red cells, white cells, platelets, and infection markers', 'fas fa-dna', 2),
        ('CAT-THYROID', 'Thyroid', 'Thyroid hormone evaluation (T3, T4, TSH) and metabolism assessment', 'fas fa-wave-square', 3),
        ('CAT-LFT', 'Liver Function', 'Hepatic enzymes, bilirubin, albumin, and cellular health', 'fas fa-lungs', 4),
        ('CAT-KFT', 'Kidney Function', 'Renal filtration, creatinine, urea, BUN, and electrolytes', 'fas fa-heartbeat', 5),
        ('CAT-LIPID', 'Lipid Profile', 'Cardiovascular risk markers, cholesterol, LDL, HDL, and triglycerides', 'fas fa-heart', 6),
        ('CAT-VITAMINS', 'Vitamin Tests', 'Nutritional adequacy, Vitamin D3, B12, and mineral panels', 'fas fa-sun', 7),
        ('CAT-HORMONES', 'Hormones', 'Endocrine, reproductive, fertility, and stress hormones', 'fas fa-venus-mars', 8),
        ('CAT-URINE', 'Urine Tests', 'Urinalysis, spot protein, microalbumin, and bacterial cultures', 'fas fa-flask', 9),
        ('CAT-STOOL', 'Stool Tests', 'Gastrointestinal screening, occult blood, and microscopy', 'fas fa-bacteria', 10),
        ('CAT-INFECTION', 'Infection and Serology', 'Dengue, Malaria, Typhoid, viral serologies, and inflammation', 'fas fa-shield-virus', 11),
        ('CAT-CARDIAC', 'Cardiac Tests', 'Cardiac biomarkers, Troponin, hs-CRP, and cardiovascular health', 'fas fa-procedures', 12),
        ('CAT-MICROBIOLOGY', 'Microbiology', 'Bacterial cultures, antibiotic susceptibility, and fungal stains', 'fas fa-microscope', 13),
        ('CAT-HISTOPATH', 'Histopathology', 'Biopsy examination, cytology, and tissue diagnostics', 'fas fa-file-medical-alt', 14),
        ('CAT-XRAY', 'X-ray', 'Digital plain radiography for chest, bones, and joints', 'fas fa-x-ray', 15),
        ('CAT-ULTRASOUND', 'Ultrasound', 'Abdominal, pelvic, vascular, and soft tissue sonography', 'fas fa-broadcast-tower', 16),
        ('CAT-CT', 'CT', 'High-resolution computed tomography scans', 'fas fa-circle-notch', 17),
        ('CAT-MRI', 'MRI', 'Magnetic resonance imaging for neurological and musculoskeletal assessment', 'fas fa-magnet', 18),
        ('CAT-OTHER', 'Other Diagnostic Services', 'Specialized clinical diagnostic tests and health screenings', 'fas fa-plus-circle', 19)
    ]

    for cat_id, name, desc, icon, order in categories:
        cursor.execute("SELECT id FROM diagnostic_categories WHERE id = ?", (cat_id,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO diagnostic_categories (id, name, description, icon, display_order, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                (cat_id, name, desc, icon, order)
            )

    # Standard Clinical Tests Required by Section 5
    tests = [
        # Blood Sugar
        ('TST-FBS', 'FBS', 'Fasting Blood Sugar (Glucose, Fasting)', 'CAT-BLOOD-SUGAR', 'Blood Sugar',
         'Measures blood glucose levels after an overnight fast. Primary screening test for prediabetes and diabetes mellitus.',
         'Blood (Fluoride Plasma)', '10-12 hours overnight fasting required. Plain water is permitted.', 1, 10, 6, 0, 99.0,
         'Reference Range: Normal: 70-99 mg/dL, Prediabetes: 100-125 mg/dL, Diabetes: >= 126 mg/dL.'),
        ('TST-PPBS', 'PPBS', 'Post-Prandial Blood Sugar (PPBS 2hr)', 'CAT-BLOOD-SUGAR', 'Blood Sugar',
         'Evaluates glycemic response exactly 2 hours after the start of a standardized meal.',
         'Blood (Fluoride Plasma)', 'Collect blood exactly 2 hours after commencing a meal. Maintain normal medication unless instructed by physician.', 0, 0, 6, 0, 99.0,
         'Reference Range: Normal: < 140 mg/dL, Impaired: 140-199 mg/dL, Diabetes: >= 200 mg/dL.'),
        ('TST-RBS', 'RBS', 'Random Blood Sugar (Glucose, Random)', 'CAT-BLOOD-SUGAR', 'Blood Sugar',
         'Rapid assessment of current blood glucose at any arbitrary time of day, regardless of food intake.',
         'Blood (Fluoride Plasma)', 'No preparation or fasting needed.', 0, 0, 4, 0, 99.0,
         'Useful for acute hypoglycemic or hyperglycemic evaluation.'),
        ('TST-HBA1C', 'HbA1c', 'HbA1c (Glycated Hemoglobin) & Estimated Average Glucose', 'CAT-BLOOD-SUGAR', 'Blood Sugar',
         'Reflects mean blood sugar concentrations over preceding 8-12 weeks (3 months). Gold standard for long-term diabetes management.',
         'Blood (EDTA Whole Blood)', 'No fasting required. Sample can be collected at any time.', 0, 0, 8, 0, 349.0,
         'Reference Range: Normal: < 5.7%, Prediabetes: 5.7% - 6.4%, Diabetes: >= 6.5%.'),

        # Complete Blood Count & Hematology
        ('TST-CBC', 'CBC', 'Complete Blood Count (CBC) with Differential & Platelets', 'CAT-CBC', 'Complete Blood Count',
         'Comprehensive assessment of cellular blood elements: RBC, WBC, Hemoglobin, Hematocrit, Platelets, MCV, MCH, MCHC, and 5-part Differential.',
         'Blood (EDTA Whole Blood)', 'No fasting needed. Normal hydration recommended.', 0, 0, 6, 0, 249.0,
         'Assesses anemia, acute/chronic infection, clotting disorders, and systemic hematologic conditions.'),
        ('TST-HB', 'Hemoglobin', 'Hemoglobin (Hb) Concentration', 'CAT-CBC', 'Complete Blood Count',
         'Measures the oxygen-carrying iron-rich protein in red blood cells.',
         'Blood (EDTA Whole Blood)', 'No fasting required.', 0, 0, 4, 0, 119.0,
         'Reference Range: Adult Males: 13.5-17.5 g/dL; Adult Females: 12.0-15.5 g/dL.'),
        ('TST-ESR', 'ESR', 'Erythrocyte Sedimentation Rate (Westergren Method)', 'CAT-CBC', 'Complete Blood Count',
         'Nonspecific marker of systemic inflammation, infection, autoimmune activity, and tissue necrosis.',
         'Blood (EDTA / Sodium Citrate)', 'No fasting required. Morning sample preferred.', 0, 0, 6, 0, 99.0,
         'Reference: Male: 0-15 mm/hr, Female: 0-20 mm/hr.'),

        # Thyroid
        ('TST-TSH', 'TSH', 'Thyroid Stimulating Hormone (Ultrasensitive TSH)', 'CAT-THYROID', 'Thyroid',
         'Primary pituitary regulator of thyroid glands. Highly sensitive frontline screen for hypo- and hyperthyroidism.',
         'Blood (Serum)', 'Morning fasting sample preferred. If taking thyroid hormone replacement, take medication AFTER blood draw.', 0, 0, 8, 0, 199.0,
         'Reference Range: 0.45 - 4.50 micro-IU/mL.'),
        ('TST-T3', 'T3', 'Triiodothyronine Total (T3)', 'CAT-THYROID', 'Thyroid',
         'Quantifies circulating active thyroid hormone to evaluate thyrotoxicosis and metabolic state.',
         'Blood (Serum)', 'Morning blood collection recommended.', 0, 0, 8, 0, 179.0,
         'Reference Range: 0.80 - 2.00 ng/mL.'),
        ('TST-T4', 'T4', 'Thyroxine Total (T4)', 'CAT-THYROID', 'Thyroid',
         'Measures total circulating thyroxine to determine thyroid functional status.',
         'Blood (Serum)', 'Morning blood collection recommended.', 0, 0, 8, 0, 179.0,
         'Reference Range: 5.1 - 14.1 micro-g/dL.'),

        # Liver Function
        ('TST-LFT', 'LFT', 'Liver Function Test (Complete LFT Profile - 12 Parameters)', 'CAT-LFT', 'Liver Function',
         'Comprehensive hepatic panel: SGOT/AST, SGPT/ALT, Total Bilirubin, Direct/Indirect Bilirubin, Alkaline Phosphatase (ALP), Total Protein, Albumin, Globulin, and A/G Ratio.',
         'Blood (Serum)', 'No strict fasting required; overnight fast or avoiding high-fat meals 4 hours prior recommended.', 0, 0, 8, 0, 449.0,
         'Detects hepatitis, hepatic steatosis, drug-induced hepatotoxicity, and biliary obstruction.'),

        # Kidney Function
        ('TST-KFT', 'KFT', 'Kidney Function Test (KFT / RFT - 8 Parameters)', 'CAT-KFT', 'Kidney Function',
         'Renal assessment panel: Serum Creatinine, Blood Urea Nitrogen (BUN), Serum Urea, Uric Acid, BUN/Creatinine Ratio, and Electrolytes.',
         'Blood (Serum)', 'Hydrate normally. Avoid intense strenuous exercise 12 hours before test.', 0, 0, 8, 0, 449.0,
         'Evaluates glomerular filtration, renal clearance, and pre-renal or intrinsic azotemia.'),
        ('TST-CREAT', 'Creatinine', 'Serum Creatinine with Estimated GFR (eGFR)', 'CAT-KFT', 'Kidney Function',
         'Accurate marker of glomerular filtration and chronic kidney disease staging.',
         'Blood (Serum)', 'Avoid heavy meat ingestion and creatine supplements 24 hours prior.', 0, 0, 6, 0, 149.0,
         'Reference Range: Male: 0.7 - 1.3 mg/dL, Female: 0.5 - 1.1 mg/dL.'),
        ('TST-UREA', 'Urea', 'Blood Urea & Blood Urea Nitrogen (BUN)', 'CAT-KFT', 'Kidney Function',
         'Measures protein breakdown end-products eliminated by kidneys.',
         'Blood (Serum)', 'No strict fasting required.', 0, 0, 6, 0, 129.0,
         'Reference Range: Blood Urea: 15 - 40 mg/dL.'),

        # Lipid Profile
        ('TST-LIPID', 'Lipid Profile', 'Lipid Profile Complete (Cholesterol, HDL, LDL, VLDL, Triglycerides)', 'CAT-LIPID', 'Lipid Profile',
         'Atherosclerotic cardiovascular risk screening: Total Cholesterol, HDL (Good), LDL (Bad), VLDL, Triglycerides, Non-HDL, and Cardiac Ratios.',
         'Blood (Serum)', 'Strict 10-12 hours overnight fasting required. Plain water allowed. Avoid alcohol 24 hours prior.', 1, 10, 8, 0, 399.0,
         'Total Cholesterol < 200 mg/dL, LDL < 100 mg/dL, HDL > 50 mg/dL, Triglycerides < 150 mg/dL.'),

        # Vitamins
        ('TST-VITD', 'Vitamin D', 'Vitamin D 25-Hydroxy (Total 25-OH Vitamin D2 + D3)', 'CAT-VITAMINS', 'Vitamin Tests',
         'Determines systemic Vitamin D status critical for bone mineralization, immune function, and calcium absorption.',
         'Blood (Serum)', 'No fasting required. Avoid high-dose biotin 24 hours prior.', 0, 0, 12, 0, 599.0,
         'Deficiency: < 20 ng/mL, Insufficiency: 20-30 ng/mL, Sufficiency: 30-100 ng/mL.'),
        ('TST-VITB12', 'Vitamin B12', 'Vitamin B12 (Cyanocobalamin / Active Cobalamin)', 'CAT-VITAMINS', 'Vitamin Tests',
         'Evaluates peripheral neuropathy, megaloblastic anemia, and metabolic deficiency.',
         'Blood (Serum)', 'Overnight fasting of 8 hours preferred. Discontinue B12 supplements 48 hours prior if physician permits.', 1, 8, 12, 0, 499.0,
         'Reference Range: 211 - 911 pg/mL.'),

        # Urine & Microbiology
        ('TST-URINE-R', 'Urine Routine', 'Urine Routine & Microscopic Examination (Complete Urinalysis)', 'CAT-URINE', 'Urine Tests',
         'Physical, chemical, and microscopic examination: Protein, Glucose, Ketones, Bilirubin, Blood, pH, Specific Gravity, Pus Cells, RBCs, Casts, and Crystals.',
         'Urine (Clean-Catch Midstream Specimen)', 'Clean genitalia prior to sample collection. Collect first morning midstream clean-catch in sterile container.', 0, 0, 6, 0, 129.0,
         'Detects urinary tract infections (UTI), proteinuria, hematuria, and renal calculi.'),
        ('TST-URINE-C', 'Urine Culture', 'Urine Culture & Automated Antibiotic Sensitivity (AST)', 'CAT-URINE', 'Urine Tests',
         'Identifies uropathogenic bacteria and determines minimum inhibitory concentration (MIC) antibiotic sensitivities.',
         'Urine (Sterile Midstream Catch)', 'Collect in sterile container BEFORE starting antibiotic therapy. Store in cold pack if transit exceeds 1 hour.', 0, 0, 48, 0, 499.0,
         'Colony count >= 10^5 CFU/mL indicates significant bacteriuria.')
    ]

    for t in tests:
        test_id, code, name, cat_id, cat_name, desc, specimen, prep, fast_req, fast_hrs, tat, rx_req, price, notes = t
        variants = [test_id]
        if test_id.startswith('TST-'):
            variants.append('TEST-' + test_id[4:])
        for vid in variants:
            vcode = code if vid == test_id else f"{code}-ALT"
            cursor.execute("SELECT id FROM diagnostic_tests WHERE id = ?", (vid,))
            if not cursor.fetchone():
                try:
                    cursor.execute("""
                        INSERT INTO diagnostic_tests (
                            id, test_code, name, category_id, category_name, description, specimen_type,
                            preparation_instructions, fasting_required, fasting_hours, expected_tat_hours,
                            prescription_required, is_active, clinical_notes, base_price
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """, (vid, vcode, name, cat_id, cat_name, desc, specimen, prep, fast_req, fast_hrs, tat, rx_req, notes, price))
                except Exception:
                    pass

    try:
        conn.commit()
    except Exception:
        pass
    conn.close()

# ─── 3. Haversine Distance Calculation ───────────────────────────────────────
def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates geographic distance in kilometers between two GPS coordinates using Haversine formula.
    Returns 0.0 if coordinates are missing.
    """
    if not lat1 or not lon1 or not lat2 or not lon2:
        return 0.0
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        if lat1 == 0.0 and lon1 == 0.0:
            return 0.0
        if lat2 == 0.0 and lon2 == 0.0:
            return 0.0
    except (ValueError, TypeError):
        return 0.0

    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)

# ─── 4. Database-Backed Nearby Pathology Lab Matching Engine ──────────────────
def find_matching_pathology_labs(test_ids, patient_lat=None, patient_lon=None, collection_mode='HOME_COLLECTION', max_radius_km=30.0, search_radius_km=None, **kwargs):
    if search_radius_km is not None:
        max_radius_km = float(search_radius_km)
    """
    Real database-backed lab discovery service (Section 8).
    Requirements:
    1. Lab account approved (status == 'APPROVED')
    2. Lab active (is_active == 1)
    3. Within configurable radius (if coordinates available)
    4. ALL requested tests supported and available
    5. Requested collection mode supported
    Returns ranked list of eligible labs with detailed pricing and distance.
    """
    if not test_ids:
        return []

    conn = get_db()
    if not conn:
        return []
    cursor = conn.cursor()

    # Fetch all approved and active labs
    cursor.execute("""
        SELECT id, legal_name, display_name, registration_number, lab_type,
               phone, email, address, city, state, pincode,
               latitude, longitude, service_radius_km, is_nabl_accredited,
               nabl_accreditation_number, home_collection_available, walkin_available,
               operating_hours
        FROM diagnostic_labs
        WHERE status = 'APPROVED' AND is_active = 1
    """)
    labs = cursor.fetchall()
    cols = [d[0] for d in cursor.description]
    lab_records = [dict(zip(cols, row)) for row in labs]

    eligible_labs = []

    for lab in lab_records:
        lab_id = lab['id']
        lab_lat = lab.get('latitude', 0.0)
        lab_lon = lab.get('longitude', 0.0)
        service_radius = float(lab.get('service_radius_km') or 15.0)

        # Check collection mode support
        if collection_mode == 'HOME_COLLECTION' and not lab.get('home_collection_available'):
            continue
        if collection_mode == 'LAB_VISIT' and not lab.get('walkin_available'):
            continue

        # Calculate distance
        distance_km = 0.0
        if patient_lat and patient_lon and lab_lat and lab_lon:
            distance_km = calculate_haversine_distance(patient_lat, patient_lon, lab_lat, lab_lon)
            # Home collection must be within lab's service radius; if search_radius_km explicitly specified, respect caller's radius
            effective_radius = max_radius_km if search_radius_km is not None else (service_radius if collection_mode == 'HOME_COLLECTION' else max_radius_km)
            if distance_km > effective_radius and distance_km > 0:
                continue

        # Check test coverage: Lab must support EVERY requested test
        placeholders = ','.join(['?' for _ in test_ids])
        cursor.execute(f"""
            SELECT s.test_id, s.price, s.mrp, s.home_collection_fee, s.home_collection_available,
                   s.processing_available, s.custom_tat_hours, s.is_available,
                   t.name as test_name, t.test_code, t.specimen_type, t.fasting_required
            FROM diagnostic_lab_services s
            JOIN diagnostic_tests t ON s.test_id = t.id
            WHERE s.lab_id = ? AND s.test_id IN ({placeholders})
              AND s.is_available = 1 AND s.processing_available = 1
        """, [lab_id] + list(test_ids))

        service_rows = cursor.fetchall()
        s_cols = [d[0] for d in cursor.description]
        available_services = [dict(zip(s_cols, r)) for r in service_rows]

        # Verify that all requested tests are present
        covered_test_ids = {s['test_id'] for s in available_services}
        if set(test_ids) - covered_test_ids:
            # Lab is missing one or more required tests
            continue

        # If home collection, ensure home collection is enabled for these services
        if collection_mode == 'HOME_COLLECTION':
            if any(not s.get('home_collection_available') for s in available_services):
                continue

        # Calculate totals
        subtotal = sum(float(s['price']) for s in available_services)
        max_collection_fee = max([float(s.get('home_collection_fee', 0.0)) for s in available_services] + [0.0])
        # Collection fee waived if subtotal >= 500 or lab standard
        applied_collection_fee = 0.0 if (collection_mode == 'LAB_VISIT' or subtotal >= 500.0) else max_collection_fee
        total_estimate = round(subtotal + applied_collection_fee, 2)

        eligible_labs.append({
            'id': lab_id,
            'display_name': lab.get('display_name'),
            'legal_name': lab.get('legal_name'),
            'city': lab.get('city') or 'Local City',
            'is_nabl_accredited': bool(lab.get('is_nabl_accredited')),
            'available_tests_count': len(available_services),
            'total_price': total_estimate,
            'lab': lab,
            'distance_km': round(distance_km, 1),
            'test_services': available_services,
            'subtotal': subtotal,
            'collection_fee': applied_collection_fee,
            'total_estimate': total_estimate,
            'tests_count': len(available_services)
        })

    conn.close()

    # Sort eligible labs: primary by distance (if coordinates present), secondary by price
    eligible_labs.sort(key=lambda x: (x['distance_km'] if x['distance_km'] > 0 else 99999, x['total_estimate']))
    return eligible_labs

# ─── 5. Unique Identifiers & Audit Logging ────────────────────────────────────
def generate_sample_id():
    """Generates unique traceable sample barcode/QR string (Section 10)."""
    now_str = datetime.now().strftime('%Y%m%d')
    suffix = uuid.uuid4().hex[:6].upper()
    return f"SMP-{now_str}-{suffix}"

def generate_booking_id():
    now_str = datetime.now().strftime('%Y%m%d')
    suffix = uuid.uuid4().hex[:6].upper()
    return f"BK-{now_str}-{suffix}"

def generate_referral_number():
    now_str = datetime.now().strftime('%Y%m%d')
    suffix = uuid.uuid4().hex[:6].upper()
    return f"REF-{now_str}-{suffix}"

def generate_report_number():
    now_str = datetime.now().strftime('%Y%m%d')
    suffix = uuid.uuid4().hex[:6].upper()
    return f"REP-{now_str}-{suffix}"

def log_diagnostic_audit(actor_type, actor_id, action, resource_type, resource_id, details=None, ip_address=None):
    """Immutable audit logging for diagnostic operations (Section 16)."""
    conn = get_db()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO diagnostic_audit_logs (actor_type, actor_id, action, resource_type, resource_id, details, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (actor_type, str(actor_id), action, resource_type, str(resource_id), str(details or ''), str(ip_address or '')))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Diagnostic audit logging note: {e}")
    finally:
        conn.close()

def create_diagnostic_notification(recipient_type, recipient_id, title, message, booking_id=None, link=None):
    """Creates in-app notification for diagnostic events (Section 15)."""
    conn = get_db()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO diagnostic_notifications (recipient_type, recipient_id, booking_id, title, message, link, is_read)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (recipient_type, str(recipient_id), booking_id, title, message, link))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Diagnostic notification note: {e}")
    finally:
        conn.close()

# ─── 6. State Machine Validator ───────────────────────────────────────────────
def can_transition_booking(current_status, target_status):
    """Server-side enforcement of valid booking lifecycle states (Section 9)."""
    if current_status == target_status:
        return True
    allowed = VALID_TRANSITIONS.get(current_status, [])
    return target_status in allowed

# ─── 7. Pathology Lab Dashboard Metrics ───────────────────────────────────────
def get_lab_dashboard_metrics(lab_id):
    """Calculates authorized real metrics from database records (Section 4)."""
    conn = get_db()
    if not conn:
        return {}
    cursor = conn.cursor()
    today_str = date.today().isoformat()

    metrics = {
        'today_bookings': 0,
        'pending_requests': 0,
        'accepted_bookings': 0,
        'rejected_bookings': 0,
        'scheduled_collections': 0,
        'samples_collected': 0,
        'tests_processing': 0,
        'reports_pending': 0,
        'completed_bookings': 0,
        'total_revenue': 0.0,
        'settlement_balance': 0.0
    }

    try:
        # Today's bookings
        cursor.execute("SELECT COUNT(*) FROM diagnostic_bookings WHERE lab_id = ? AND scheduled_date = ?", (lab_id, today_str))
        metrics['today_bookings'] = cursor.fetchone()[0] or 0

        # Pending requests
        cursor.execute("SELECT COUNT(*) FROM diagnostic_bookings WHERE lab_id = ? AND status IN ('REQUESTED', 'AWAITING_LAB_ACCEPTANCE')", (lab_id,))
        metrics['pending_requests'] = cursor.fetchone()[0] or 0

        # Accepted bookings
        cursor.execute("SELECT COUNT(*) FROM diagnostic_bookings WHERE lab_id = ? AND status IN ('ACCEPTED', 'CONFIRMED', 'COLLECTION_SCHEDULED', 'COLLECTOR_ASSIGNED')", (lab_id,))
        metrics['accepted_bookings'] = cursor.fetchone()[0] or 0

        # Rejected bookings
        cursor.execute("SELECT COUNT(*) FROM diagnostic_bookings WHERE lab_id = ? AND status = 'DECLINED'", (lab_id,))
        metrics['rejected_bookings'] = cursor.fetchone()[0] or 0

        # Scheduled collections
        cursor.execute("SELECT COUNT(*) FROM diagnostic_bookings WHERE lab_id = ? AND status IN ('COLLECTION_SCHEDULED', 'COLLECTOR_ASSIGNED')", (lab_id,))
        metrics['scheduled_collections'] = cursor.fetchone()[0] or 0

        # Samples collected
        cursor.execute("SELECT COUNT(*) FROM diagnostic_bookings WHERE lab_id = ? AND status = 'SAMPLE_COLLECTED'", (lab_id,))
        metrics['samples_collected'] = cursor.fetchone()[0] or 0

        # Tests processing
        cursor.execute("SELECT COUNT(*) FROM diagnostic_bookings WHERE lab_id = ? AND status IN ('SAMPLE_RECEIVED', 'PROCESSING')", (lab_id,))
        metrics['tests_processing'] = cursor.fetchone()[0] or 0

        # Reports pending
        cursor.execute("SELECT COUNT(*) FROM diagnostic_bookings WHERE lab_id = ? AND status = 'REPORT_PENDING_VERIFICATION'", (lab_id,))
        metrics['reports_pending'] = cursor.fetchone()[0] or 0

        # Completed bookings
        cursor.execute("SELECT COUNT(*) FROM diagnostic_bookings WHERE lab_id = ? AND status IN ('REPORT_PUBLISHED', 'COMPLETED')", (lab_id,))
        metrics['completed_bookings'] = cursor.fetchone()[0] or 0

        # Total Revenue (sum of lab_payout_amount on paid/confirmed/completed bookings)
        cursor.execute("""
            SELECT SUM(lab_payout_amount) FROM diagnostic_bookings 
            WHERE lab_id = ? AND status NOT IN ('CANCELLED', 'DECLINED', 'REFUNDED')
        """, (lab_id,))
        rev_row = cursor.fetchone()
        metrics['total_revenue'] = round(float(rev_row[0] or 0.0), 2)

        # Settlement balance (revenue minus completed settlements)
        cursor.execute("SELECT SUM(net_payout_amount) FROM diagnostic_settlements WHERE lab_id = ? AND status = 'TRANSFERRED'", (lab_id,))
        settled_row = cursor.fetchone()
        settled_amt = float(settled_row[0] or 0.0)
        metrics['settlement_balance'] = max(0.0, round(metrics['total_revenue'] - settled_amt, 2))

    except Exception as e:
        print(f"⚠️ Error calculating dashboard metrics: {e}")
    finally:
        conn.close()

    return metrics

# ─── 8. Portal Query Services ────────────────────────────────────────────────
def get_patient_diagnostic_data(patient_id):
    """Fetches diagnostic bookings, referrals, published reports, and active catalog for patient portal."""
    conn = get_db()
    if not conn:
        return {'bookings': [], 'referrals': [], 'reports': [], 'categories': [], 'tests': []}
    cursor = conn.cursor()
    patient_id_str = str(patient_id)

    # 1. Bookings
    bookings = []
    try:
        cursor.execute("""
            SELECT b.id, b.booking_source, b.lab_id, l.display_name AS lab_name, l.phone AS lab_phone, l.address AS lab_address,
                   b.collection_type, b.scheduled_date, b.scheduled_slot, b.subtotal, b.collection_fee, b.total_amount,
                   b.status, b.decline_reason, b.cancellation_reason, b.created_at, b.doctor_id,
                   (SELECT COUNT(*) FROM diagnostic_reports r WHERE r.booking_id = b.id AND r.status IN ('PUBLISHED', 'AMENDED')) as report_count
            FROM diagnostic_bookings b
            LEFT JOIN diagnostic_labs l ON b.lab_id = l.id
            WHERE b.patient_id = ?
            ORDER BY b.created_at DESC
        """, (patient_id_str,))
        cols = [c[0] for c in cursor.description]
        rows = cursor.fetchall()
        for r in rows:
            b_dict = dict(zip(cols, r))
            # fetch items
            cursor.execute("SELECT test_id, test_name, test_code, price, specimen_type, fasting_required FROM diagnostic_booking_items WHERE booking_id = ?", (b_dict['id'],))
            item_cols = [c[0] for c in cursor.description]
            b_dict['items'] = [dict(zip(item_cols, ir)) for ir in cursor.fetchall()]

            # fetch tracking status
            cursor.execute("SELECT sample_identifier, status, specimen_type FROM diagnostic_samples WHERE booking_id = ?", (b_dict['id'],))
            s_rows = cursor.fetchall()
            b_dict['samples'] = [{'identifier': sr[0], 'status': sr[1], 'specimen': sr[2]} for sr in s_rows]

            # fetch reports
            cursor.execute("SELECT id, report_number, test_name, status, version, amendment_reason, published_at FROM diagnostic_reports WHERE booking_id = ? AND status IN ('PUBLISHED', 'AMENDED')", (b_dict['id'],))
            rep_cols = [c[0] for c in cursor.description]
            b_dict['reports'] = [dict(zip(rep_cols, rr)) for rr in cursor.fetchall()]
            bookings.append(b_dict)
    except Exception as e:
        print(f"Error fetching patient bookings: {e}")

    # 2. Referrals
    referrals = []
    try:
        cursor.execute("""
            SELECT r.id, r.referral_number, r.doctor_id, r.doctor_name, r.priority, r.clinical_indication,
                   r.doctor_instructions, r.status, r.selected_lab_id, l.display_name AS lab_name, r.created_at, r.booking_id
            FROM diagnostic_referrals r
            LEFT JOIN diagnostic_labs l ON r.selected_lab_id = l.id
            WHERE r.patient_id = ?
            ORDER BY r.created_at DESC
        """, (patient_id_str,))
        cols = [c[0] for c in cursor.description]
        for r in cursor.fetchall():
            ref_dict = dict(zip(cols, r))
            cursor.execute("SELECT test_id, test_name, test_code FROM diagnostic_referral_items WHERE referral_id = ?", (ref_dict['id'],))
            t_cols = [c[0] for c in cursor.description]
            ref_dict['tests'] = [dict(zip(t_cols, tr)) for tr in cursor.fetchall()]
            referrals.append(ref_dict)
    except Exception as e:
        print(f"Error fetching patient referrals: {e}")

    # 3. Direct Reports
    reports = []
    try:
        cursor.execute("""
            SELECT r.id, r.booking_id, r.report_number, r.test_name, r.file_name, r.file_size, r.status,
                   r.verified_by, r.published_at, r.version, r.amendment_reason, l.display_name AS lab_name
            FROM diagnostic_reports r
            LEFT JOIN diagnostic_labs l ON r.lab_id = l.id
            WHERE r.patient_id = ? AND r.status IN ('PUBLISHED', 'AMENDED')
            ORDER BY r.published_at DESC
        """, (patient_id_str,))
        cols = [c[0] for c in cursor.description]
        reports = [dict(zip(cols, r)) for r in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching patient reports: {e}")

    # 4. Master Categories and Tests
    categories = []
    tests = []
    try:
        cursor.execute("SELECT id, name, description, icon FROM diagnostic_categories WHERE is_active = 1 ORDER BY display_order ASC")
        c_cols = [c[0] for c in cursor.description]
        categories = [dict(zip(c_cols, r)) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT id, category_id, test_code, name AS test_name, specimen_type, preparation_instructions,
                   fasting_required, expected_tat_hours AS turnaround_hours, prescription_required
            FROM diagnostic_tests
            WHERE is_active = 1
            ORDER BY name ASC
        """)
        t_cols = [c[0] for c in cursor.description]
        tests = [dict(zip(t_cols, r)) for r in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching catalog: {e}")
    finally:
        conn.close()

    return {
        'bookings': bookings,
        'referrals': referrals,
        'reports': reports,
        'categories': categories,
        'tests': tests
    }

def get_doctor_diagnostic_data(doctor_id):
    """Fetches diagnostic referrals and reports issued or tracked by this doctor."""
    conn = get_db()
    if not conn:
        return {'referrals': [], 'categories': [], 'tests': []}
    cursor = conn.cursor()
    doctor_id_str = str(doctor_id)

    referrals = []
    try:
        cursor.execute("""
            SELECT r.id, r.referral_number, r.patient_id, r.patient_name, r.priority, r.clinical_indication,
                   r.doctor_instructions, r.status, r.selected_lab_id, l.display_name AS lab_name,
                   r.created_at, r.booking_id,
                   b.status AS booking_status
            FROM diagnostic_referrals r
            LEFT JOIN diagnostic_labs l ON r.selected_lab_id = l.id
            LEFT JOIN diagnostic_bookings b ON r.booking_id = b.id
            WHERE r.doctor_id = ?
            ORDER BY r.created_at DESC
        """, (doctor_id_str,))
        cols = [c[0] for c in cursor.description]
        for r in cursor.fetchall():
            ref_dict = dict(zip(cols, r))
            cursor.execute("SELECT test_id, test_name, test_code FROM diagnostic_referral_items WHERE referral_id = ?", (ref_dict['id'],))
            t_cols = [c[0] for c in cursor.description]
            ref_dict['tests'] = [dict(zip(t_cols, tr)) for tr in cursor.fetchall()]

            # fetch report if available
            cursor.execute("""
                SELECT id, report_number, test_name, status, version, published_at
                FROM diagnostic_reports
                WHERE (doctor_id = ? OR booking_id = ?) AND status IN ('PUBLISHED', 'AMENDED')
            """, (doctor_id_str, str(ref_dict.get('booking_id') or '')))
            rep_cols = [c[0] for c in cursor.description]
            ref_dict['reports'] = [dict(zip(rep_cols, rr)) for rr in cursor.fetchall()]
            referrals.append(ref_dict)
    except Exception as e:
        print(f"Error fetching doctor referrals: {e}")

    # Active Categories & Tests for creating new referrals
    categories = []
    tests = []
    try:
        cursor.execute("SELECT id, name, description, icon FROM diagnostic_categories WHERE is_active = 1 ORDER BY display_order ASC")
        c_cols = [c[0] for c in cursor.description]
        categories = [dict(zip(c_cols, r)) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT id, category_id, test_code, name AS test_name, specimen_type, preparation_instructions,
                   fasting_required, expected_tat_hours AS turnaround_hours, prescription_required
            FROM diagnostic_tests
            WHERE is_active = 1
            ORDER BY name ASC
        """)
        t_cols = [c[0] for c in cursor.description]
        tests = [dict(zip(t_cols, r)) for r in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching catalog for doctor: {e}")
    finally:
        conn.close()

    return {
        'referrals': referrals,
        'categories': categories,
        'tests': tests
    }

def get_admin_diagnostic_data():
    """Fetches laboratory approval queue, all labs, all bookings, referrals, catalog, and settlements for Admin."""
    conn = get_db()
    if not conn:
        return {'pending_labs': [], 'all_labs': [], 'recent_bookings': [], 'recent_referrals': [], 'tests': [], 'categories': []}
    cursor = conn.cursor()
    data = {}
    try:
        # 1. Pending labs
        cursor.execute("""
            SELECT id, legal_name, display_name, registration_number, lab_type, owner_name, phone, email,
                   city, state, pincode, license_number, nabl_accreditation_number, is_nabl_accredited,
                   status, rejection_reason, correction_request, created_at
            FROM diagnostic_labs
            WHERE status = 'PENDING_VERIFICATION'
            ORDER BY created_at DESC
        """)
        cols = [c[0] for c in cursor.description]
        data['pending_labs'] = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # 2. All labs
        cursor.execute("""
            SELECT id, legal_name, display_name, registration_number, lab_type, phone, email,
                   city, state, pincode, status, is_nabl_accredited, is_active, created_at
            FROM diagnostic_labs
            ORDER BY created_at DESC
        """)
        cols = [c[0] for c in cursor.description]
        data['all_labs'] = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # 3. Recent Bookings
        cursor.execute("""
            SELECT b.id, b.booking_source, b.patient_name, b.patient_phone, l.display_name AS lab_name,
                   b.collection_type, b.scheduled_date, b.scheduled_slot, b.total_amount, b.status, b.created_at
            FROM diagnostic_bookings b
            LEFT JOIN diagnostic_labs l ON b.lab_id = l.id
            ORDER BY b.created_at DESC
        """)
        cols = [c[0] for c in cursor.description]
        data['recent_bookings'] = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # 4. Recent Referrals
        cursor.execute("""
            SELECT r.id, r.referral_number, r.doctor_name, r.patient_name, l.display_name AS lab_name,
                   r.priority, r.clinical_indication, r.status, r.created_at
            FROM diagnostic_referrals r
            LEFT JOIN diagnostic_labs l ON r.selected_lab_id = l.id
            ORDER BY r.created_at DESC
        """)
        cols = [c[0] for c in cursor.description]
        data['recent_referrals'] = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # 5. Catalog tests & categories
        cursor.execute("""
            SELECT t.id, t.category_id, c.name AS category_name, t.test_code, t.name AS test_name,
                   t.specimen_type, t.preparation_instructions, t.fasting_required,
                   t.expected_tat_hours AS turnaround_hours, t.prescription_required, t.is_active
            FROM diagnostic_tests t
            LEFT JOIN diagnostic_categories c ON t.category_id = c.id
            ORDER BY c.name ASC, t.name ASC
        """)
        cols = [c[0] for c in cursor.description]
        data['tests'] = [dict(zip(cols, r)) for r in cursor.fetchall()]

        cursor.execute("SELECT id, name, description, icon, is_active FROM diagnostic_categories ORDER BY display_order ASC")
        c_cols = [c[0] for c in cursor.description]
        data['categories'] = [dict(zip(c_cols, r)) for r in cursor.fetchall()]

    except Exception as e:
        print(f"Error fetching admin diagnostic data: {e}")
    finally:
        conn.close()

    return data
