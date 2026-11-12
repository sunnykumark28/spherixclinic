import pytest
from datetime import date, time
from werkzeug.security import generate_password_hash
from spherix import create_app
from spherix.services.database import TEMP_DATA
from spherix.models.user import Patient, Doctor
from spherix.models.clinical import Appointment, BedBooking
from spherix.models.commerce import Order

@pytest.fixture
def care_client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client

def test_booked_items_sidebar_integration(care_client):
    client = care_client
    pat_id = 'PAT_SIDEBAR_TEST_01'
    patient = Patient(
        id=pat_id,
        name='Aarav Mehta',
        email='aarav.mehta@example.com',
        phone='9876543210',
        password=generate_password_hash('Pass12345!', method='pbkdf2:sha256:260000')
    )
    patient.is_verified = True
    TEMP_DATA.setdefault('patients', {})[pat_id] = patient

    # 1. Setup Doctor Consultation
    doc_id = 'DOC_TEST_01'
    doctor = Doctor(
        id=doc_id,
        first_name='Ananya',
        last_name='Sharma',
        email='ananya@example.com',
        phone='9811122233',
        department='Cardiology',
        specialty='Cardiology',
        consultation_fee=500,
        password=generate_password_hash('DocPass123!', method='pbkdf2:sha256:260000')
    )
    TEMP_DATA.setdefault('doctors', {})[doc_id] = doctor

    appt_id = 99
    appt = Appointment(
        id=appt_id,
        patient_name=patient.name,
        doctor_id=doc_id,
        appointment_date=date(2026, 11, 20),
        appointment_time=time(10, 30),
        patient_id=pat_id,
        patient_phone=patient.phone,
        reason='Hypertension and ECG Checkup',
        status='confirmed',
        consultation_fee=500,
        fee_amount=500,
        token_number='TK-999',
        consultation_type='in_person'
    )
    appt.doctor_name = "Dr. Ananya Sharma"
    appt.specialty = "Cardiology"
    TEMP_DATA.setdefault('appointments', {})[appt_id] = appt

    # 2. Setup Medicine Order
    order_id = 88
    order = Order(
        id=order_id,
        patient_id=pat_id,
        items=[{'name': 'Atorvastatin 20mg', 'quantity': 2, 'price': 150.0}],
        total_price=300.0,
        shipping_address={'name': patient.name, 'phone': patient.phone, 'address': 'Flat 402, Green Valley Apartments', 'city': 'New Delhi', 'state': 'Delhi', 'pincode': '110001'},
        order_date=date(2026, 11, 18),
        payment_method='online',
        status='dispatched'
    )
    TEMP_DATA.setdefault('orders', {})[order_id] = order

    # 3. Setup Hospital Bed Booking
    bed_id = 'BED-77'
    bed_booking = BedBooking(
        id=bed_id,
        hospital_id='HOSP_01',
        patient_id=pat_id,
        patient_name=patient.name,
        patient_phone=patient.phone,
        bed_type='Deluxe Private Room',
        reason='Post-Angioplasty Inpatient Monitoring',
        status='admitted'
    )
    bed_booking.hospital_name = 'Spherix Apex Heart Institute'
    bed_booking.admission_date = '2026-11-18'
    bed_booking.charge_per_day = 2500
    TEMP_DATA.setdefault('bed_bookings', {})[bed_id] = bed_booking

    # 4. Setup Ambulance SOS Booking
    amb_id = 'SOS-66'
    amb_booking = {
        'id': amb_id,
        'user_id': pat_id,
        'patient_phone': patient.phone,
        'vehicle_name': 'Cardiac Advanced Life Support (ALS) Ambulance',
        'service_category': 'Emergency Critical Response',
        'pickup_address': 'Sector 15, Dwarka, New Delhi',
        'destination_hospital': 'Spherix Apex Trauma Center',
        'fee': 750,
        'status': 'dispatched',
        'driver_name': 'Rajesh Kumar (Paramedic)',
        'driver_phone': '9876001122',
        'vehicle_number': 'DL-01-SPX-7788',
        'timestamp': '2026-11-18 14:15:00'
    }
    TEMP_DATA.setdefault('ambulance_bookings', {})[amb_id] = amb_booking

    # 5. Setup Diagnostic Lab Test Request
    lab_id = 55
    lab_req = {
        'id': lab_id,
        'patient_id': pat_id,
        'patient_name': patient.name,
        'doctor_id': doc_id,
        'doctor_name': 'Dr. Ananya Sharma',
        'test_name': 'Lipid Profile & Serum Electrolytes',
        'status': 'completed',
        'created_at': '2026-11-17 09:00:00',
        'notes': 'Overnight Fasting Sample Verified',
        'center_name': 'Spherix Central Diagnostics'
    }
    TEMP_DATA.setdefault('lab_requests', {})[lab_id] = lab_req

    with client.session_transaction() as sess:
        sess['_user_id'] = pat_id
        sess['user_role'] = 'patient'

    res = client.get('/patient/dashboard')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify Sidebar Offcanvas Component exists
    assert 'id="bookingDetailsOffcanvas"' in html
    assert 'booking-details-offcanvas' in html
    assert 'id="drawerServiceIcon"' in html
    assert 'id="drawerCategoryBadge"' in html
    assert 'id="drawerStatusBadge"' in html
    assert 'id="drawerRefTitle"' in html
    assert 'id="drawerDynamicBody"' in html
    assert 'id="drawerActionButtons"' in html

    # Verify JSON Data Stores are serialized
    assert 'id="patientAppointmentsData"' in html
    assert 'id="medicineOrdersData"' in html
    assert 'id="patientBedBookingsData"' in html
    assert 'id="patientAmbulanceBookingsData"' in html
    assert 'id="patientLabRequestsData"' in html

    # Verify specific records are serialized in JSON stores
    assert str(appt_id) in html
    assert str(order_id) in html
    assert str(bed_id) in html
    assert str(amb_id) in html
    assert str(lab_id) in html

    # Verify Click Triggers for All 5 Care Categories
    # Category 1: Doctor Consultation
    assert f"openBookingItemSidebar('appointment', '{appt_id}')" in html
    # Category 2: Medicine Order
    assert f"openBookingItemSidebar('medicine', '{order_id}')" in html
    # Category 3: Hospital Bed Booking
    assert f"openBookingItemSidebar('bed', '{bed_id}')" in html
    # Category 4: Ambulance SOS
    assert f"openBookingItemSidebar('ambulance', '{amb_id}')" in html
    # Category 5: Diagnostic Lab Test
    assert f"openBookingItemSidebar('lab', '{lab_id}')" in html

    # Verify clickable class and hover feedback
    assert 'clickable-booked-item' in html

    # Verify Action & Download links in dashboard
    assert f"/appointment/payment/receipt/{appt_id}" in html
    assert f"/order/invoice/{order_id}" in html
    assert f"/patient/lab-report/download/{lab_id}" in html
    assert 'printBookingSlip' in html
