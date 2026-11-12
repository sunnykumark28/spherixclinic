import pytest
from spherix.models.user import Doctor
from spherix.services.database import TEMP_DATA

@pytest.fixture
def client():
    from spherix import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client

def test_doctor_cover_hero_section_rendering(client):
    """Verifies that doctor details renders the cinematic cover profile banner and overlapping avatar layout."""
    doc_id = 'DOC-COVER-TEST-001'
    doc = Doctor(
        doc_id,
        'Aarav',
        'Singhania',
        'aarav.singhania@example.com',
        'Password123!',
        'Cardiology',
        specialization='Adult & Pediatric Interventional Cardiology',
        medical_degrees='MBBS, MD (Medicine), DM (Cardiology), FACC',
        license_number='MCI-REG-2026-888',
        experience=16,
        consultation_fee=1500.0,
        video_fee=1200.0,
        follow_up_fee=700.0,
        appointment_duration='30 Minutes',
        publishing_status='published',
        is_verified=True,
        availability_status='available',
        cover_image_url='https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=1600&q=80',
        clinic_photos='https://images.unsplash.com/photo-1586773860418-d37222d8fce3?auto=format&fit=crop&w=800&q=80',
        hospital_name='Spherix Apex Heart Institute'
    )
    TEMP_DATA['doctors'][doc_id] = doc

    res = client.get(f'/doctor/{doc_id}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # 1. Verify Cover Profile Banner elements
    assert "PANORAMIC COVER PROFILE BANNER" in html
    assert "Dr. Aarav Singhania Clinical Practice" in html
    assert "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d" in html
    assert "Senior Clinical Faculty" in html
    assert "Cover View" in html

    # 2. Verify Overlapping Doctor Profile Avatar Container
    assert "-mt-16 sm:-mt-20 lg:-mt-24" in html
    assert "Official Medical Portrait" in html
    assert "View Full Portrait" in html
    assert "Available" in html
    assert "Reg No: MCI-REG-2026-888" in html
    assert "16 Years Experience" in html

    # 3. Verify Pricing & Telemetry Card
    assert "Consultation Fees" in html
    assert "In-Person Visit" in html
    assert "Online Video Call" in html
    assert "Follow-Up Consultation" in html
    assert "Includes 7-Day Digital Follow-Up &amp; Lab Review" in html or "Includes 7-Day Digital Follow-Up" in html

    # 4. Verify 4 Quick Highlights
    assert "Clinical Exp" in html
    assert "Scheduled Appts" in html
    assert "Consult Modes" in html
    assert "Medical License" in html

    # 5. Verify Full-Screen Viewport Container & Scroll Discovery Anchor
    assert "min-h-[calc(100vh-80px)]" in html
    assert "max-w-[1850px]" in html
    assert "doctor-tabs-content" in html
    assert "Explore Clinical Dossier" in html

def test_doctor_cover_hero_procedural_fallback_without_custom_cover(client):
    """Verifies that doctor details renders procedural medical pulse cover banner when doctor has no custom cover."""
    doc_id = 'DOC-COVER-TEST-002'
    doc = Doctor(
        doc_id,
        'Priya',
        'Nair',
        'priya.nair@example.com',
        'Password123!',
        'Neurology',
        specialization='Cognitive Neurology',
        consultation_fee=900.0,
        publishing_status='published',
        is_verified=False
    )
    TEMP_DATA['doctors'][doc_id] = doc

    res = client.get(f'/doctor/{doc_id}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify procedural pulse SVG wave is present
    assert "Dynamic Medical Pulse Waveform Accent" in html
    assert "Clinical Care Network" in html
    assert "Admin Verification In Review" in html
